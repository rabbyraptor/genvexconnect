"""Proof that an RPC45 batch becomes an authenticated five-value snapshot.

Offline only: fake RPC reader, no Nabto SDK, no socket, no real credentials.
"""
import unittest

from ipc_auth import new_ipc_token
from polling_worker import ReadOnlyPoller
from snapshot_api import handle_read_request
from snapshot_state import SnapshotState
from snapshot_contract import parse_snapshot
import json


class WorkerToAPIContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_rpc_to_authorized_api_to_validated_ha_snapshot(self):
        calls = []
        async def fake_rpc(hostname, addresses):
            calls.append(addresses)
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(
            device_id="123456789012", reader=fake_rpc,
        ))
        self.assertTrue(await state.refresh())
        token = new_ipc_token()
        code, response = handle_read_request(
            method="GET", path="/v1/snapshot",
            authorization="Bearer " + token,
            expected_token=token,
            device_id="123456789012",
            snapshot=state.current(),
        )
        self.assertEqual(code, 200)
        parsed = parse_snapshot(json.loads(response), expected_device_id="123456789012")
        self.assertEqual(parsed["supply_air"], 6.7)
        self.assertEqual(parsed["outdoor_air"], -0.1)
        self.assertEqual(parsed["humidity"], 65.0)
        self.assertEqual(calls, [(20, 21, 22, 23, 26)])

    async def test_failed_subsequent_rpc_forces_503_not_cached_200(self):
        count = 0
        async def fake_rpc(_host, _addresses):
            nonlocal count
            count += 1
            if count > 1:
                raise OSError("private error / fake secret")
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(
            device_id="123456789012", reader=fake_rpc,
        ))
        token = new_ipc_token()

        def fetch():
            return handle_read_request(
                method="GET", path="/v1/snapshot",
                authorization="Bearer " + token, expected_token=token,
                device_id="123456789012", snapshot=state.current(),
            )

        self.assertTrue(await state.refresh())
        self.assertEqual(fetch()[0], 200)
        self.assertFalse(await state.refresh())
        status, body = fetch()
        self.assertEqual(status, 503)
        self.assertNotIn(b"secret", body)
        self.assertNotIn(b"supply_air", body)

    async def test_no_snapshot_before_first_poll(self):
        async def fake_rpc(_host, _addresses):
            return [367, 299, 315, 377, 65]
        state = SnapshotState(ReadOnlyPoller(
            device_id="123456789012", reader=fake_rpc,
        ))
        token = new_ipc_token()
        code, _ = handle_read_request(
            method="GET", path="/v1/snapshot",
            authorization="Bearer " + token, expected_token=token,
            device_id="123456789012", snapshot=state.current(),
        )
        self.assertEqual(code, 503)


if __name__ == "__main__":
    unittest.main()
