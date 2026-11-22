"""Offline contract tests for the real Core Supervisor-client adapter.

No installed Home Assistant Core, real Supervisor credentials or network.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "custom_components/genvex_remote"
PACKAGE = "offline_genvex_core_pairing"

pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE, pkg)


def load(name):
    full = f"{PACKAGE}.{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


pairing = load("supervisor_pairing")
adapter = load("core_supervisor_loader")


class FakeAddon:
    slug = "local_genvex_nabto_remote"
    state = "started"

    def __init__(self):
        self.options = {
            "device_id": "123456789012",
            "ipc_token": "T" * 43,
            "identity": "PRIVATE-IDENTITY",
            "unlock_secret": "PRIVATE-ACCOUNT-PASSWORD",
        }


class CoreSupervisorLoaderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = []
        self.addon = FakeAddon()
        self.hass = object()

        async def addon_info(slug):
            self.calls.append(slug)
            return self.addon

        hassio = types.ModuleType("homeassistant.components.hassio")
        hassio.get_supervisor_client = lambda hass: types.SimpleNamespace(
            addons=types.SimpleNamespace(addon_info=addon_info)
        ) if hass is self.hass else None
        homeassistant = types.ModuleType("homeassistant")
        components = types.ModuleType("homeassistant.components")
        homeassistant.components = components
        components.hassio = hassio
        self.modules = {
            "homeassistant": homeassistant,
            "homeassistant.components": components,
            "homeassistant.components.hassio": hassio,
        }
        self.patch_modules = patch.dict(sys.modules, self.modules)
        self.patch_modules.start()
        self.addCleanup(self.patch_modules.stop)

    async def test_reads_exact_fixed_app_and_only_returns_valid_token(self):
        token = await adapter.async_fetch_paired_token(
            self.hass, device_id="123456789012"
        )
        self.assertEqual(token, "T" * 43)
        self.assertEqual(self.calls, [pairing.APP_ID])
        self.assertNotIn("PRIVATE-ACCOUNT-PASSWORD", repr(token))

    async def test_invalid_device_and_wrong_app_fail_closed(self):
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            await adapter.async_fetch_paired_token(self.hass, device_id="wrong")
        self.assertEqual(self.calls, [])
        self.addon.slug = "some_other_app"
        with self.assertRaises(pairing.SupervisorPairingUnavailable):
            await adapter.async_fetch_paired_token(
                self.hass, device_id="123456789012"
            )

    async def test_stopped_app_redacted_token_and_mismatch(self):
        for change in ("stopped", "missing_token", "mismatch"):
            self.addon = FakeAddon()
            if change == "stopped":
                self.addon.state = "stopped"
            elif change == "missing_token":
                self.addon.options.pop("ipc_token")
            else:
                self.addon.options["device_id"] = "999999999999"
            with self.subTest(change=change), self.assertRaises(
                pairing.SupervisorPairingUnavailable
            ):
                await adapter.async_fetch_paired_token(
                    self.hass, device_id="123456789012"
                )

    async def test_transport_errors_are_sanitized(self):
        async def failing(_slug):
            raise RuntimeError("SENSITIVE_PRIVATE_OPTIONS")

        sys.modules["homeassistant.components.hassio"].get_supervisor_client = (
            lambda _hass: types.SimpleNamespace(
                addons=types.SimpleNamespace(addon_info=failing)
            )
        )
        with self.assertRaises(pairing.SupervisorPairingUnavailable) as caught:
            await adapter.async_fetch_paired_token(
                self.hass, device_id="123456789012"
            )
        self.assertEqual(str(caught.exception), "Trusted App pairing unavailable")
        self.assertNotIn("SENSITIVE_PRIVATE_OPTIONS", str(caught.exception))

    async def test_cancellation_propagates_to_caller(self):
        started = asyncio.Event()

        async def blocking(_slug):
            started.set()
            await asyncio.Event().wait()

        sys.modules["homeassistant.components.hassio"].get_supervisor_client = (
            lambda _hass: types.SimpleNamespace(
                addons=types.SimpleNamespace(addon_info=blocking)
            )
        )
        task = asyncio.create_task(
            adapter.async_fetch_paired_token(self.hass, device_id="123456789012")
        )
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    unittest.main()
