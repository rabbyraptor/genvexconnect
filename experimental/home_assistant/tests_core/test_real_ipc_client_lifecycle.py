"""Real Home Assistant Core with actual authenticated snapshot HTTP client.

No sockets are opened: the only injected component is a finite fake
aiohttp-like session, using the real integration, reader, coordinator,
sensor platform, entity registry and state machine.
"""
from __future__ import annotations

import json
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
    await hass.async_add_executor_job(copytree, COMPONENT, target)

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
