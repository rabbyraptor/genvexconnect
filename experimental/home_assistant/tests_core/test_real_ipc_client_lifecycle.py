"""Real Home Assistant Core with actual authenticated snapshot HTTP client.

No sockets are opened: the only injected component is a finite fake
aiohttp-like session, using the real integration, reader, coordinator,
sensor platform, entity registry and state machine.
"""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from shutil import copytree
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant.common import MockConfigEntry

from custom_components.genvex_remote.const import (
    DOMAIN, CONF_DEVICE_ID, CONF_RUNTIME_ENDPOINT, CONF_RUNTIME_TOKEN,
)
from custom_components.genvex_remote.runtime_client import EXPECTED_APP_ENDPOINT
from test_real_core_availability import DEVICE, make_snapshot

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
TOKEN = "Q" * 48


class FakeBody:
    def __init__(self, data):
        self.data = data
        self.limits = []

    async def read(self, size):
        self.limits.append(size)
        return self.data[:size]


class FakeResponse:
    def __init__(self, status, data):
        self.status = status
        self.content = FakeBody(data)
        self.content_length = len(data)


class FakeContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *exc):
        return None


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, headers, allow_redirects=True):
        self.calls.append((url, dict(headers), allow_redirects))
        return FakeContext(self.responses.pop(0))


def response(snapshot, *, status=200):
    return FakeResponse(status, json.dumps(snapshot).encode("utf-8"))


@pytest.mark.asyncio
async def test_actual_authenticated_ipc_client_config_entry_lifecycle(hass, enable_custom_integrations):
    """One authorized read, one 401, then recovery using real Core entities."""
    target = Path(hass.config.path("custom_components", DOMAIN))
    await hass.async_add_executor_job(
        partial(copytree, COMPONENT, target, dirs_exist_ok=True)
    )

    # All responses are local Python objects. No real HTTP request occurs.
    session = FakeSession([
        response(make_snapshot()),
        FakeResponse(401, b"private-401-response"),
        response(make_snapshot(humidity=68)),
    ])
    entry = MockConfigEntry(
        domain=DOMAIN, title="Genvex Remote test", unique_id=DEVICE,
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

        entities = er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        assert len(entities) == 5
        entity_ids = [e.entity_id for e in entities]
        assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE
                   for entity_id in entity_ids)

        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id).state == STATE_UNAVAILABLE
                   for entity_id in entity_ids)
        assert all("private-401-response" not in str(hass.states.get(entity_id))
                   for entity_id in entity_ids)
        assert all(TOKEN not in str(hass.states.get(entity_id))
                   for entity_id in entity_ids)

        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id).state != STATE_UNAVAILABLE
                   for entity_id in entity_ids)

        assert len(session.calls) == 3
        for url, headers, allow_redirects in session.calls:
            assert url == EXPECTED_APP_ENDPOINT
            assert headers == {
                "Authorization": "Bearer " + TOKEN,
                "Accept": "application/json",
            }
            assert allow_redirects is False
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.entry_id not in hass.data.get(DOMAIN, {})

@pytest.mark.asyncio
async def test_real_runtime_handler_to_core_entities_without_sockets(hass, enable_custom_integrations):
    """Exercise both *real* IPC contract endpoints as an in-memory transport."""
    import sys
    runtime = Path(__file__).resolve().parents[3] / "genvex-nabto-remote" / "runtime"
    sys.path.insert(0, str(runtime))
    from snapshot_api import handle_read_request

    target = Path(hass.config.path("custom_components", DOMAIN))
    await hass.async_add_executor_job(
        partial(copytree, COMPONENT, target, dirs_exist_ok=True)
    )

    class LoopbackSession:
        def __init__(self):
            self.snapshot = make_snapshot()
            self.expected_token = TOKEN
            self.calls = []

        def get(self, url, *, headers, allow_redirects=True):
            self.calls.append((url, allow_redirects))
            status, data = handle_read_request(
                method="GET",
                path="/v1/snapshot",
                authorization=headers.get("Authorization"),
                expected_token=self.expected_token,
                device_id=DEVICE,
                snapshot=self.snapshot,
            )
            return FakeContext(FakeResponse(status, data))

    session = LoopbackSession()
    entry = MockConfigEntry(
        domain=DOMAIN, title="Genvex Remote loopback", unique_id=DEVICE,
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
        entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        assert len(entities) == 5
        ids = [item.entity_id for item in entities]
        assert all(hass.states.get(eid).state != STATE_UNAVAILABLE for eid in ids)

        coordinator = hass.data[DOMAIN][entry.entry_id]
        # A missing SDK snapshot is projected to HTTP 503 by the real handler.
        session.snapshot = None
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(eid).state == STATE_UNAVAILABLE for eid in ids)

        # Fail closed when the server's expected IPC token is different.
        session.expected_token = "X" * 48
        session.snapshot = make_snapshot()
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(eid).state == STATE_UNAVAILABLE for eid in ids)

        # The valid 5-value result may become visible after authentication
        # and the backend snapshot both recover.
        session.expected_token = TOKEN
        session.snapshot = make_snapshot(humidity=69)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert all(hass.states.get(eid).state != STATE_UNAVAILABLE for eid in ids)
        assert all(url == EXPECTED_APP_ENDPOINT and redirects is False
                   for url, redirects in session.calls)
        assert len(session.calls) == 4

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.entry_id not in hass.data.get(DOMAIN, {})
