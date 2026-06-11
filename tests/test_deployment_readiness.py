"""
GAOS deployment-readiness test suite.

Run from the project root:
    python -m unittest tests.test_deployment_readiness -v

Covers the v3.3.1 hardening fixes:
  * GAOS_CONFIG_JSON env fallback (cloud config without config.json)
  * CORS headers + OPTIONS preflight for the cross-origin chat widget
  * Honest /health reporting (config_loaded / config_source)
  * Message length clamping on /chat and /whatsapp
  * Twilio signature validation (opt-in via GAOS_VALIDATE_TWILIO)
  * should_run_at double-fire dedupe
  * Bounded session stores in modules 22 / 23 / 24
  * gaos_ai env-key bootstrapping with import-order fix
No external test framework and no network access required.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_CONFIG = {
    "business": {"name": "Test Plumbing Ltd"},
    "deepseek": {"api_key": "sk-test"},
    "google_sheets": {"sheet_id": "sheet123", "tabs": {}},
    "twilio": {
        "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "auth_token": "testtoken123",
        "from_number": "+447000000000",
        "owner_mobile": "+447111111111",
    },
    "server": {"port": 8080},
}


class TestConfigEnvFallback(unittest.TestCase):
    """config.json is gitignored — Railway must get config from the env."""

    def setUp(self):
        import gaos_core
        self.core = gaos_core

    def test_env_json_used_when_file_missing(self):
        with mock.patch.dict(os.environ,
                             {"GAOS_CONFIG_JSON": json.dumps(FAKE_CONFIG)}):
            cfg = self.core.load_config(path="definitely_missing.json")
        self.assertEqual(cfg["business"]["name"], "Test Plumbing Ltd")

    def test_empty_when_nothing_available(self):
        env = {k: v for k, v in os.environ.items() if k != "GAOS_CONFIG_JSON"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = self.core.load_config(path="definitely_missing.json")
        self.assertEqual(cfg, {})

    def test_invalid_env_json_returns_empty_not_crash(self):
        with mock.patch.dict(os.environ, {"GAOS_CONFIG_JSON": "{not json"}):
            cfg = self.core.load_config(path="definitely_missing.json")
        self.assertEqual(cfg, {})

    def test_config_source_reporting(self):
        env = {k: v for k, v in os.environ.items() if k != "GAOS_CONFIG_JSON"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(self.core.config_source(), "none")
        with mock.patch.dict(os.environ, {"GAOS_CONFIG_JSON": "{}"}):
            # file absent in test runner CWD → env wins
            if not os.path.exists("config.json"):
                self.assertEqual(self.core.config_source(), "env")


class TestScheduler(unittest.TestCase):
    """should_run_at must fire at most once per window per day."""

    def setUp(self):
        import gaos_core
        self.core = gaos_core
        self.core._fired_slots.clear()

    def test_fires_once_then_dedupes_within_window(self):
        from datetime import datetime
        fixed = datetime(2026, 6, 10, 8, 2, 0)  # Wed 08:02 — inside 08:00–08:05

        def poll():  # single call site, like a module's run loop
            return self.core.should_run_at(8)

        with mock.patch("gaos_core.datetime") as dt:
            dt.now.return_value = fixed
            self.assertTrue(poll())    # first poll fires
            self.assertFalse(poll())   # second poll deduped

    def test_outside_window_never_fires(self):
        from datetime import datetime
        fixed = datetime(2026, 6, 10, 9, 30, 0)
        with mock.patch("gaos_core.datetime") as dt:
            dt.now.return_value = fixed
            self.assertFalse(self.core.should_run_at(8))

    def test_next_day_fires_again(self):
        from datetime import datetime

        def poll():
            return self.core.should_run_at(8)

        with mock.patch("gaos_core.datetime") as dt:
            dt.now.return_value = datetime(2026, 6, 10, 8, 1, 0)
            self.assertTrue(poll())
            dt.now.return_value = datetime(2026, 6, 11, 8, 1, 0)
            self.assertTrue(poll())    # new day, fires again

    def test_independent_slots_do_not_collide(self):
        from datetime import datetime
        with mock.patch("gaos_core.datetime") as dt:
            dt.now.return_value = datetime(2026, 6, 10, 8, 1, 0)
            # Two DIFFERENT call sites at the same hour: both must fire.
            self.assertTrue(self.core.should_run_at(8))
            self.assertTrue(self.core.should_run_at(8))  # different line → fires

    def test_same_call_site_in_loop_dedupes(self):
        from datetime import datetime

        def poll():  # one call site, polled repeatedly (the run_loop pattern)
            return self.core.should_run_at(8)

        with mock.patch("gaos_core.datetime") as dt:
            dt.now.return_value = datetime(2026, 6, 10, 8, 1, 0)
            self.assertTrue(poll())
            dt.now.return_value = datetime(2026, 6, 10, 8, 4, 0)
            self.assertFalse(poll())  # same window, same site → deduped


class _ServerTestBase(unittest.TestCase):
    """Boots gaos_server with FAKE_CONFIG injected via the env path."""

    @classmethod
    def setUpClass(cls):
        cls._env = mock.patch.dict(
            os.environ, {"GAOS_CONFIG_JSON": json.dumps(FAKE_CONFIG)})
        cls._env.start()
        # Force a clean import so module-level _load() sees the env config
        for name in list(sys.modules):
            if name.startswith("gaos_server"):
                del sys.modules[name]
        import gaos_server
        cls.server = gaos_server
        cls.client = gaos_server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls._env.stop()


class TestServerCORS(_ServerTestBase):
    """The widget runs on CLIENT websites — CORS is mandatory for /chat."""

    def test_preflight_options_returns_204_with_cors(self):
        r = self.client.options("/chat",
                                headers={"Origin": "https://client-site.co.uk"})
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", r.headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type",
                      r.headers.get("Access-Control-Allow-Headers", ""))

    def test_chat_post_carries_cors_header(self):
        with mock.patch.object(self.server, "_chatbot") as mod:
            mod.return_value.handle_message.return_value = "Hello!"
            r = self.client.post("/chat",
                                 json={"session_id": "s1", "message": "hi"},
                                 headers={"Origin": "https://client-site.co.uk"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(r.get_json()["reply"], "Hello!")

    def test_origin_allowlist_blocks_unknown_sites(self):
        with mock.patch.dict(os.environ,
                             {"GAOS_ALLOWED_ORIGINS": "https://allowed.co.uk"}):
            ok = self.client.options("/chat",
                                     headers={"Origin": "https://allowed.co.uk"})
            self.assertEqual(ok.headers.get("Access-Control-Allow-Origin"),
                             "https://allowed.co.uk")
            bad = self.client.options("/chat",
                                      headers={"Origin": "https://evil.example"})
            self.assertIsNone(bad.headers.get("Access-Control-Allow-Origin"))


class TestServerRoutes(_ServerTestBase):

    def test_health_reports_true_config_state(self):
        r = self.client.get("/health")
        body = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(body["config_loaded"])
        self.assertIn(body["config_source"], ("env", "file"))

    def test_chat_clamps_oversized_message(self):
        captured = {}
        def fake_handle(cfg, sid, msg):
            captured["len"] = len(msg)
            return "ok"
        with mock.patch.object(self.server, "_chatbot") as mod:
            mod.return_value.handle_message.side_effect = fake_handle
            r = self.client.post("/chat", json={"message": "x" * 50000})
        self.assertEqual(r.status_code, 200)
        self.assertLessEqual(captured["len"], self.server.MAX_MESSAGE_CHARS)

    def test_chat_empty_message_400(self):
        r = self.client.post("/chat", json={"message": "   "})
        self.assertEqual(r.status_code, 400)

    def test_whatsapp_happy_path_returns_twiml(self):
        with mock.patch.object(self.server, "_whatsapp") as mod:
            mod.return_value.handle_message.return_value = "Hi there <&>"
            r = self.client.post("/whatsapp",
                                 data={"Body": "hello",
                                       "From": "whatsapp:+447700900000"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/xml", r.content_type)
        self.assertIn("Hi there &lt;&amp;&gt;", r.data.decode())  # XML-escaped

    def test_chat_returns_503_not_crash_when_unconfigured(self):
        # Simulate Railway with NO config at all
        with mock.patch.object(self.server, "_get_cfg", return_value={}):
            r = self.client.post("/chat", json={"message": "hi"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("set up", r.get_json()["reply"])


class TestTwilioSignatureValidation(_ServerTestBase):

    def _sign(self, url, form, token):
        payload = url + "".join(k + form[k] for k in sorted(form))
        digest = hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    def test_disabled_by_default_accepts_unsigned(self):
        with mock.patch.object(self.server, "_whatsapp") as mod:
            mod.return_value.handle_message.return_value = "ok"
            r = self.client.post("/whatsapp",
                                 data={"Body": "hi", "From": "whatsapp:+4477"})
        self.assertEqual(r.status_code, 200)

    def test_enabled_rejects_unsigned_request(self):
        with mock.patch.dict(os.environ, {"GAOS_VALIDATE_TWILIO": "1"}):
            r = self.client.post("/whatsapp",
                                 data={"Body": "hi", "From": "whatsapp:+4477"})
        self.assertEqual(r.status_code, 403)

    def test_enabled_accepts_correctly_signed_request(self):
        form = {"Body": "hi", "From": "whatsapp:+447700900000"}
        url = "http://localhost/whatsapp"
        sig = self._sign(url, form, FAKE_CONFIG["twilio"]["auth_token"])
        with mock.patch.dict(os.environ, {"GAOS_VALIDATE_TWILIO": "1"}), \
             mock.patch.object(self.server, "_whatsapp") as mod:
            mod.return_value.handle_message.return_value = "ok"
            r = self.client.post("/whatsapp", data=form,
                                 headers={"X-Twilio-Signature": sig})
        self.assertEqual(r.status_code, 200)

    def test_enabled_rejects_tampered_signature(self):
        form = {"Body": "hi", "From": "whatsapp:+447700900000"}
        with mock.patch.dict(os.environ, {"GAOS_VALIDATE_TWILIO": "1"}):
            r = self.client.post("/whatsapp", data=form,
                                 headers={"X-Twilio-Signature": "forged=="})
        self.assertEqual(r.status_code, 403)


class TestBoundedSessionStores(unittest.TestCase):
    """Long-lived servers must not grow memory without bound."""

    def test_module_22_evicts_oldest_sessions(self):
        from modules import module_22_website_chatbot as m22
        m22._conversations.clear()
        for i in range(m22.MAX_SESSIONS + 50):
            m22._store_history(f"session_{i}", [{"role": "user", "content": "x"}])
        self.assertEqual(len(m22._conversations), m22.MAX_SESSIONS)
        self.assertNotIn("session_0", m22._conversations)          # oldest gone
        self.assertIn(f"session_{m22.MAX_SESSIONS + 49}",
                      m22._conversations)                           # newest kept

    def test_module_23_evicts_oldest_senders(self):
        from modules import module_23_whatsapp_agent as m23
        m23._conversations.clear()
        for i in range(m23.MAX_SESSIONS + 10):
            m23._store_history(f"+44770{i:07d}", [{"role": "user", "content": "x"}])
        self.assertEqual(len(m23._conversations), m23.MAX_SESSIONS)

    def test_module_24_frees_history_on_end(self):
        from modules import module_24_voice_agent as m24
        m24._calls.clear()
        m24._store_call("CAabc", [{"role": "user", "content": "x"}])
        self.assertIn("CAabc", m24._calls)
        m24._end_call("CAabc")
        self.assertNotIn("CAabc", m24._calls)

    def test_module_24_caps_concurrent_calls(self):
        from modules import module_24_voice_agent as m24
        m24._calls.clear()
        for i in range(m24.MAX_CALLS + 25):
            m24._store_call(f"CA{i}", [])
        self.assertEqual(len(m24._calls), m24.MAX_CALLS)

    def test_history_per_session_stays_bounded(self):
        from modules import module_22_website_chatbot as m22
        m22._conversations.clear()
        long_history = [{"role": "user", "content": str(i)} for i in range(100)]
        m22._store_history("s", long_history)
        self.assertEqual(len(m22._conversations["s"]), m22.MAX_HISTORY)


class TestAIManagerBootstrap(unittest.TestCase):

    def test_env_keys_create_providers(self):
        import gaos_ai
        gaos_ai.reset()
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-live-x",
                                          "GROQ_API_KEY": "gsk-live-y"}):
            status = gaos_ai.get_ai_status()
        names = [p["name"] for p in status["providers"]]
        self.assertEqual(names, ["deepseek", "groq"])
        self.assertEqual(status["active_provider"], "deepseek")
        gaos_ai.reset()

    def test_no_keys_means_no_providers_no_crash(self):
        import gaos_ai
        gaos_ai.reset()
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("DEEPSEEK_API_KEY", "GROQ_API_KEY",
                              "GAOS_CONFIG_JSON")}
        with mock.patch.dict(os.environ, clean, clear=True):
            self.assertEqual(gaos_ai.ask_ai("hi"), {})        # graceful empty
            self.assertEqual(gaos_ai.chat_ai([{"role": "user",
                                               "content": "hi"}]), "")
        gaos_ai.reset()


class TestLauncherIntegrity(unittest.TestCase):
    """Every module the launcher references must exist and import cleanly."""

    def test_all_module_files_importable(self):
        import importlib
        import gaos_launcher as gl
        for mid, path in gl.MODULE_FILES.items():
            with self.subTest(module=mid):
                mod = importlib.import_module(path)
                self.assertTrue(hasattr(mod, "run"),
                                f"module {mid} has no run() entry point")

    def test_every_role_module_id_resolves(self):
        import gaos_launcher as gl
        for role, spec in gl.ROLES.items():
            for mid in spec["modules"]:
                self.assertIn(mid, gl.MODULE_FILES,
                              f"role '{role}' references unknown module {mid}")

    def test_full_team_is_deduplicated(self):
        import gaos_launcher as gl
        self.assertEqual(len(gl.FULL_TEAM_MODULES),
                         len(set(gl.FULL_TEAM_MODULES)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
