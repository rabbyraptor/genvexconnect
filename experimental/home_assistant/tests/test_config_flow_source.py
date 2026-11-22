"""Offline source contract for the pinned-endpoint and optional Core pairing flow."""
from pathlib import Path
import ast
import json
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
SOURCE = ROOT / "config_flow.py"


class OnboardingSourceTests(unittest.TestCase):
    def test_config_flow_never_accepts_untrusted_url(self):
        source = SOURCE.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("vol.Required(CONF_RUNTIME_ENDPOINT)", source)
        self.assertNotIn("user_input[CONF_RUNTIME_ENDPOINT]", source)
        self.assertIn("CONF_RUNTIME_ENDPOINT: EXPECTED_APP_ENDPOINT", source)
        self.assertIn("vol.Required(CONF_DEVICE_ID)", source)

    def test_manual_ipc_token_alternative_remains_available(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("vol.Optional(CONF_RUNTIME_TOKEN)", source)
        self.assertIn("TextSelectorType.PASSWORD", source)
        self.assertNotIn("unlock_secret", source)
        self.assertNotIn("account_password", source)

    def test_supervisor_pairing_requires_explicit_boolean_opt_in(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('CONF_PAIR_FROM_APP = "pair_from_app"', source)
        self.assertIn("vol.Optional(CONF_PAIR_FROM_APP, default=False)", source)
        self.assertIn("type(user_input.get(CONF_PAIR_FROM_APP, False)) is not bool", source)
        self.assertIn("if user_input.get(CONF_PAIR_FROM_APP) is True:", source)
        self.assertIn("await async_fetch_paired_token(", source)
        self.assertIn('errors["base"] = "app_pairing_unavailable"', source)

    def test_error_translations_present(self):
        for filename in ("strings.json", "translations/da.json"):
            with self.subTest(filename=filename):
                payload = json.loads((ROOT / filename).read_text())
                data = payload["config"]["step"]["user"]["data"]
                errors = payload["config"]["error"]
                self.assertIn("pair_from_app", data)
                self.assertIn("runtime_token", data)
                self.assertNotIn("runtime_endpoint", data)
                self.assertIn("app_pairing_unavailable", errors)


if __name__ == "__main__":
    unittest.main()
