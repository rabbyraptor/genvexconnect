"""No-socket tests of inert future private aiohttp IPC application factory."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

RUNTIME = Path(__file__).resolve().parents[3] / "genvex-nabto-remote" / "runtime"
sys.path.insert(0, str(RUNTIME))
from ipc_web_candidate import build_ipc_application, create_handler

from test_real_core_availability import DEVICE, make_snapshot

TOKEN = "K" * 48


def request(*, token=TOKEN, method="GET", path="/v1/snapshot",
            has_body=False, length=None):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    return SimpleNamespace(
        headers=headers, method=method, raw_path=path,
        can_read_body=has_body, content_length=length,
    )


@pytest.mark.asyncio
async def test_authenticated_complete_snapshot_and_unavailable():
    state = {"snapshot": make_snapshot()}
    calls = []
    def supplier():
        calls.append("called")
        return state["snapshot"]
    handler = create_handler(expected_token=TOKEN, device_id=DEVICE,
                             get_snapshot=supplier)
    good = await handler(request())
    assert good.status == 200
    payload = json.loads(good.body)
    assert payload["values"]["humidity"] == 66.0
    assert len(calls) == 1

    state["snapshot"] = None
    unavailable = await handler(request())
    assert unavailable.status == 503
    assert unavailable.body == b'{"error":"unavailable"}'
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_bad_token_never_reads_snapshot():
    calls = []
    def supplier():
        calls.append("called")
        return make_snapshot()
    handler = create_handler(expected_token=TOKEN, device_id=DEVICE,
                             get_snapshot=supplier)
    for bad in (None, "X" * 48, "", "short"):
        result = await handler(request(token=bad))
        assert result.status == 401
        assert result.body == b'{"error":"unauthorized"}'
    assert calls == []


@pytest.mark.asyncio
async def test_only_exact_get_without_query_or_body():
    calls = []
    def supplier():
        calls.append("called")
        return make_snapshot()
    handler = create_handler(expected_token=TOKEN, device_id=DEVICE,
                             get_snapshot=supplier)
    for method, path in (
        ("POST", "/v1/snapshot"),
        ("DELETE", "/v1/snapshot"),
        ("GET", "/v1/snapshot?debug=true"),
        ("GET", "/v1/secret"),
    ):
        result = await handler(request(method=method, path=path))
        assert result.status == 404
    for length, has_body in ((5, True), (None, True)):
        result = await handler(request(has_body=has_body, length=length))
        assert result.status == 413
    assert calls == []


@pytest.mark.asyncio
async def test_provider_failure_is_redacted_unavailable():
    def supplier():
        raise RuntimeError("secret-profile-location")
    handler = create_handler(expected_token=TOKEN, device_id=DEVICE,
                             get_snapshot=supplier)
    result = await handler(request())
    assert result.status == 503
    assert b"secret" not in result.body


def test_factory_does_not_open_any_socket_and_validates_inputs():
    app = build_ipc_application(expected_token=TOKEN, device_id=DEVICE,
                                get_snapshot=lambda: None)
    assert len(list(app.router.routes())) == 1
    assert not hasattr(app, "_runner")
    with pytest.raises(ValueError):
        create_handler(expected_token="short", device_id=DEVICE,
                       get_snapshot=lambda: None)
    with pytest.raises(ValueError):
        create_handler(expected_token=TOKEN, device_id="bad-id",
                       get_snapshot=lambda: None)
    with pytest.raises(ValueError):
        create_handler(expected_token=TOKEN, device_id=DEVICE,
                       get_snapshot=None)
