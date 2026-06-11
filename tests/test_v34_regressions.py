"""
GAOS v3.4 regression suite.

Run from the project root:
    python -m unittest tests.test_v34_regressions -v

Locks in the v3.4 hardening fixes:
  * Senders (gmail_send / send_sms / send_whatsapp / post_to_slack)
    report success so modules only write dedupe markers on real sends
  * parse_date / safe_int tolerate hand-edited sheet cells
  * should_run_at's widened 10-minute window (poll-straddle safety)
  * TAB_HEADERS is the single source of truth: every tab referenced by
    the industry packs, CORE_TABS, and config.example.json has headers
  * Industry packs no longer reference merged-away modules 09/11
  * Launcher pricing math behind the documented £394/mo Full Team saving
  * Server: root route exists; /health exposes AI provider status
No network access required.
"""

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_deployment_readiness import _ServerTestBase


class TestSendersReturnSuccess(unittest.TestCase):
    """Modules gate their 'Sent' markers on these return values."""

    def setUp(self):
        import gaos_core
        self.core = gaos_core

    def _response_ok(self):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        return resp

    def test_send_sms_true_on_success_false_on_failure(self):
        with mock.patch.object(self.core.requests, "post",
                               return_value=self._response_ok()):
            self.assertTrue(self.core.send_sms("AC1", "tok", "+44", "+44", "hi"))
        with mock.patch.object(self.core.requests, "post",
                               side_effect=Exception("network down")):
            self.assertFalse(self.core.send_sms("AC1", "tok", "+44", "+44", "hi"))

    def test_send_whatsapp_true_on_success_false_on_failure(self):
        with mock.patch.object(self.core.requests, "post",
                               return_value=self._response_ok()):
            self.assertTrue(self.core.send_whatsapp("AC1", "tok", "+44", "+44", "hi"))
        with mock.patch.object(self.core.requests, "post",
                               side_effect=Exception("boom")):
            self.assertFalse(self.core.send_whatsapp("AC1", "tok", "+44", "+44", "hi"))

    def test_post_to_slack_true_on_success_false_on_failure(self):
        with mock.patch.object(self.core.requests, "post",
                               return_value=self._response_ok()):
            self.assertTrue(self.core.post_to_slack("https://hooks", "msg"))
        with mock.patch.object(self.core.requests, "post",
                               side_effect=Exception("boom")):
            self.assertFalse(self.core.post_to_slack("https://hooks", "msg"))

    def test_gmail_send_true_on_success_false_on_failure(self):
        gmail = mock.MagicMock()
        self.assertTrue(self.core.gmail_send(gmail, "a@b.c", "me@x.y", "s", "b"))
        gmail.users().messages().send().execute.side_effect = Exception("quota")
        self.assertFalse(self.core.gmail_send(gmail, "a@b.c", "me@x.y", "s", "b"))


class TestCellParsers(unittest.TestCase):
    """Sheets are hand-edited; one bad cell must never abort a run."""

    def setUp(self):
        import gaos_core
        self.core = gaos_core

    def test_parse_date_accepts_common_formats(self):
        for text in ("2026-06-11", "11/06/2026", "11-06-2026",
                     "11 Jun 2026", "11 June 2026", "2026-06-11 08:00:00"):
            parsed = self.core.parse_date(text)
            self.assertIsNotNone(parsed, f"failed to parse {text!r}")
            self.assertEqual((parsed.year, parsed.month, parsed.day),
                             (2026, 6, 11), f"wrong date for {text!r}")

    def test_parse_date_returns_none_on_junk(self):
        for text in ("", None, "soon", "TBC", "n/a"):
            self.assertIsNone(self.core.parse_date(text))

    def test_safe_int_tolerates_hand_entered_values(self):
        self.assertEqual(self.core.safe_int("30 days"), 30)
        self.assertEqual(self.core.safe_int("30.0"), 30)
        self.assertEqual(self.core.safe_int(25), 25)
        self.assertEqual(self.core.safe_int("", 30), 30)
        self.assertEqual(self.core.safe_int(None, 7), 7)
        self.assertEqual(self.core.safe_int("no number here", 5), 5)


class TestSchedulerWindow(unittest.TestCase):
    """The dedupe window must exceed the 300s poll interval."""

    def setUp(self):
        import gaos_core
        self.core = gaos_core
        self.core._fired_slots.clear()

    def test_default_window_covers_late_poll(self):
        from datetime import datetime
        with mock.patch("gaos_core.datetime") as dt:
            # 08:07 — outside the old 5-minute window, inside the new 10
            dt.now.return_value = datetime(2026, 6, 10, 8, 7, 0)
            self.assertTrue(self.core.should_run_at(8))


class TestSchemaSingleSourceOfTruth(unittest.TestCase):
    """Every tab any component references must have canonical headers."""

    @classmethod
    def setUpClass(cls):
        import gaos_install
        cls.install = gaos_install
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "industry_packs.json"), encoding="utf-8") as fh:
            cls.packs = json.load(fh)
        with open(os.path.join(root, "config.example.json"), encoding="utf-8") as fh:
            cls.config = json.load(fh)

    def test_every_pack_tab_has_headers(self):
        for pack_key, pack in self.packs.items():
            for tab_key, tab_name in pack.get("sheet_tabs", {}).items():
                self.assertIn(tab_name, self.install.TAB_HEADERS,
                              f"pack '{pack_key}' tab '{tab_name}' has no headers")

    def test_core_tabs_all_have_headers(self):
        for tab in self.install.CORE_TABS:
            self.assertIn(tab, self.install.TAB_HEADERS)

    def test_config_example_tabs_all_have_headers(self):
        for key, tab_name in self.config["google_sheets"]["tabs"].items():
            self.assertIn(tab_name, self.install.TAB_HEADERS,
                          f"config tabs.{key} → '{tab_name}' has no headers")

    def test_packs_reference_only_live_modules(self):
        import gaos_launcher as gl
        for pack_key, pack in self.packs.items():
            for mid in pack.get("modules", []):
                self.assertNotIn(mid, ("09", "11"),
                                 f"pack '{pack_key}' references merged module {mid}")
                self.assertIn(mid, gl.MODULE_FILES,
                              f"pack '{pack_key}' references unknown module {mid}")


class TestPricingIntegrity(unittest.TestCase):
    """Backs the documented 'save £394/mo vs individual' claim."""

    def test_full_team_saving_math(self):
        import gaos_launcher as gl
        individual = sum(r["price"] for r in gl.ROLES.values()) + 99  # voice add-on
        self.assertEqual(individual, 1393)
        self.assertEqual(gl.FULL_TEAM_PRICE, 999)
        self.assertEqual(individual - gl.FULL_TEAM_PRICE, 394)

    def test_full_team_covers_all_modules(self):
        import gaos_launcher as gl
        self.assertEqual(set(gl.FULL_TEAM_MODULES), set(gl.MODULE_FILES))


class TestServerSurface(_ServerTestBase):

    def test_root_route_is_not_404(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["service"], "GAOS Web Server")

    def test_health_exposes_ai_provider_status(self):
        r = self.client.get("/health")
        body = r.get_json()
        self.assertIn("ai", body)
        self.assertIn("active_provider", body["ai"])
        self.assertIsInstance(body["ai"]["providers"], list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
