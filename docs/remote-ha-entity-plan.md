# Remote Genvex → Home Assistant: first five read-only sensors

**Status: sensor model scaffold committed; NOT YET a working Home Assistant integration and NOT deployed.**

## Verified on 2026-11-19: two HAOS/QEMU stability checks

Both runs on the user's HAOS Raspberry Pi through the *existing isolated* v0.4.0 runtime returned SDK startup/resources/profile/XML/RPC status 0, decoded **5/5**, closed the session and shut down SDK with status 0. A fresh Nabto session was opened for each batch, 15 seconds apart. Observed RPC durations: **1,200 ms** and **1,260 ms**. Readings were identical in those runs:

| RPC 45 obj=0 address | Sensor | Raw | Decoded |
| ---: | --- | ---: | ---: |
| 20 | Supply air | 365 | 6.50 °C |
| 21 | Outdoor air | 301 | 0.10 °C |
| 22 | Exhaust air | 315 | 1.50 °C |
| 23 | Extract air | 376 | 7.60 °C |
| 26 | Humidity | 66 | 66 % |

This is a short repeatability smoke test, **not** proof of week-long uptime or automatic reconnect behavior. No setpoint writes were tested.

## Scaffold committed

[`experimental/genvex_remote/sensor_model.py`](../experimental/genvex_remote/sensor_model.py) defines the five supported sensors, decimal device-ID → Nabto hostname conversion, temperature transformation `(raw - 300)/10`, humidity conversion, strict signed-int16 validation and fail-whole-batch behavior. It contains **no Nabto SDK binary and no private credentials**.

[`experimental/genvex_remote/test_sensor_model.py`](../experimental/genvex_remote/test_sensor_model.py) tests the verified batch, address order, device-ID validation, malformed and incomplete responses offline. This model is intentionally staged **outside** `custom_components/genvex_connect`, so installing or updating the existing local integration cannot be affected.

## Remaining bridge (must be implemented before live HA entities)

Build a private, well-defined **HAOS runtime → Home Assistant data bridge**. The current v0.4.0 app exposes a one-shot manual RPC script, not a polling service, shared state/API or Home Assistant Config Entry. No false live-data dashboard shortcut.

Recommended architecture:

1. A confined, read-only Nabto worker inside the separate runtime app, using the existing encrypted client certificate and a secret injection strategy that survives HAOS restarts without logging the passphrase. No credentials in the public repository, URL, command line, entity attributes or debug output.
2. One worker poll per ~60 seconds (serial, never overlap), bounded call timeout, backoff on failure and last-success timestamp. Produce an atomic **five-value** snapshot with schema/version, device ID, timestamp, and valid decoded readings, with no credentials. An internal endpoint or controlled shared file may be used; the exact mechanism must be reviewed for HAOS permission/isolation, concurrency and HA process access.
3. A *separate* `genvex_remote` HA integration, with config flow for the 12-digit device ID, async DataUpdateCoordinator reading the worker snapshot, five sensor entities with stable unique IDs, temperature/humidity device classes, measurement state classes and units. On stale/failed reads, mark all five **unavailable** instead of retaining misleading 'live' values.
4. Isolation: do **not** modify `custom_components/genvex_connect` or its `genvexnabto==1.5.4` dependency, and do not expose climate/switch/number/write controls in v1.

## Engineering gates before installation

- Verify transport bridge in isolation: permissions, schema, heartbeat, malformed payload, stale timestamp, worker crash/restart, QEMU hard timeout and credential cleanup.
- Test update coordinator concurrency, entity availability and restart behavior using mocks.
- Review redistribution/legal constraints for legacy Nabto SDK; don't commit binaries, key or cert.
- Only then install `genvex_remote` as a second integration and add its sensors to a Lovelace dashboard.

**Success criterion:** five actual, auto-refreshing sensor entities with no dependency on Steam Deck or manual SSH, even though the proprietary SDK is still emulated through QEMU.
