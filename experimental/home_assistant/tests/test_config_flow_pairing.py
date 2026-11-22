"""Execute the real config-flow source with minimal offline HA stubs.

Verifies the explicit opt-in flow and manual fallback without HA Core,
Supervisor credentials, network, an SDK, or the installed HAOS instance.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
NAMESPACE = "offline_genvex_config_flow"

DEVICE = "123456789012"
TOKEN = "R" * 43


class ConfigFlowBase:
    def __init_subclass__(cls, **kwargs):
        kwargs.pop("domain", None)
        return super().__init_subclass__(**kwargs)

    async def async_set_unique_id(self, device_id):
        self.unique_id = device_id

    def _abort_if_unique_id_configured(self):
        return None

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, *, step_id, data_schema, errors):
        return {"type": "form", "step_id": step_id, "errors": errors}


class ConfigFlowPairingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = []
        pkg = types.ModuleType(NAMESPACE)
        pkg.__path__ = [str(ROOT)]
        constants = types.ModuleType(f"{NAMESPACE}.const")
        constants.CONF_DEVICE_ID = "device_id"
        constants.CONF_RUNTIME_ENDPOINT = "runtime_endpoint"
        constants.CONF_RUNTIME_TOKEN = "runtime_token"
        constants.CONF_PAIR_FROM_APP = "pair_from_app"
        constants.DOMAIN = "genvex_remote"
        constants.valid_device_id = (
            lambda value: type(value) is str
            and len(value) == 12 and value.isascii() and value.isdecimal()
        )
        runtime = types.ModuleType(f"{NAMESPACE}.runtime_client")
        runtime.EXPECTED_APP_ENDPOINT = (
            "http://local-genvex-nabto-remote:18275/v1/snapshot"
        )
        pairing = types.ModuleType(f"{NAMESPACE}.supervisor_pairing")

        class PairingUnavailable(ValueError):
            pass

        pairing.SupervisorPairingUnavailable = PairingUnavailable
        core = types.ModuleType(f"{NAMESPACE}.core_supervisor_loader")

        async def fetch(hass, *, device_id):
            self.calls.append((hass, device_id))
            return TOKEN

        core.async_fetch_paired_token = fetch

        config_entries = types.ModuleType("homeassistant.config_entries")
        config_entries.ConfigFlow = ConfigFlowBase
        homeassistant = types.ModuleType("homeassistant")
        homeassistant.config_entries = config_entries
        helpers = types.ModuleType("homeassistant.helpers")
        selector = types.ModuleType("homeassistant.helpers.selector")

        class PasswordSelectorType:
            PASSWORD = "password"

        selector.TextSelectorType = PasswordSelectorType
        selector.TextSelectorConfig = lambda **kwargs: kwargs
        selector.TextSelector = lambda value: value
        voluptuous = types.ModuleType("voluptuous")
        voluptuous.Required = lambda key, **kwargs: ("required", key)
        voluptuous.Optional = lambda key, **kwargs: ("optional", key)
        voluptuous.Schema = lambda data: data

        self.patch_modules = patch.dict(sys.modules, {
            NAMESPACE: pkg,
            f"{NAMESPACE}.const": constants,
            f"{NAMESPACE}.runtime_client": runtime,
            f"{NAMESPACE}.supervisor_pairing": pairing,
            f"{NAMESPACE}.core_supervisor_loader": core,
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.selector": selector,
            "voluptuous": voluptuous,
        })
        self.patch_modules.start()
        self.addCleanup(self.patch_modules.stop)
        spec = importlib.util.spec_from_file_location(
            f"{NAMESPACE}.config_flow", ROOT / "config_flow.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        self.core = core
        self.flow = module.GenvexRemoteConfigFlow()
        self.flow.hass = object()

    async def test_manual_token_flow_does_not_touch_supervisor(self):
        result = await self.flow.async_step_user({
            "device_id": DEVICE, "runtime_token": TOKEN,
        })
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["runtime_token"], TOKEN)
        self.assertEqual(result["data"]["runtime_endpoint"],
                         self.module.EXPECTED_APP_ENDPOINT)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.flow.unique_id, DEVICE)

    async def test_auto_pairing_requires_explicit_true(self):
        result = await self.flow.async_step_user({
            "device_id": DEVICE, "pair_from_app": True,
        })
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["pair_from_app"], True)
        self.assertNotIn("runtime_token", result["data"])
        self.assertEqual(self.calls, [(self.flow.hass, DEVICE)])

    async def test_missing_token_without_optin_is_rejected(self):
        result = await self.flow.async_step_user({"device_id": DEVICE})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"]["base"], "invalid_runtime_config")
        self.assertEqual(self.calls, [])

    async def test_nonboolean_pair_flag_is_rejected_before_access(self):
        result = await self.flow.async_step_user({
            "device_id": DEVICE, "pair_from_app": "true",
            "runtime_token": TOKEN,
        })
        self.assertEqual(result["errors"]["base"], "invalid_runtime_config")
        self.assertEqual(self.calls, [])

    async def test_invalid_device_rejected_before_access(self):
        result = await self.flow.async_step_user({
            "device_id": "invalid", "pair_from_app": True,
        })
        self.assertEqual(result["errors"]["base"], "invalid_device_id")
        self.assertEqual(self.calls, [])

    async def test_supervisor_failure_preserves_manual_fallback(self):
        async def failing(_hass, *, device_id):
            raise self.module.SupervisorPairingUnavailable("PRIVATE")

        self.core.async_fetch_paired_token = failing
        # The imported reference is captured at module-import time.
        self.module.async_fetch_paired_token = failing
        failed = await self.flow.async_step_user({
            "device_id": DEVICE, "pair_from_app": True,
        })
        self.assertEqual(failed["errors"]["base"], "app_pairing_unavailable")
        self.assertEqual(failed["type"], "form")
        manual = await self.flow.async_step_user({
            "device_id": DEVICE, "runtime_token": TOKEN,
        })
        self.assertEqual(manual["type"], "create_entry")


if __name__ == "__main__":
    unittest.main()
