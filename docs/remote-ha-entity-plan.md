# Remote Genvex → Home Assistant: first five read-only sensors

**Status: isolated development-only Home Assistant integration scaffold and read-only polling worker committed. NOT deployed; authenticated App-to-Core transport and automatic CA enrollment remain incomplete.**

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

## Phase A certificate enrollment progress

An **offline-only** [legacy CA enrollment prototype](../experimental/genvex_remote/enrollment_core.py) plus [fake CA tests](../experimental/genvex_remote/test_enrollment_core.py) now implement candidate RSA-1024 CSR and encrypted key generation, observed CA result parsing, key/certificate match and expiration checks. It does **not** make HTTP requests, verify the actual legacy Nabto trust chain, persist secrets, create UI, or enroll a real device. Its encrypted key format still needs SDK 4.9.11 compatibility testing, and full secure rotation is unimplemented. Six initial offline prototype tests passed locally. Subsequent key-format/pinned-CA work adds [SDK-compatible PBES2 encoder](../experimental/genvex_remote/sdk_compat.py), [explicit CA signature verification](../experimental/genvex_remote/certificate_trust.py), and 13 passing additional offline tests. Neither actual legacy CA trust-anchor pinning nor a newly enrolled SDK session has been validated; read the [UI onboarding design](remote-ha-ui-onboarding-architecture.md) before any live enabling.

## Scaffold committed

[`experimental/genvex_remote/sensor_model.py`](../experimental/genvex_remote/sensor_model.py) defines the five supported sensors, decimal device-ID → Nabto hostname conversion, temperature transformation `(raw - 300)/10`, humidity conversion, strict signed-int16 validation and fail-whole-batch behavior. It contains **no Nabto SDK binary and no private credentials**.

[`experimental/genvex_remote/test_sensor_model.py`](../experimental/genvex_remote/test_sensor_model.py) tests the verified batch, address order, device-ID validation, malformed and incomplete responses offline. This model is intentionally staged **outside** `custom_components/genvex_connect`, so installing or updating the existing local integration cannot be affected.

## Target end-user experience (new product requirement)

The user expects **Settings → Devices & services → Add integration → Genvex Remote** with an ordinary login/config form. The user should **never** have to use SSH/terminal, transfer certificates, create CSRs, copy encrypted keys, or type the local key-unlock passphrase for routine operation. The runtime App must internally handle private key + CSR generation, vendor legacy CA certificate enrollment, persistent protected credential lifecycle and SDK startup; the separate HA integration owns device/entity UI. The old standalone test app exists because its x86_64 SDK cannot run in native ARM64 HA Core. Full [architecture and security gates](remote-ha-ui-onboarding-architecture.md).

## Implemented foundational contracts (development branch only)

- [Registration HTTP transport](../experimental/genvex_remote/registration_http.py): known legacy CA endpoint, strict TLS, bounded POST, no redirects; **not invoked automatically**.
- [Transactional enrollment](../experimental/genvex_remote/enrollment_service.py): injected transport and explicitly pinned CA, with versioned credential installation only after verification.
- [Private profile store](../experimental/genvex_remote/profile_store.py): private persistent generations and atomic active pointer, without overwriting the existing key on failed enrollment; cleanup/rotation after crash is still to be designed.
- [Fresh snapshot contract](../experimental/genvex_remote/snapshot_contract.py): checks device ID, schema, complete five readings, UTC timestamp, freshness and finite values, so the eventual HA coordinator never displays failed/stale data as live.
- [Offline CI workflow](../.github/workflows/remote-nabto-offline.yml): exercises fake CA, safe storage, URL transport and snapshot logic; **CI execution outcome not independently confirmed in this update**.

**All of these are isolated development files, not yet imported by the installed HAOS runtime or an integration. No new live cert was issued.**

## Home Assistant UI and read-only poller scaffold — 2026-11-20

[`experimental/home_assistant/`](../experimental/home_assistant/README.md) now contains a separate `genvex_remote` HA integration **development scaffold** (config flow, unique 12-digit device ID, 60-second `DataUpdateCoordinator`, five temperature/humidity sensor entities with stable unique IDs and device registry group, English/Danish labels). Importantly, [`UnconfiguredReader`](../experimental/home_assistant/custom_components/genvex_remote/runtime_client.py) *always fails closed*, so installing this unfinished scaffold **will not generate fictional live readings** and configuration entries remain not-ready. It is not yet intended for installation.

[`experimental/genvex_remote/polling_worker.py`](../experimental/genvex_remote/polling_worker.py) defines an SDK-independent serial, single-flight read-only worker with one five-address RPC45 callback, bounded timeout, strict decode and timestamp generated only after complete success. [Offline tests](../experimental/genvex_remote/test_polling_worker.py) cover addresses, concurrency, timeout/recovery and sanitization. A real SDK reader and authenticated App-to-Core bridge are **still missing**.

The [CI workflow](../.github/workflows/remote-nabto-offline.yml) now includes HA parser tests and source compilation checks. **No CI pass status or live HA Core/hassfest test is claimed yet**; the user's earlier 51/51 successful HAOS suite predates these new files.

