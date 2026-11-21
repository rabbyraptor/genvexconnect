"""Real TCP transport -> real Home Assistant Core config entry and five entities.

Runs ONLY in the isolated GitHub Actions pytest harness. All measurements
and authentication tokens are synthetic. The production reader endpoint stays
strictly pinned to the Supervisor App name; the test-only aiohttp DNS resolver
maps that single hostname:port to an ephemeral IPv4 loopback listener.
No Nabto connection, HAOS installation, App startup or polling is involved.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path
from shutil import copytree
import socket
import sys
from unittest.mock import patch

from aiohttp import ClientSession, TCPConnector
from aiohttp.abc import AbstractResolver
import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.genvex_remote.const import (
    CONF_DEVICE_ID, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN, DOMAIN, SENSORS,
)
from custom_components.genvex_remote.runtime_client import EXPECTED_APP_ENDPOINT
from test_real_core_availability import DEVICE, make_snapshot

RUNTIME = Path(__file__).resolve().parents[3] / "genvex-nabto-remote" / "runtime"
sys.path.insert(0, str(RUNTIME))
from polling_http_server import SnapshotHTTPServer

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
TOKEN = "R" * 48
HOST = "local-genvex-nabto-remote"
PORT = 18275


class PinnedLoopbackResolver(AbstractResolver):
    """Only the exact production DNS name may be redirected in this test."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.resolved: list[tuple[str, int]] = []

    async def resolve(self, host, port=0, family=socket.AF_INET):
        if (host, port) != (HOST, PORT):
            raise OSError("Unexpected DNS lookup in isolated test")
        self.resolved.append((host, port))
        return [{
            "hostname": host,
            "host": "127.0.0.1",
            "port": self.port,
            "family": socket.AF_INET,
            "proto": 0,
            "flags": socket.AI_NUMERICHOST,
        }]

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_real_tcp_snapshot_to_registered_core_entities(
    hass, enable_custom_integrations, socket_enabled,
):
    """Use real aiohttp, real HTTP server and the actual HA entry lifecycle."""
    target = Path(hass.config.path("custom_components", DOMAIN))
    await hass.async_add_executor_job(
        partial(copytree, COMPONENT, target, dirs_exist_ok=True)
    )

    state = {"snapshot": make_snapshot(), "provider_calls": 0}

    def snapshot_provider():
        state["provider_calls"] += 1
        return state["snapshot"]

    # The production server and handler are used unchanged. Loopback binding
    # and an ephemeral port prevent exposure of this synthetic CI fixture.
    server = SnapshotHTTPServer(
        bind_host="127.0.0.1", port=0, token=TOKEN,
        device_id=DEVICE, snapshot_provider=snapshot_provider,
    )
    loopback_port = server._server.server_address[1]
    resolver = PinnedLoopbackResolver(loopback_port)
    server.start()
    try:
        connector = TCPConnector(
            resolver=resolver, use_dns_cache=False, force_close=True,
        )
        async with ClientSession(connector=connector, trust_env=False) as session:
            entry = MockConfigEntry(
                domain=DOMAIN,
                title="Genvex Remote real TCP CI",
                unique_id=DEVICE,
                data={
                    CONF_DEVICE_ID: DEVICE,
                    CONF_RUNTIME_ENDPOINT: EXPECTED_APP_ENDPOINT,
                    CONF_RUNTIME_TOKEN: TOKEN,
                },
            )
            entry.add_to_hass(hass)

            with patch(
                "custom_components.genvex_remote.async_get_clientsession",
                return_value=session,
            ):
                assert await hass.config_entries.async_setup(entry.entry_id)
                await hass.async_block_till_done()

                entries = er.async_entries_for_config_entry(
                    er.async_get(hass), entry.entry_id
                )
                assert len(entries) == len(SENSORS) == 5
                entity_ids = [item.entity_id for item in entries]
                devices = dr.async_entries_for_config_entry(
                    dr.async_get(hass), entry.entry_id
                )
                assert len(devices) == 1
                assert (DOMAIN, DEVICE) in devices[0].identifiers
                assert all(item.device_id == devices[0].id for item in entries)
                assert all(
                    hass.states.get(eid).state != STATE_UNAVAILABLE
                    for eid in entity_ids
                )
                assert state["provider_calls"] == 1

                coordinator = hass.data[DOMAIN][entry.entry_id]
                assert coordinator.data["humidity"] == 66.0

                # A real HTTP 503 invalidates all five readings.
                state["snapshot"] = None
                await coordinator.async_refresh()
                await hass.async_block_till_done()
                assert not coordinator.last_update_success
                assert all(
                    hass.states.get(eid).state == STATE_UNAVAILABLE
                    for eid in entity_ids
                )
                assert state["provider_calls"] == 2

                # Wrong bearer must fail before consulting snapshot state.
                state["snapshot"] = make_snapshot(humidity=70.0)
                coordinator.reader._token = "X" * 48
                await coordinator.async_refresh()
                await hass.async_block_till_done()
                assert not coordinator.last_update_success
                assert state["provider_calls"] == 2
                assert all(
                    hass.states.get(eid).state == STATE_UNAVAILABLE
                    for eid in entity_ids
                )
                assert all(TOKEN not in str(hass.states.get(eid))
                           for eid in entity_ids)

                # After restoring authentication, one fresh TCP response
                # makes the same five registered entities available again.
                coordinator.reader._token = TOKEN
                state["snapshot"] = make_snapshot(humidity=71.0)
                await coordinator.async_refresh()
                await hass.async_block_till_done()
                assert coordinator.last_update_success
                assert coordinator.data["humidity"] == 71.0
                assert state["provider_calls"] == 3
                assert all(
                    hass.states.get(eid).state != STATE_UNAVAILABLE
                    for eid in entity_ids
                )
                assert len(resolver.resolved) == 4
                assert all(value == (HOST, PORT) for value in resolver.resolved)

                assert await hass.config_entries.async_unload(entry.entry_id)
                await hass.async_block_till_done()
                assert entry.entry_id not in hass.data.get(DOMAIN, {})
    finally:
        server.stop()
