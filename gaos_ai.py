"""
GAOS™ AI Provider Manager  v3.4
================================
Unified interface to multiple AI providers with automatic failover.

Provider Selection Logic:
  1. If customer has configured a primary AI in config, use it as primary
  2. If no customer preference, use Groq as primary (free), DeepSeek as fallback
  3. If both fail, return empty/default value

Each provider has a circuit breaker to prevent repeated calls to a failing service.
Cost tracking is logged to Usage_Log sheet tab (module 36 reads this for reports).

Public Interface:
  ask_ai(prompt, max_tokens=500, expect_json=True, system=None)
  chat_ai(messages, system_prompt=None, max_tokens=500)
  get_ai_status() -> dict (for dashboard / module 36)
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
    """
    Prevents cascading failures by tracking consecutive failures.
    After threshold failures, opens the circuit for cooldown seconds,
    then tries a half-open state before fully closing.
    """
    def __init__(self, name: str, threshold: int = 5, cooldown: int = 600):
        self.name      = name
        self.threshold = threshold
        self.cooldown  = cooldown
        self.failures  = 0
        self.opened_at = 0.0
        self.state     = "closed"   # closed | open | half-open

    def allow(self) -> bool:
        """Returns True if a request should be attempted."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.opened_at >= self.cooldown:
                self.state = "half-open"
                _log.info("Circuit %s → half-open (attempting recovery)", self.name)
                return True
            return False
        return True  # half-open: let one through

    def success(self):
        """Resets the circuit to closed on successful request."""
        self.failures = 0
        if self.state != "closed":
            _log.info("Circuit %s → closed (recovery successful)", self.name)
        self.state = "closed"

    def failure(self):
        """Increments failure count; opens circuit if threshold exceeded."""
        self.failures += 1
        if self.failures >= self.threshold:
            self.state     = "open"
            self.opened_at = time.time()
            _log.warning("Circuit %s OPENED after %d consecutive failures (cooldown: %ds)",
                        self.name, self.failures, self.cooldown)


# ── PROVIDERS ─────────────────────────────────────────────────

class _Provider:
    """Wrapper for a single AI provider (DeepSeek or Groq)."""

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
        self.last_error   = None

    def _post(self, messages: list, max_tokens: int, temperature: float,
              expect_json: bool) -> Optional[str]:
        """Sends a single API request; returns content or None on failure."""
        if not self.api_key or self.api_key.startswith("YOUR_"):
            self.last_error = "No API key configured"
            return None
        if not self.breaker.allow():
            self.last_error = "Circuit breaker open"
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
            self.last_error = None
            self._log_usage(tokens)
            return content
        except Exception as exc:
            self.breaker.failure()
            self.last_error = str(exc)
            _log.warning("[%s] Request failed: %s", self.name, exc)
            return None

    def _log_usage(self, tokens: int):
        """
        Persists token usage to the Usage_Log sheet tab so module 36
        (Cost Rollup Reporter) can produce monthly reports.
        
        Never raises — logs failures to stderr so they don't break successful
        AI calls. Usage loss is tracked and reported.
        """
        if not tokens:
            return
        try:
            from gaos_core import load_config, log_usage
            cfg = load_config()
            if cfg.get("google_sheets", {}).get("sheet_id"):
                log_usage(cfg, f"ai_{self.name}", tokens,
                          (tokens / 1000) * self.cost_per_1k)
        except Exception as exc:
            # Log to stderr so operators see usage tracking failures
            _log.error(
                "[%s] Usage logging failed (tokens: %d, cost: %.6f GBP) — "
                "module 36 cost report may be incomplete: %s",
                self.name, tokens, (tokens / 1000) * self.cost_per_1k, exc
            )

    def ask(self, prompt: str, max_tokens: int, expect_json: bool,
            system: Optional[str]) -> Optional[object]:
        """Calls the provider to generate a JSON or text response."""
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
            _log.warning("[%s] JSON parse failed: %s — raw: %.120s",
                        self.name, exc, cleaned)
            return None

    def chat(self, messages: list, system_prompt: Optional[str],
             max_tokens: int) -> Optional[str]:
        """Calls the provider for a multi-turn conversation."""
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.extend(messages)
        return self._post(msgs, max_tokens, 0.4, expect_json=False)


# ── MANAGER SINGLETON ─────────────────────────────────────────

