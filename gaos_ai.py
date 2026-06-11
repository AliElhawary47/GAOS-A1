"""
GAOS™ AI Provider Manager  v3.4
================================
Unified interface to multiple AI providers with automatic failover.

Primary:  DeepSeek (deepseek-chat) — low cost, high quality
Fallback: Groq     (llama-3.3-70b) — free tier, always on

All 33+ modules keep calling core.ask_deepseek() / core.chat_deepseek()
unchanged.  gaos_core routes those calls through this module transparently.

Interface (the only surface callers ever see):
  ask_ai(prompt, api_key=None, max_tokens=500, expect_json=True, system=None)
  chat_ai(messages, api_key=None, system_prompt=None, max_tokens=500)
  get_ai_status()   -> dict   (for dashboard / logging)
"""

import json
import logging
import os
import re
import time
from typing import Optional

import requests

_log = logging.getLogger("gaos.ai")

# ── COST CONSTANTS ────────────────────────────────────────────
DEEPSEEK_COST_PER_1K = 0.00014   # GBP  (deepseek-chat input+output blended)
GROQ_COST_PER_1K     = 0.0       # free tier


# ── CIRCUIT BREAKER ───────────────────────────────────────────

class _CircuitBreaker:
    def __init__(self, name: str, threshold: int = 5, cooldown: int = 600):
        self.name      = name
        self.threshold = threshold
        self.cooldown  = cooldown
        self.failures  = 0
        self.opened_at = 0.0
        self.state     = "closed"   # closed | open | half-open

    def allow(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.opened_at >= self.cooldown:
                self.state = "half-open"
                _log.info("Circuit %s → half-open", self.name)
                return True
            return False
        return True  # half-open: let one through

    def success(self):
        self.failures = 0
        if self.state != "closed":
            _log.info("Circuit %s → closed", self.name)
        self.state = "closed"

    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.state     = "open"
            self.opened_at = time.time()
            _log.warning("Circuit %s OPENED after %d failures", self.name, self.failures)


# ── PROVIDERS ─────────────────────────────────────────────────

class _Provider:
    def __init__(self, name: str, api_url: str, model: str,
                 api_key: str, cost_per_1k: float, breaker_cooldown: int = 600):
        self.name         = name
        self.api_url      = api_url
        self.model        = model
        self.api_key      = api_key
        self.cost_per_1k  = cost_per_1k
        self.breaker      = _CircuitBreaker(name, cooldown=breaker_cooldown)
        self.total_tokens = 0
        self.total_cost   = 0.0
        self.total_calls  = 0

    def _post(self, messages: list, max_tokens: int, temperature: float,
              expect_json: bool) -> Optional[str]:
        if not self.api_key or self.api_key.startswith("YOUR_"):
            return None
        if not self.breaker.allow():
            return None
        payload = {
            "model":      self.model,
            "messages":   messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if expect_json and self.name == "deepseek":
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data    = resp.json()
            content = data["choices"][0]["message"]["content"]
            tokens  = data.get("usage", {}).get("total_tokens", 0)
            self.total_tokens += tokens
            self.total_cost   += (tokens / 1000) * self.cost_per_1k
            self.total_calls  += 1
            self.breaker.success()
            self._log_usage(tokens)
            return content
        except Exception as exc:
            self.breaker.failure()
            _log.warning("[%s] %s", self.name, exc)
            return None

    def _log_usage(self, tokens: int):
        """Persists token usage to the Usage_Log sheet tab so module 36
        (Cost Rollup) can produce monthly reports. Never raises — a
        logging failure must not break the AI call that just succeeded."""
        if not tokens:
            return
        try:
            from gaos_core import load_config, log_usage
            cfg = load_config()
            if cfg.get("google_sheets", {}).get("sheet_id"):
                log_usage(cfg, self.name, tokens,
                          (tokens / 1000) * self.cost_per_1k)
        except Exception:
            pass

    def ask(self, prompt: str, max_tokens: int, expect_json: bool,
            system: Optional[str]) -> Optional[object]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        raw = self._post(msgs, max_tokens, 0.0, expect_json)
        if raw is None:
            return None
        if not expect_json:
            return raw
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except Exception as exc:
            _log.warning("[%s] JSON parse failed: %s — raw: %.120s", self.name, exc, cleaned)
            return None

    def chat(self, messages: list, system_prompt: Optional[str],
             max_tokens: int) -> Optional[str]:
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        return self._post(msgs, max_tokens, 0.4, expect_json=False)


# ── MANAGER SINGLETON ─────────────────────────────────────────

class _AIManager:
    """Holds ordered provider list and tries each in turn."""

    def __init__(self):
        self._providers: list[_Provider] = []
        self._build()

    def _build(self):
        try:
            # Lazy import — gaos_core only imports gaos_ai inside function
            # bodies, so there is no circular import at module load time.
            # Using core.load_config() means GAOS_CONFIG_JSON (cloud deploys)
            # works for AI provider keys exactly like it does everywhere else.
            from gaos_core import load_config
            cfg = load_config()
        except Exception:
            cfg = {}

        ds_key = (os.environ.get("DEEPSEEK_API_KEY")
                  or cfg.get("deepseek", {}).get("api_key", ""))
        gq_key = (os.environ.get("GROQ_API_KEY")
                  or cfg.get("groq", {}).get("api_key", ""))

        if ds_key and not ds_key.startswith("YOUR_"):
            self._providers.append(_Provider(
                name="deepseek",
                api_url="https://api.deepseek.com/v1/chat/completions",
                model="deepseek-chat",
                api_key=ds_key,
                cost_per_1k=DEEPSEEK_COST_PER_1K,
                breaker_cooldown=600,
            ))
        if gq_key and not gq_key.startswith("YOUR_"):
            self._providers.append(_Provider(
                name="groq",
                api_url="https://api.groq.com/openai/v1/chat/completions",
                model="llama-3.3-70b-versatile",
                api_key=gq_key,
                cost_per_1k=GROQ_COST_PER_1K,
                breaker_cooldown=300,
            ))

        names = [p.name for p in self._providers]
        if names:
            _log.info("AI providers: %s", " → ".join(names))
        else:
            _log.error("No AI providers configured — AI features disabled")

    def ask(self, prompt: str, max_tokens: int, expect_json: bool,
            system: Optional[str]) -> object:
        for p in self._providers:
            result = p.ask(prompt, max_tokens, expect_json, system)
            if result is not None:
                if p.name != self._providers[0].name:
                    _log.warning("Failover: request handled by %s", p.name)
                return result
        _log.error("All AI providers failed (ask)")
        return {} if expect_json else ""

    def chat(self, messages: list, system_prompt: Optional[str],
             max_tokens: int) -> str:
        for p in self._providers:
            result = p.chat(messages, system_prompt, max_tokens)
            if result is not None:
                if p.name != self._providers[0].name:
                    _log.warning("Failover: chat handled by %s", p.name)
                return result
        _log.error("All AI providers failed (chat)")
        return ""

    def status(self) -> dict:
        return {
            "active_provider": self._providers[0].name if self._providers else "none",
            "providers": [
                {
                    "name":          p.name,
                    "calls":         p.total_calls,
                    "tokens":        p.total_tokens,
                    "cost_gbp":      round(p.total_cost, 6),
                    "circuit_state": p.breaker.state,
                }
                for p in self._providers
            ],
        }


_manager: Optional[_AIManager] = None


def _get_manager() -> _AIManager:
    global _manager
    if _manager is None:
        _manager = _AIManager()
    return _manager


def reset():
    """Force re-initialisation (e.g. after config.json change)."""
    global _manager
    _manager = None


# ── PUBLIC INTERFACE ──────────────────────────────────────────

def ask_ai(prompt: str, api_key: str = None, max_tokens: int = 500,
           expect_json: bool = True, system: str = None) -> object:
    """Drop-in replacement for the bare DeepSeek call.
    api_key is accepted but ignored — keys come from config/env."""
    return _get_manager().ask(prompt, max_tokens, expect_json, system)


def chat_ai(messages: list, api_key: str = None, system_prompt: str = None,
            max_tokens: int = 500) -> str:
    """Drop-in replacement for the bare DeepSeek chat call."""
    return _get_manager().chat(messages, system_prompt, max_tokens)


def get_ai_status() -> dict:
    """Returns provider health and cost data for dashboard / module 36."""
    return _get_manager().status()
