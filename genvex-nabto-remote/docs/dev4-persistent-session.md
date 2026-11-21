# DEV4 persistent Micro Nabto polling — opt-in candidate

Source branch: `feature/dev4-persistent-session`, distinct from the
installed DEV3 App and its working Home Assistant Core integration.

## Why

DEV3 Gate H observed 27/31 complete snapshots in 30 minutes and four
HTTP 503 responses. The P.1 native QEMU SDK trial of the new persistent
adapter reported five successful RPC45 batches out of six, with one
status-26 failure at RPC #3 and successful in-session recovery at RPC #4.
One worker remained in use, and shutdown reaped it. DEV3 normal
polling ran simultaneously; these rates are **not comparable**.

## DEV4 App configuration

- Bumped source candidate version to `0.1.0-dev4` so the Supervisor App
  upgrade can be explicitly staged later.
- Adds a strict boolean `persistent_session` App option, default **false**.
- False or absent: existing `SDKSnapshotAdapter` (new child/session each
  poll), identical to DEV3 behavior.
- True: `PersistentSDKSnapshotAdapter` with one QEMU SDK process/Nabto
  session across serial polling cycles, same five RPC45 addresses and
  snapshot API.
- Normal shutdown now awaits persistent adapter `aclose()`, including
  worker shutdown after poller stop. Diagnostic-only mode cannot enable
  persistent sessions.
- App remains private-network-only, manual boot; existing token, endpoint,
  sensor keys, and Home Assistant entity IDs do not need changes.

## Recovery policy

An RPC45 error makes that cycle unavailable via `SnapshotState`.
After the first such error, retain the session for the next normally
scheduled poll. After two consecutive RPC errors, gracefully close
and reap the worker so the next poll opens a new session. Other
invalid data, protocol errors, timeout and cancellation cause immediate
worker termination. No automatic rapid retries.

## Offline gates

- `test_dev3_persistent_adapter.py`: actual fake local subprocess
  protocol, fake ctypes SDK, post-status-26 recovery, two-error
  recycle, cancellation, timeout, invalid frames, wrong device, cleanup.
- `test_dev4_mode_switch.py`: old config compatibility, strict opt-in,
  default/false/true mode choice and deterministic shutdown cleanup.
- `test_app_bootstrap.py`: strict bool and mutual exclusion with
  diagnostic-only mode.
- CI builds an ARM64 `0.1.0-dev4` image from the entire runtime
  and checks no exposed host ports.
- These gates exercise no live Nabto gateway.

## Live validation still required

The checked-in code is an **App candidate**, not installed on HAOS.
Next perform read-only host preflight of installed App and available
rollback path, then an operator-approved DEV4 App upgrade with
`persistent_session=false` to verify identical baseline behavior.
Only then switch the App option to `true` and validate five live
sensors, stable entity IDs and startup/stop recovery. Compare
mutually exclusive 30-minute one-shot and persistent windows;
record HTTP status, snapshot freshness, resource use, process identity,
RPC failures and recovery. Do not treat the parallel P.1 trial as
evidence of reduced production failure rates.
