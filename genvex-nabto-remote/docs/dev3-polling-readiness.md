# DEV3 polling and Home Assistant availability review

Status: **source-only, not deployed**. Keep the existing LAN integration
untouched; the installed Genvex Remote DEV2 App remains stopped.

## Confirmed live transport and mapping

One isolated HAOS/QEMU Nabto Micro RPC45 batch returned a valid five-value
snapshot. The operator compared it with the official Genvex Connect application:
four temperatures differed by 0.1-0.2 °C and humidity agreed exactly.
This corroborates the five known addresses (20/21/22/23/26) and conversions,
but one matching batch does not establish reliability under periodic load.

## Proposed runtime behavior

The existing runtime already implements serial, read-only polls, a 60..3600
second App configuration interval, a snapshot API requiring bearer auth, and
an 85-second single-read SDK timeout. It does not run until separately enabled.

The DEV3 snapshot-state change strengthens this contract:

- A successful five-value batch is projected into an owned, validated copy.
  Mutating the SDK's returned object after validation cannot change published
  readings.
- During an in-flight poll, the last known good result may remain available
  **only while its age is at most 180 seconds**. This avoids an unnecessary
  unavailable blip during normal slow reads.
- A failed read invalidates the entire five-value batch immediately; no
  partial readings or lingering old-success state.
- Cancellation or explicit stop invalidates the snapshot.
- A completed successful read replaces the old values atomically. Later
  successes may recover all five sensors.
- PollingService performs one read at a time and waits its configured interval
  after each completed attempt. No catch-up burst or concurrent RPC calls.

The Home Assistant `GenvexRemoteCoordinator` fetches one authenticated
snapshot every 60 seconds, rejects stale, invalid or wrong-device snapshots
and raises `UpdateFailed` for expected fetch/validation failures.
`CoordinatorEntity` then supplies the standard HA unavailable behavior.
The existing HA integration is a **scaffold**, not a verified installation.

## Offline regression tests

```sh
# From genvex-nabto-remote/
python3 -m compileall -q runtime ../experimental/home_assistant/custom_components/genvex_remote
python3 -m unittest discover -s tests -p 'test_*live_once*.py' -v
python3 -m unittest discover -s tests -p 'test_dev3_polling_state.py' -v
python3 -m unittest discover -s ../experimental/home_assistant/tests -p 'test_dev3_coordinator.py' -v
```

The new state tests cover copies, failure invalidation, recovery, stale expiry,
concurrent refresh serialization, in-flight values, cancellation and shutdown.
The HA coordinator tests use minimal API stubs and do **not** prove behavior
inside an installed HA Core version. Neither suite talks to the gateway.

## Gates before enabling a live polling service

1. Offline regression tests pass.
2. Review the bearer-token provisioning and private App DNS channel on HAOS,
   without exposing credentials in command lines, public ports or logs.
3. Build a separate DEV3 App image; keep DEV2 stopped/manual and preserve LAN.
4. Stage a strictly bounded, operator-approved multi-poll trial (few attempts,
   no writes); capture success/failure timing without credentials.
5. Confirm HA coordinator failures mark the five entities unavailable on
   a supported Home Assistant version, and recovery restores all five.
6. Only then consider persistent App startup and automatic restart policy.

No production installation or unattended periodic polling is authorized by
this branch.
