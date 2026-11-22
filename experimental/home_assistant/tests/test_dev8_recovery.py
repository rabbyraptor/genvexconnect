"""DEV8.1 offline regression gate: recovery without HA Core or live credentials."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

# The existing loader exposes actual component modules without importing HA.
from test_snapshot import RuntimeUnavailable
from dev_remote import runtime_client
from dev_remote.runtime_client import AuthenticatedSnapshotReader, EXPECTED_APP_ENDPOINT

OLD = "A" * 43
NEW = "B" * 43
NEXT = "C" * 43


class _Body:
    def __init__(self, payload):
        self.payload = payload

    async def read(self, limit):
        return self.payload[:limit]


class _Response:
    def __init__(self, status):
        self.status = status
        self.content_length = None
        self.content = _Body(
            json.dumps({"source": "live"}).encode() if status == 200
            else b"PRIVATE_SERVER_BODY"
        )


class _Context:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        # Allow simultaneous requests to observe the old token before any
        # refresh lock is acquired.
        await asyncio.sleep(0)
        return _Response(self.status)

    async def __aexit__(self, *_args):
        return None


class _Session:
    def __init__(self, accepted_token=OLD, *, reject_status=401, down=False):
        self.accepted_token = accepted_token
        self.reject_status = reject_status
        self.down = down
        self.calls = []

    def get(self, url, *, headers, allow_redirects):
        assert url == EXPECTED_APP_ENDPOINT
        assert allow_redirects is False
        token = headers["Authorization"].removeprefix("Bearer ")
        self.calls.append(token)
        status = (
            503 if self.down
            else 200 if token == self.accepted_token
            else self.reject_status
        )
        return _Context(status)


class TokenRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = _Session(NEW)
        self.lookups = 0

        async def load():
            self.lookups += 1
            return NEW

        self.load = load

    def reader(self, *, loader=True, token=OLD):
        return AuthenticatedSnapshotReader(
            self.session, endpoint=EXPECTED_APP_ENDPOINT, token=token,
            token_loader=self.load if loader else None,
        )

    async def test_rotated_token_is_fetched_and_retried_once(self):
        reader = self.reader()
        self.assertEqual(await reader.async_fetch_snapshot("123456789012"),
                         {"source": "live"})
        self.assertEqual(self.session.calls, [OLD, NEW])
        self.assertEqual(self.lookups, 1)
        self.assertEqual(reader._token, NEW)
        self.assertEqual(await reader.async_fetch_snapshot("123456789012"),
                         {"source": "live"})
        self.assertEqual(self.session.calls, [OLD, NEW, NEW])
        self.assertEqual(self.lookups, 1)

    async def test_403_also_triggers_one_refresh(self):
        self.session.reject_status = 403
        result = await self.reader().async_fetch_snapshot("123456789012")
        self.assertEqual(result, {"source": "live"})
        self.assertEqual(self.session.calls, [OLD, NEW])

    async def test_manual_token_never_calls_supervisor(self):
        with self.assertRaises(RuntimeUnavailable):
            await self.reader(loader=False).async_fetch_snapshot("123456789012")
        self.assertEqual(self.lookups, 0)
        self.assertEqual(self.session.calls, [OLD])

    async def test_503_outage_never_calls_supervisor(self):
        self.session.down = True
        with self.assertRaises(RuntimeUnavailable):
            await self.reader().async_fetch_snapshot("123456789012")
        self.assertEqual(self.session.calls, [OLD])
        self.assertEqual(self.lookups, 0)

    async def test_authorized_snapshot_never_calls_supervisor(self):
        self.session.accepted_token = OLD
        self.assertEqual(await self.reader().async_fetch_snapshot("123456789012"),
                         {"source": "live"})
        self.assertEqual(self.lookups, 0)

    async def test_unchanged_supervisor_token_does_not_retry(self):
        async def unchanged():
            self.lookups += 1
            return OLD

        self.load = unchanged
        reader = self.reader()
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(self.lookups, 1)
        self.assertEqual(self.session.calls, [OLD])
        self.assertEqual(reader._token, OLD)

    async def test_invalid_replacement_is_rejected_without_request(self):
        for replacement in ("short", NEW + "\r\n", NEW + "\x00"):
            with self.subTest(replacement=repr(replacement)):
                self.session.calls.clear()

                async def invalid():
                    return replacement

                self.load = invalid
                reader = self.reader()
                with self.assertRaises(RuntimeUnavailable):
                    await reader.async_fetch_snapshot("123456789012")
                self.assertEqual(self.session.calls, [OLD])
                self.assertEqual(reader._token, OLD)

    async def test_supervisor_error_is_redacted(self):
        async def error():
            raise RuntimeError("PRIVATE_SUPERVISOR_SECRET")

        self.load = error
        reader = self.reader()
        with self.assertRaises(RuntimeUnavailable) as caught:
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(str(caught.exception), "Runtime snapshot unavailable")
        self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertEqual(reader._token, OLD)

    async def test_second_unauthorized_response_does_not_loop(self):
        self.session.accepted_token = NEXT
        reader = self.reader()
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(self.session.calls, [OLD, NEW])
        self.assertEqual(self.lookups, 1)

    async def test_concurrent_401_responses_share_one_supervisor_lookup(self):
        reader = self.reader()
        results = await asyncio.gather(
            reader.async_fetch_snapshot("123456789012"),
            reader.async_fetch_snapshot("123456789012"),
            reader.async_fetch_snapshot("123456789012"),
        )
        self.assertEqual(results, [{"source": "live"}] * 3)
        self.assertEqual(self.lookups, 1)
        self.assertEqual(self.session.calls.count(OLD), 3)
        self.assertEqual(self.session.calls.count(NEW), 3)

    async def test_app_restart_recovers_without_token_rotation(self):
        self.session.accepted_token = OLD
        self.session.down = True
        reader = self.reader()
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(self.lookups, 0)
        self.session.down = False
        self.assertEqual(await reader.async_fetch_snapshot("123456789012"),
                         {"source": "live"})
        self.assertEqual(self.lookups, 0)
        self.assertEqual(self.session.calls, [OLD, OLD])

    async def test_app_restart_then_token_rotation_recovers_next_poll(self):
        self.session.down = True
        reader = self.reader()
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(self.lookups, 0)
        self.session.down = False
        self.assertEqual(await reader.async_fetch_snapshot("123456789012"),
                         {"source": "live"})
        self.assertEqual(self.session.calls, [OLD, OLD, NEW])
        self.assertEqual(self.lookups, 1)

    async def test_cancellation_of_supervisor_lookup_propagates(self):
        started = asyncio.Event()

        async def blocking():
            started.set()
            await asyncio.Event().wait()

        self.load = blocking
        reader = self.reader()
        task = asyncio.create_task(reader.async_fetch_snapshot("123456789012"))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(reader._token, OLD)

    async def test_hung_supervisor_lookup_is_bounded(self):
        async def blocking():
            await asyncio.Event().wait()

        self.load = blocking
        reader = self.reader()
        with patch.object(runtime_client, "TOKEN_REFRESH_TIMEOUT_SECONDS", 0.02):
            with self.assertRaises(RuntimeUnavailable):
                await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(reader._token, OLD)

    def test_token_shape_checked_at_initialization(self):
        with self.assertRaises(ValueError):
            self.reader(token=OLD + "\r\n")


if __name__ == "__main__":
    unittest.main()