class _AIManager:
    """
    Manages multiple AI providers with customer-first selection logic.
    
    Selection order:
      1. If customer has a configured provider preference, use it as primary
      2. Otherwise, Groq (free) is primary, DeepSeek is fallback
      3. If both fail, return empty value
    """

    def __init__(self):
        self._providers: list[_Provider] = []
        self._customer_preference = None  # Track which provider customer chose
        self._build()

    def _build(self):
        """Loads config and initializes providers with customer-first logic."""
        try:
            from gaos_core import load_config
            cfg = load_config()
        except Exception:
            cfg = {}

        ds_key = (os.environ.get("DEEPSEEK_API_KEY")
                  or cfg.get("deepseek", {}).get("api_key", ""))
        gq_key = (os.environ.get("GROQ_API_KEY")
                  or cfg.get("groq", {}).get("api_key", ""))

        # Determine which provider customer explicitly configured
        customer_pref = None
        if ds_key and not ds_key.startswith("YOUR_"):
            customer_pref = "deepseek"
        if gq_key and not gq_key.startswith("YOUR_"):
            customer_pref = "groq"  # If both present, Groq is preferred (it's free)

        self._customer_preference = customer_pref

        # Build provider list with customer preference first
        if customer_pref == "deepseek" and ds_key and not ds_key.startswith("YOUR_"):
            # Customer wants DeepSeek primary
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

        elif customer_pref == "groq" and gq_key and not gq_key.startswith("YOUR_"):
            # Customer wants Groq primary (or only has Groq)
            self._providers.append(_Provider(
                name="groq",
                api_url="https://api.groq.com/openai/v1/chat/completions",
                model="llama-3.3-70b-versatile",
                api_key=gq_key,
                cost_per_1k=GROQ_COST_PER_1K,
                breaker_cooldown=300,
            ))
            if ds_key and not ds_key.startswith("YOUR_"):
                self._providers.append(_Provider(
                    name="deepseek",
                    api_url="https://api.deepseek.com/v1/chat/completions",
                    model="deepseek-chat",
                    api_key=ds_key,
                    cost_per_1k=DEEPSEEK_COST_PER_1K,
                    breaker_cooldown=600,
                ))

        else:
            # Neither configured or only partial config — default: Groq first, DeepSeek fallback
            if gq_key and not gq_key.startswith("YOUR_"):
                self._providers.append(_Provider(
                    name="groq",
                    api_url="https://api.groq.com/openai/v1/chat/completions",
                    model="llama-3.3-70b-versatile",
                    api_key=gq_key,
                    cost_per_1k=GROQ_COST_PER_1K,
                    breaker_cooldown=300,
                ))
            if ds_key and not ds_key.startswith("YOUR_"):
                self._providers.append(_Provider(
                    name="deepseek",
                    api_url="https://api.deepseek.com/v1/chat/completions",
                    model="deepseek-chat",
                    api_key=ds_key,
                    cost_per_1k=DEEPSEEK_COST_PER_1K,
                    breaker_cooldown=600,
                ))

        names = [p.name for p in self._providers]
        if names:
            pref_str = f" (customer preference: {customer_pref})" if customer_pref else " (default order)"
            _log.info("AI providers: %s%s", " → ".join(names), pref_str)
        else:
            _log.error("No AI providers configured — AI features disabled")

    def ask(self, prompt: str, max_tokens: int, expect_json: bool,
            system: Optional[str]) -> object:
        """Tries each provider in order until one succeeds."""
        for p in self._providers:
            result = p.ask(prompt, max_tokens, expect_json, system)
            if result is not None:
                if p.name != self._providers[0].name:
                    _log.warning("Failover: request handled by %s (primary %s failed)",
                                p.name, self._providers[0].name)
                return result
        _log.error("All AI providers failed (ask) — returning empty")
        return {} if expect_json else ""

    def chat(self, messages: list, system_prompt: Optional[str],
             max_tokens: int) -> str:
        """Tries each provider in order until one succeeds."""
        for p in self._providers:
            result = p.chat(messages, system_prompt, max_tokens)
            if result is not None:
                if p.name != self._providers[0].name:
                    _log.warning("Failover: chat handled by %s (primary %s failed)",
                                p.name, self._providers[0].name)
                return result
        _log.error("All AI providers failed (chat) — returning empty")
        return ""

    def status(self) -> dict:
        """Returns provider health, cost data, and configuration for dashboard."""
        return {
            "customer_preference": self._customer_preference,
            "active_provider": self._providers[0].name if self._providers else "none",
            "total_providers": len(self._providers),
            "providers": [
                {
                    "name":          p.name,
                    "calls":         p.total_calls,
                    "tokens":        p.total_tokens,
                    "cost_gbp":      round(p.total_cost, 6),
                    "circuit_state": p.breaker.state,
                    "last_error":    p.last_error,
                }
                for p in self._providers
            ],
        }


_manager: Optional[_AIManager] = None


def _get_manager() -> _AIManager:
    """Returns or initializes the singleton manager."""
    global _manager
    if _manager is None:
        _manager = _AIManager()
    return _manager

def reset():
    """Force re-initialisation (e.g. after config.json change)."""
    global _manager
    _manager = None
    _log.info("AI manager reset")


# ── PUBLIC INTERFACE ──────────────────────────────────────────
def ask_ai(prompt: str, max_tokens: int = 500,
           expect_json: bool = True, system: str = None) -> object:
    """
    Generates a response to a prompt using configured AI providers.
    
    Provider selection:
      - If customer configured a primary provider, uses it
      - Otherwise defaults to Groq (free) with DeepSeek fallback
      - Tries each provider in order until one succeeds
    
    Args:
      prompt: The prompt to send to the AI
      max_tokens: Maximum response length (default 500)
      expect_json: Whether response should be valid JSON (default True)
      system: Optional system prompt to shape behavior
    
    Returns:
      Parsed JSON dict if expect_json=True, else text string.
      Returns {} or "" on total failure.
    """
    return _get_manager().ask(prompt, max_tokens, expect_json, system)

def chat_ai(messages: list, system_prompt: str = None,
            max_tokens: int = 500) -> str:
    """
    Conducts a multi-turn conversation using configured AI providers.
    
    Provider selection:
      - If customer configured a primary provider, uses it
      - Otherwise defaults to Groq (free) with DeepSeek fallback
      - Tries each provider in order until one succeeds
    
    Args:
      messages: List of {"role": "user"|"assistant", "content": "..."} dicts
      system_prompt: Optional system message to shape behavior
      max_tokens: Maximum response length (default 500)
    
    Returns:
      Text response string. Returns "" on total failure.
    """
    return _get_manager().chat(messages, system_prompt, max_tokens)

def get_ai_status() -> dict:
    """
    Returns provider health, cost data, and configuration.
    Used by:
      - /health endpoint (gaos_server.py)
      - Module 36 (Cost Rollup Reporter) for monthly reports
      - Dashboard views
    """
    return _get_manager().status()
