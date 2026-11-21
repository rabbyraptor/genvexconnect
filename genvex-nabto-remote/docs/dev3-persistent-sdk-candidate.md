# DEV3 persistent Micro Nabto worker — offline candidate

The operator's live A+B.4 trial showed one legacy Nabto session returning
success, SDK status 26, then two more successful RPC45 reads without
`nabtoOpenSession()` or SDK restart. That supports an opt-in persistent
session prototype; it does not prove the cause of SDK status 26.

## New source modules

- `runtime/persistent_rpc45_worker.py`: x86_64/QEMU SDK process with
  private JSON configuration on its first stdin line and exact `POLL`
  / `CLOSE` commands thereafter. One startup, certificate/profile setup,
  session open, XML interface registration and final close/shutdown.
  Each successful RPC45 returns one complete five-sensor JSON snapshot;
  failures return only bounded numeric SDK status and elapsed time.
- `runtime/persistent_sdk_adapter.py`: parent async single-flight client.
  Credentials enter child stdin, never argv/environment/logs. Results are
  checked against `snapshot_contract.parse_snapshot` before publication.
  Polling and worker lifecycle remain explicit; nothing starts on import.

## Recovery contract

1. Successful reads clear the consecutive-RPC-error counter.
2. First RPC error (including status 26): mark the poll unavailable,
   preserve the worker and Nabto session; **no immediate retry**.
3. Second consecutive RPC error: mark unavailable, terminate and reap
   worker. The **next scheduled poll** may start a fresh session.
4. Timeout, cancellation, malformed IPC frame, invalid snapshot or
   worker startup error: terminate/reap immediately.
5. `aclose()` attempts a bounded graceful shutdown and then force-kills
   if necessary. No parallel RPC45 calls or catch-up bursts.

## SDK-free automated verification

Run from `genvex-nabto-remote`:

```sh
python3 -m unittest discover -s tests -p 'test_dev3_persistent_adapter.py' -v
```

Tests exercise actual local child-process communication and a fake ctypes
SDK. Scenarios include RPC26 recovery without reopening, fail-closed
`SnapshotState` transitions, two-error recycle, serialization, timeout,
cancellation, oversized response, mismatched device ID, failed startup,
graceful close and one session lifecycle in the fake native SDK.

**Status:** New code is not connected to `polling_runtime.py`, the
installed HAOS App, its Supervisor configuration, or Home Assistant Core.
Real QEMU/native SDK operation of this new worker is not yet verified.
Previously observed 27/31 successful snapshots in the 30-minute DEV3
Gate H remain the baseline, not a direct comparison with this prototype.

## Next verification

Run a bounded operator-controlled live test of this **new worker and
parent adapter**, without modifying the installed polling code. Record
the worker PID, serial statuses, timings, session-reuse decisions and
resource cleanup. Existing polling still runs concurrently, so results
cannot yet establish comparative reliability. For an unbiased comparison,
run separate mutually exclusive polling windows later.
