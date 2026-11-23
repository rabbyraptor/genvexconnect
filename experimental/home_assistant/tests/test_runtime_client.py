"""Fake aiohttp contract tests for the HA consumer, without HA imports."""
import asyncio
import json
import unittest

# Reuse the independent package loader in test_snapshot.py.
from test_snapshot import RuntimeUnavailable
from dev_remote.runtime_client import AuthenticatedSnapshotReader, SNAPSHOT_REQUEST_TIMEOUT_SECONDS


class _BodyStream:
    def __init__(self, body):
        self.body = body
        self.read_limits = []

    async def read(self, limit):
        self.read_limits.append(limit)
        return self.body[:limit]


class _Response:
    def __init__(self, status=200, body=b"{}", content_length=None):
        self.status = status
        self.content = _BodyStream(body)
        self.content_length = content_length


class _Context:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_):
        return None


class _Session:
    def __init__(self, response):
        self.response = response
        self.headers = None
        self.url = None
        self.allow_redirects = None

    def get(self, url, *, headers, allow_redirects=True):
        self.url = url
        self.headers = headers
        self.allow_redirects = allow_redirects
        return _Context(self.response)


class AuthenticatedReaderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.token = "z" * 43
        self.endpoint = "http://local-genvex-nabto-remote:18275/v1/snapshot"

    def reader(self, response):
        session = _Session(response)
        return AuthenticatedSnapshotReader(
            session, endpoint=self.endpoint, token=self.token,
        ), session

    def test_timeout_budget_covers_measured_cold_start(self):
        # DEV3 first live SDK read took 10.504s; avoid an 8s cold-start failure.
        self.assertGreater(SNAPSHOT_REQUEST_TIMEOUT_SECONDS, 10.504)
        self.assertLessEqual(SNAPSHOT_REQUEST_TIMEOUT_SECONDS, 30)

    async def test_authorized_get(self):
        body = json.dumps({"schema_version": 1}).encode()
        reader, session = self.reader(_Response(body=body))
        result = await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(result, {"schema_version": 1})
        self.assertEqual(session.headers["Authorization"], "Bearer " + self.token)
        self.assertEqual(session.url, self.endpoint)
        self.assertIs(session.allow_redirects, False)
        self.assertEqual(session.response.content.read_limits, [4097])

    async def test_error_status_is_redacted(self):
        reader, _ = self.reader(_Response(status=401, body=b"SECRET"))
        with self.assertRaises(RuntimeUnavailable) as ctx:
            await reader.async_fetch_snapshot("123456789012")
        self.assertNotIn("SECRET", str(ctx.exception))
        self.assertNotIn(self.token, str(ctx.exception))

    async def test_oversize_rejected(self):
        reader, _ = self.reader(_Response(body=b"x" * 4097))
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")

    async def test_non_object_rejected(self):
        reader, _ = self.reader(_Response(body=b"[]"))
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")

    async def test_large_declared_content_length_rejected_before_read(self):
        reader, session = self.reader(_Response(body=b"{}", content_length=5000))
        with self.assertRaises(RuntimeUnavailable):
            await reader.async_fetch_snapshot("123456789012")
        self.assertEqual(session.response.content.read_limits, [])

    async def test_bad_endpoint_rejected(self):
        for bad in (
            "https://example.com/api",
            "http://127.0.0.1:18275/v1/enroll",
            "http://example.com:18275/v1/snapshot?token=sensitive",
            "http://user:password@example.com:18275/v1/snapshot",
            "http://example.com/v1/snapshot",
            "http://app_local_other_app:18275/v1/snapshot",
            "http://127.0.0.1:18275/v1/snapshot",
            "http://10.0.0.5:18275/v1/snapshot",
            "http://app_local_genvex_nabto_remote.evil.example:18275/v1/snapshot",
            "http://app_local_genvex_nabto_remote:18275/v1/snapshot#fragment",
            "http://APP_LOCAL_GENVEX_NABTO_REMOTE:18275/v1/snapshot",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    AuthenticatedSnapshotReader(_Session(_Response()), endpoint=bad, token=self.token)


if __name__ == "__main__":
    unittest.main()
