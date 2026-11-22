"""Run real setup_entry source with fake HA Core to verify token handling."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
NAMESPACE = "offline_genvex_setup"


class SetupAutoPairingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tokens = []
        self.token_loaders = []
        self.lookups = []
        self.latest_token = "N" * 43
        self.missing = False

        module = types.ModuleType(NAMESPACE)
        module.__path__ = [str(ROOT)]
        const = types.ModuleType(f"{NAMESPACE}.const")
        for key, value in {
            "CONF_DEVICE_ID": "device_id",
            "CONF_RUNTIME_ENDPOINT": "runtime_endpoint",
            "CONF_RUNTIME_TOKEN": "runtime_token",
            "CONF_PAIR_FROM_APP": "pair_from_app",
            "DOMAIN": "genvex_remote",
        }.items():
            setattr(const, key, value)
        core = types.ModuleType(f"{NAMESPACE}.core_supervisor_loader")
        exceptions = types.ModuleType(f"{NAMESPACE}.supervisor_pairing")

        class PairingUnavailable(ValueError):
            pass

        exceptions.SupervisorPairingUnavailable = PairingUnavailable

        async def fetch(hass, *, device_id):
            self.lookups.append(device_id)
            if self.missing:
                raise PairingUnavailable("PRIVATE")
            return self.latest_token

        core.async_fetch_paired_token = fetch

        coordinator = types.ModuleType(f"{NAMESPACE}.coordinator")
        outer = self

        class FakeCoordinator:
            def __init__(self, hass, device_id, reader):
                outer.tokens.append(reader._token)
                outer.token_loaders.append(reader._token_loader)

            async def async_config_entry_first_refresh(self):
                return None

        coordinator.GenvexRemoteCoordinator = FakeCoordinator

        client = types.ModuleType(f"{NAMESPACE}.runtime_client")

        class FakeReader:
            def __init__(self, session, *, endpoint, token, token_loader=None):
                if endpoint != "http://local-genvex-nabto-remote:18275/v1/snapshot":
                    raise ValueError
                self._token = token
                self._token_loader = token_loader

        client.AuthenticatedSnapshotReader = FakeReader
        homeassistant = types.ModuleType("homeassistant")
        homeassistant.const = types.ModuleType("homeassistant.const")
        homeassistant.const.Platform = types.SimpleNamespace(SENSOR="sensor")
        homeassistant.config_entries = types.ModuleType("homeassistant.config_entries")
        homeassistant.config_entries.ConfigEntry = object
        homeassistant.core = types.ModuleType("homeassistant.core")
        homeassistant.core.HomeAssistant = object
        homeassistant.exceptions = types.ModuleType("homeassistant.exceptions")

        class EntryNotReady(Exception):
            pass

        homeassistant.exceptions.ConfigEntryNotReady = EntryNotReady
        self.EntryNotReady = EntryNotReady
        homeassistant.helpers = types.ModuleType("homeassistant.helpers")
        homeassistant.helpers.aiohttp_client = types.ModuleType(
            "homeassistant.helpers.aiohttp_client"
        )
        homeassistant.helpers.aiohttp_client.async_get_clientsession = (
            lambda hass: object()
        )
        self.patch_modules = patch.dict(sys.modules, {
            NAMESPACE: module,
            f"{NAMESPACE}.const": const,
            f"{NAMESPACE}.core_supervisor_loader": core,
            f"{NAMESPACE}.supervisor_pairing": exceptions,
            f"{NAMESPACE}.coordinator": coordinator,
            f"{NAMESPACE}.runtime_client": client,
            "homeassistant": homeassistant,
            "homeassistant.const": homeassistant.const,
            "homeassistant.config_entries": homeassistant.config_entries,
            "homeassistant.core": homeassistant.core,
            "homeassistant.exceptions": homeassistant.exceptions,
            "homeassistant.helpers": homeassistant.helpers,
            "homeassistant.helpers.aiohttp_client": homeassistant.helpers.aiohttp_client,
        })
        self.patch_modules.start()
        self.addCleanup(self.patch_modules.stop)
        spec = importlib.util.spec_from_file_location(
            NAMESPACE, ROOT / "__init__.py",
            submodule_search_locations=[str(ROOT)],
        )
        integration = importlib.util.module_from_spec(spec)
        sys.modules[NAMESPACE] = integration
        spec.loader.exec_module(integration)
        self.integration = integration

        class ConfigEntries:
            async def async_forward_entry_setups(self, entry, platforms):
                return None

        self.hass = types.SimpleNamespace(data={}, config_entries=ConfigEntries())
        self.entry = types.SimpleNamespace(
            entry_id="test-entry",
            options={},
            data={
                "device_id": "123456789012",
                "runtime_endpoint": "http://local-genvex-nabto-remote:18275/v1/snapshot",
                "pair_from_app": True,
            },
        )

    async def test_auto_paired_entry_reloads_current_token_without_persisting(self):
        self.assertTrue(await self.integration.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.tokens, ["N" * 43])
        self.latest_token = "M" * 43
        self.assertTrue(await self.integration.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.tokens, ["N" * 43, "M" * 43])
        self.assertEqual(self.lookups, ["123456789012"] * 2)
        self.assertTrue(all(callable(loader) for loader in self.token_loaders))
        self.assertEqual(await self.token_loaders[0](), "M" * 43)
        self.assertNotIn("runtime_token", self.entry.data)

    async def test_manual_token_entry_skips_supervisor_lookup(self):
        self.entry.data = {
            "device_id": "123456789012",
            "runtime_endpoint": "http://local-genvex-nabto-remote:18275/v1/snapshot",
            "runtime_token": "S" * 43,
        }
        self.assertTrue(await self.integration.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.tokens, ["S" * 43])
        self.assertEqual(self.lookups, [])
        self.assertIsNone(self.token_loaders[0])

    async def test_existing_manual_entry_can_be_migrated_by_options(self):
        self.entry.data = {
            "device_id": "123456789012",
            "runtime_endpoint": "http://local-genvex-nabto-remote:18275/v1/snapshot",
        }
        self.entry.options = {"pair_from_app": True}
        self.assertTrue(await self.integration.async_setup_entry(self.hass, self.entry))
        self.assertEqual(self.tokens, ["N" * 43])
        self.assertEqual(self.lookups, ["123456789012"])
        self.assertNotIn("runtime_token", self.entry.data)

    async def test_unavailable_auto_pair_fails_without_stale_token(self):
        self.missing = True
        with self.assertRaises(self.EntryNotReady) as caught:
            await self.integration.async_setup_entry(self.hass, self.entry)
        self.assertEqual(str(caught.exception), "Genvex Remote App pairing unavailable")
        self.assertEqual(self.tokens, [])
        self.assertNotIn("runtime_token", self.entry.data)


if __name__ == "__main__":
    unittest.main()
