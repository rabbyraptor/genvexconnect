"""Offline execution tests for the in-place DEV7 Core pairing options flow."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
NAMESPACE = "offline_genvex_options"
DEVICE_ID = "123456789012"
MANUAL_TOKEN = "M" * 43
AUTO_TOKEN = "A" * 43


class FakeOptionsFlow:
    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "data": data}

    def async_show_form(self, *, step_id, data_schema, errors):
        return {"type": "form", "step_id": step_id, "errors": errors}

    @property
    def config_entry(self):
        return self._entry


class PairingOptionsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.lookups = []
        self.fail_pairing = False
        self.returned_token = AUTO_TOKEN
        self.entry = types.SimpleNamespace(
            data={"device_id": DEVICE_ID, "runtime_token": MANUAL_TOKEN,
                  "runtime_endpoint": "http://local-genvex-nabto-remote:18275/v1/snapshot"},
            options={},
            entry_id="existing-remote",
        )
        outer = self

        class FakeConfigEntries:
            def async_update_entry(self, entry, *, data):
                outer.entry.data = data

        self.hass = types.SimpleNamespace(config_entries=FakeConfigEntries())
        package = types.ModuleType(NAMESPACE)
        package.__path__ = [str(ROOT)]
        const = types.ModuleType(NAMESPACE + ".const")
        const.CONF_DEVICE_ID = "device_id"
        const.CONF_RUNTIME_TOKEN = "runtime_token"
        const.CONF_PAIR_FROM_APP = "pair_from_app"
        const.CONF_RAW_REGISTERS_V3 = "raw_registers_v3"
        const.CONF_FAN_LEVEL_V4 = "fan_level_v4"
        pairing = types.ModuleType(NAMESPACE + ".supervisor_pairing")

        class Unavailable(ValueError):
            pass

        pairing.SupervisorPairingUnavailable = Unavailable
        core = types.ModuleType(NAMESPACE + ".core_supervisor_loader")

        async def paired_token(hass, *, device_id):
            self.lookups.append((hass, device_id))
            if self.fail_pairing:
                raise Unavailable("PRIVATE")
            return self.returned_token

        core.async_fetch_paired_token = paired_token
        ha = types.ModuleType("homeassistant")
        config_entries = types.ModuleType("homeassistant.config_entries")
        config_entries.OptionsFlowWithReload = FakeOptionsFlow
        ha.config_entries = config_entries
        selectors = types.ModuleType("homeassistant.helpers.selector")
        selectors.TextSelector = lambda config: config
        selectors.TextSelectorConfig = lambda **kwargs: kwargs
        selectors.TextSelectorType = types.SimpleNamespace(PASSWORD="password")
        helpers = types.ModuleType("homeassistant.helpers")
        helpers.selector = selectors
        vol = types.ModuleType("voluptuous")
        vol.Optional = lambda key, **kwargs: key
        vol.Schema = lambda dictionary: dictionary
        self.modules = patch.dict(sys.modules, {
            NAMESPACE: package,
            NAMESPACE + ".const": const,
            NAMESPACE + ".supervisor_pairing": pairing,
            NAMESPACE + ".core_supervisor_loader": core,
            "homeassistant": ha,
            "homeassistant.config_entries": config_entries,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.selector": selectors,
            "voluptuous": vol,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            NAMESPACE + ".pairing_options", ROOT / "pairing_options.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.flow = module.GenvexRemoteOptionsFlow()
        self.flow._entry = self.entry
        self.flow.hass = self.hass

    async def test_existing_manual_entry_preserved_until_opt_in(self):
        result = await self.flow.async_step_init()
        self.assertEqual(result["type"], "form")
        self.assertEqual(self.entry.data["runtime_token"], MANUAL_TOKEN)
        self.assertEqual(self.lookups, [])

    async def test_successful_switch_removes_stored_token_and_keeps_entry(self):
        before = self.entry.entry_id
        result = await self.flow.async_step_init({"pair_from_app": True})
        self.assertEqual(result, {
            "type": "create_entry", "data": {"pair_from_app": True},
        })
        self.assertEqual(self.lookups, [(self.hass, DEVICE_ID)])
        self.assertEqual(self.entry.entry_id, before)
        self.assertNotIn("runtime_token", self.entry.data)
        self.assertEqual(self.entry.data["device_id"], DEVICE_ID)
        self.assertIn("runtime_endpoint", self.entry.data)

    async def test_failure_keeps_original_manual_token(self):
        self.fail_pairing = True
        result = await self.flow.async_step_init({"pair_from_app": True})
        self.assertEqual(result["errors"], {
            "base": "app_pairing_unavailable"
        })
        self.assertEqual(self.entry.data["runtime_token"], MANUAL_TOKEN)

    async def test_manual_entry_can_keep_token_without_retyping(self):
        result = await self.flow.async_step_init({"pair_from_app": False})
        self.assertEqual(result["data"], {"pair_from_app": False})
        self.assertEqual(self.entry.data["runtime_token"], MANUAL_TOKEN)
        self.assertEqual(self.lookups, [])

    async def test_reverse_pairing_requires_new_manual_token(self):
        self.entry.options["pair_from_app"] = True
        self.entry.data.pop("runtime_token")
        result = await self.flow.async_step_init({"pair_from_app": False})
        self.assertEqual(result["errors"], {
            "base": "invalid_runtime_config"
        })
        self.assertNotIn("runtime_token", self.entry.data)
        result = await self.flow.async_step_init({
            "pair_from_app": False, "runtime_token": MANUAL_TOKEN
        })
        self.assertEqual(result["data"], {"pair_from_app": False})
        self.assertEqual(self.entry.data["runtime_token"], MANUAL_TOKEN)

    async def test_non_boolean_flag_is_not_accepted(self):
        result = await self.flow.async_step_init({"pair_from_app": "true"})
        self.assertEqual(result["errors"], {
            "base": "invalid_runtime_config"
        })
        self.assertEqual(self.lookups, [])

    async def test_v3_opt_in_and_disable_preserve_pairing(self):
        result = await self.flow.async_step_init({
            "pair_from_app": True, "raw_registers_v3": True,
        })
        self.assertEqual(result["data"], {
            "pair_from_app": True, "raw_registers_v3": True,
        })
        self.assertNotIn("runtime_token", self.entry.data)
        self.entry.options = dict(result["data"])
        self.lookups.clear()
        result = await self.flow.async_step_init({
            "pair_from_app": True, "raw_registers_v3": False,
        })
        self.assertEqual(result["data"], {"pair_from_app": True})
        self.assertEqual(len(self.lookups), 1)

    async def test_raw_v3_non_boolean_flag_is_rejected(self):
        for flag in ("true", 1, None):
            with self.subTest(flag=flag):
                result = await self.flow.async_step_init({
                    "pair_from_app": True, "raw_registers_v3": flag,
                })
                self.assertEqual(
                    result["errors"], {"base": "invalid_runtime_config"}
                )
        self.assertEqual(self.lookups, [])

    async def test_invalid_supervisor_token_is_not_persisted(self):
        self.returned_token = "short"
        result = await self.flow.async_step_init({"pair_from_app": True})
        self.assertEqual(result["errors"], {
            "base": "app_pairing_unavailable"
        })
        self.assertEqual(self.entry.data["runtime_token"], MANUAL_TOKEN)


if __name__ == "__main__":
    unittest.main()