## Remaining bridge (must be implemented before live HA entities)

Build a private, well-defined **HAOS runtime → Home Assistant data bridge**. The current v0.4.0 app exposes a one-shot manual RPC script, not a polling service, shared state/API or Home Assistant Config Entry. No false live-data dashboard shortcut.

Recommended architecture:

1. A confined, read-only Nabto worker inside the separate runtime app, using the existing encrypted client certificate and a secret injection strategy that survives HAOS restarts without logging the passphrase. No credentials in the public repository, URL, command line, entity attributes or debug output.
2. One worker poll per ~60 seconds (serial, never overlap), bounded call timeout, backoff on failure and last-success timestamp. Produce an atomic **five-value** snapshot with schema/version, device ID, timestamp, and valid decoded readings, with no credentials. An internal endpoint or controlled shared file may be used; the exact mechanism must be reviewed for HAOS permission/isolation, concurrency and HA process access.
3. A *separate* `genvex_remote` HA integration, with config flow for the 12-digit device ID, async DataUpdateCoordinator reading the worker snapshot, five sensor entities with stable unique IDs, temperature/humidity device classes, measurement state classes and units. On stale/failed reads, mark all five **unavailable** instead of retaining misleading 'live' values.
4. Isolation: do **not** modify `custom_components/genvex_connect` or its `genvexnabto==1.5.4` dependency, and do not expose climate/switch/number/write controls in v1.

## Authenticated runtime IPC decision

Review [`remote-runtime-ipc-security.md`](remote-runtime-ipc-security.md) before selecting the transport. The existing v0.5.0 App uses `host_network: true` for legacy LAN discovery; **do not** add an unauthenticated HTTP or enrollment endpoint to it. A separate runtime App on the internal Supervisor network may be preferable, but the remote Nabto path must be verified there. No shared secret/authorization mechanism is implemented yet. See [Home Assistant's App communication guidance](https://contributors.home-assistant.io/apps/guides/communication/) and [2026 host-network security advisory](https://github.com/home-assistant/core/security/advisories/GHSA-gh5m-4m97-c95h).

The [combined native HAOS offline test runner](../scripts/run_haos_remote_dev_tests.sh) exercises the original enrollment/sensor tests, new serialized worker, isolated HA parser and compiles the entire HA scaffold. **Its result has not yet been reported from HAOS.**

### Verified full remote-to-HTTP one-shot test and new polling scaffold — 2026-11-20

The user's HAOS terminal output confirms [`run_haos_live_rpc_to_ipc_test_v2.sh`](../scripts/run_haos_live_rpc_to_ipc_test_v2.sh) passed: a real read-only remote RPC45 batch created a complete fresh snapshot, a second Docker container rejected missing/incorrect bearer tokens and accepted five **real** sensor values over HTTP. The device identity, timestamp and schema passed strict validation. This was **not Home Assistant Core**, and no long-lived worker was started.

[`polling_service.py`](../experimental/genvex_remote/polling_service.py) and [offline lifecycle tests](../experimental/genvex_remote/test_polling_service.py) are now staged, but **not yet HAOS-tested, connected to the SDK, or installed**. Remaining blocking deliverables: supervised SDK worker, secure shared secret provisioning, production App packaging, real Home Assistant config entry and enrollment/CA pinning.

### SDK subprocess adapter — staged after 84/84 HAOS tests

[`sdk_snapshot_adapter.py`](../experimental/genvex_remote/sdk_snapshot_adapter.py) now provides a native Python async bridge to the **already working isolated QEMU x86_64 snapshot probe**. The adapter uses a bounded subprocess, routes the existing unlock secret only over stdin (never as a command-line argument/environment variable), captures output without logging it, accepts exactly one validated structured snapshot marker, and kills/waits for the subprocess on timeout/cancellation. Its `poll_once()` method is directly compatible with `SnapshotState` and the serial 60-second `PollingService`. This is **source-only**: the installed App still has no persistent worker or secured token-provisioned IPC.

[`test_sdk_snapshot_adapter.py`](../experimental/genvex_remote/test_sdk_snapshot_adapter.py) adds mock-subprocess tests for success, SDK failure redaction, timeout, cancellation, malformed output and polling integration. The pinned [native HAOS test runner](../scripts/run_haos_sdk_adapter_offline_v1.sh) exercises the full backend suite plus compilation **without touching the real Nabto profile or gateway**. **Test result pending.** Remaining production work includes daemon supervision/restart, credential lifecycle/CA pinning, bounded stream buffering, secure internal API and real HA Core config-flow test.

## Engineering gates before installation

- Verify transport bridge in isolation: permissions, schema, heartbeat, malformed payload, stale timestamp, worker crash/restart, QEMU hard timeout and credential cleanup.
- Test update coordinator concurrency, entity availability and restart behavior using mocks.
- Review redistribution/legal constraints for legacy Nabto SDK; don't commit binaries, key or cert.
- Only then install `genvex_remote` as a second integration and add its sensors to a Lovelace dashboard.

**Success criterion:** five actual, auto-refreshing sensor entities with no dependency on Steam Deck or manual SSH, even though the proprietary SDK is still emulated through QEMU.
