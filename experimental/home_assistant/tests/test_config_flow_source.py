"""Offline source contract for the experimental pinned-endpoint config flow."""
from pathlib import Path
import ast
import unittest

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components/genvex_remote/config_flow.py"
)


class OnboardingSourceTests(unittest.TestCase):
    def test_user_is_not_asked_for_internal_app_url(self):
        source = SOURCE.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("vol.Required(CONF_RUNTIME_ENDPOINT)", source)
        self.assertNotIn("user_input[CONF_RUNTIME_ENDPOINT]", source)
        self.assertIn("CONF_RUNTIME_ENDPOINT: EXPECTED_APP_ENDPOINT", source)
        self.assertIn("vol.Required(CONF_RUNTIME_TOKEN)", source)
        self.assertIn("vol.Required(CONF_DEVICE_ID)", source)


if __name__ == "__main__":
    unittest.main()
