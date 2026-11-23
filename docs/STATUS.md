# Remote Nabto development status — DEV9

**Current verified state:** 23 November 2026. **Code baseline:** DEV9 commit `e0f2f462`. **Refactoring branch:** `overnight-refactoring`. Changes here are not automatically installed on HAOS.

| System | Verified state |
| --- | --- |
| Home Assistant OS | ARM64 host, x86-64 legacy Nabto Micro SDK under QEMU |
| Remote App | `0.1.0-dev9`, persistent read-only SDK session |
| HA integration | `genvex_remote` `0.3.0` |
| RPC45 | Five scaled measurements and seventeen raw signed-int16 diagnostics |
| RPC42 | Selected ventilation stage from obj=0, address=7; integer 0–4, null = unavailable |
| Available entities | **24/24** on tested setup: 5 scaled + 17 raw + 1 data age + 1 stage |
| Authentication | Private App IPC token, automatic Supervisor pairing or manual token |
| Read/write catalog | All currently source-known RPC commands and twelve setpoint read/write address pairs are documented; **remote RPC43 writes remain unverified and disabled** |
| Sensor metadata | New sensor entities use catalog-based default icons and Home Assistant native English/Danish translations, selected by the HA user's language |
| Hardware scope | One known Optima 270 configuration; no general multi-model remote deployment claim |

The [architecture map](overnight-architecture-baseline.md) and [task log](overnight-refactoring-log.md) are the source for the *current branch's* design and code/test changes. The [protocol library](micro-nabto-protocol-library.md) documents read-only lookups and source-evidence categories. No tests of live hardware were repeated as part of the refactoring.

---

## Historical chronology — preserve dates, NOT current system status

The following sections were written during earlier DEV1–DEV8 investigations, including when only five sensors or an older App version were available. Their “current”, “remaining” and “not yet deployed” statements are **historical at the time they were recorded** and must not override the DEV9 summary above.

## What is verified

| Area | Evidence | Boundary |
| --- | --- | --- |
| Existing LAN integration | `custom_components/genvex_connect/` uses the separate local-UDP `genvexnabto` library | Not the experimental remote transport |
| Remote RPC | Legacy Nabto SDK 4.9.11 authenticated, remote read-only RPC 17 and RPC 45; five Optima 270 addresses 20, 21, 22, 23, 26 returned data on Steam Deck and on HAOS/QEMU | No remote control/write support |
| Seven-address prototype | A single read-only batch of 20, 21, 22, 23, 26, 18, 19 succeeded on Steam Deck (20 November) | Not yet verified as a seven-item live HAOS/QEMU deployment; fan-duty interpretation requires UI comparison |
| HAOS transport | ARM64 container running x86_64 legacy SDK through QEMU, native ARM64 orchestration, dedicated experimental Supervisor App | No proven native ARM64 Nabto 4 SDK |
| HAOS App installation | `local_genvex_nabto_remote` was verified updated to `0.1.0-dev2` on 20 November; backup `07337fa3` contains a previous `dev1` App record | Backup restore/integrity not verified; current live Supervisor state should be rechecked before future deployment |
| DEV4 App → HA Core authenticated snapshot (22 November) | **Operator-verified PASS:** HA Core resolved `local-genvex-nabto-remote` to `172.30.33.2`, reached TCP `18275`, and received HTTP `401` without token; with the App-private bearer token, HA Core received HTTP `200`, schema v1, health `ok`, five expected sensor fields, exit code 0 | Confirms live IPC transport but not HA entity registration or ongoing polling |
| DEV4 Gate P.6a (22 November) | **Operator-verified PASS:** App `0.1.0-dev4` started with manual boot, persistent session disabled; first diagnostic probe PASS, five sensors returned, snapshot freshness PASS, exit code 0 | Validates one bounded manually started read, not persistent polling or HA Core entities |
| Persistent SDK adapter (DEV3) | **Operator-verified 21 November:** preflight and local offline checks PASS; three authorized RPC45 reads returned 5 values each, with elapsed times **10,504 ms / 40 ms / 34 ms**. Worker process was reused on reads 2 and 3; worker closed successfully, exit 0; DEV3 restart check PASS | Validates that live test sequence, not a production background polling service or Home Assistant Core integration |
| Offline tests | Repeated source-only / CI suites and synthetic App/HA tests have passed in earlier gates; see dated logs and evidence | Synthetic endpoints do not establish live device readings |

The DEV3 figures are per-read observations, **not** representative latency guarantees. The first call includes startup/initialization; subsequent calls demonstrate process reuse within this bounded run.

## Architecture

```text
Genvex Connect / Optima 270 gateway
          │  remote Nabto Micro 4, authenticated read-only RPC45
          ▼
Experimental HAOS App (aarch64)
  native Python supervisor/runtime ── QEMU x86_64 ── legacy Nabto SDK
          │  planned authenticated internal snapshot endpoint
          ▼
Experimental separate HA integration (genvex_remote)
          │  HA coordinator / sensors (not production deployed)
          ▼
Home Assistant Core
```

The LAN `genvex_connect` HACS integration is a **separate already-working path**. The remote implementation is **not** a phone-app translation layer: it invokes the legacy SDK RPC interface directly. A native ARM64 reverse-engineered client is not implemented; QEMU is the tested compatibility mechanism.

## Data-age deployment (22 November 2026)

**Operator-verified on HAOS:** source commit `08f4b94` fast-forwarded; 34 HA offline tests passed, Python syntax PASS, backup PASS, integration files deployed, Home Assistant Core restart requested successfully, and deployed source verification confirmed `GRACE_SECONDS = 600`, `GenvexRemoteDataAge`, and 20-second snapshot client timeout (exit code 0). **Runtime entity registration and live grace/recovery behavior remain to be verified.**

## Open gates / immediate next development

**DEV4 milestone (22 November):** P.6a passed following the earlier P.6 `BLOCKED_PROBE` result. The observed success was a single fresh five-sensor snapshot in manually started/non-persistent mode. The App-to-HA live transport and entity lifecycle remain unverified.

1. Reconcile the DEV3 persistent worker and its lifecycle with the checked-in SDK adapter and App runtime, and repeat failure/restart/shutdown tests without leaking credentials.
2. Verify the real App-to-HA authenticated snapshot contract and private DNS in HAOS; validate HA Core import, config flow, sensor availability and entity identities.
3. Finish private profile provisioning and IPC token lifecycle; maintain stable five-sensor v1 behavior while bringing the optional v2/7-value path under separately tested gates.
4. Validate sustained operation, recovery/soak tests, packaging parity and proprietary legacy SDK licensing/distribution before declaring remote support installable.

For the development entry points see [scripts](../scripts/README.md), [experimental runtime](../experimental/genvex_remote/), [HA scaffold](../experimental/home_assistant/README.md), [isolated App](../genvex-nabto-remote/DOCS.md) and [architecture roadmap](architecture-maintenance-plan.md).


### HAOS live entity registration (22 November 2026)
Operator verification after coordinator `config_entry` fix (`984930e`): all six `genvex_remote` entities registered and enabled, including unique ID `286529209114_data_age` (entity ID `sensor.sommerhus_genvex_connect_remote`). Genvex log matches after the 01:46 restart contained only the generic custom-integration warning, no setup error. Live measurement-age progression and ten-minute grace recovery still require runtime verification.

## DEV4 unattended polling and periodic Nabto error investigation — 22 November 2026

**Operator-observed on the running HAOS `0.1.0-dev4` App; temporary runtime-container instrumentation, not yet committed to source.** After the HA coordinator/config-entry fix, six remote entities were registered (five measurements and a diagnostic data-age sensor). Recorder samples showed data age increasing and then resetting after fresh snapshots; no entities became `unavailable` during the sampled short gaps. The user observed three corresponding red connection indicators in the official Genvex Connect iPhone app while using cellular data. HAOS was on the user's home internet, and the Genvex gateway was at a separate address, connected by Ethernet to an attic Wi-Fi extender that uses wireless backhaul to the summer-house router. Coincident indicators suggest a shared gateway/upstream problem but do **not** isolate Wi-Fi loss, gateway registration, or Nabto infrastructure.

### RPC45 evidence

- **Non-persistent mode (`persistent_session: false`, `poll_seconds: 60`):** usual successful RPC45 duration approximately **5.6–5.9 s**; failures took **15–18 s** in observed samples. Failure completion timestamps included **02:54:27, 03:00:08, 03:05:49 CET**, each separated by **341 s** in that sequence. Subsequent reads succeeded.
- **Persistent mode (`persistent_session: true`, `poll_seconds: 60`):** usual successful repeated reads approximately **0.03–0.09 s** after initial worker startup; intermittent failures persisted. Observed failure completion timestamps included **10:42:16 and 10:48:22 CET** (**366 s** apart), **10:54:22, 11:00:28, 11:07:20** and **11:13:02 CET** (last inferred from the timestamp `2026-11-22T10:13:02Z`). Failure durations varied (examples **5.03 s**, **5.06 s**, **8.52 s**). At least one long read completed successfully (**13.50 s**). The exact six-minute periodicity is a measured pattern in short runs, **not** established as a time-based protocol rule.
- **Worker reuse:** during a recorded failure at **10:37:10 CET**, the SDK process remained PID 99 before and after the error; recovery succeeded next minute (0.40 s). Other errors likewise kept the same process PID. A surviving worker does not prove its Nabto session stayed connected.
- **Error provenance:** the x86_64 legacy library `/opt/nabto/libnabto_client_api.so` provides `nabtoStatusStr`; for `nabtoRpcInvoke()` status **26** its own text is **`the operation failed with a detailed json error message`**, **not** an independently established connection timeout. The nested JSON error contained keys `body`, `detail`, `event`, `header`. A later captured numeric **`error.event = 1000015`**, interpreted as `MICROSERVER_NOT_KNOWN` according to legacy Nabto documentation. This is consistent with temporary failure to locate/recognize the gateway through Nabto, but does not by itself establish the root cause.

**Instrumentation:** temporary edits within the running container to `polling_service.py`, `snapshot_state.py` and `persistent_rpc45_worker.py` logged timestamp/result/duration, SDK status, worker PID and *structural* JSON error metadata. The JSON diagnosis was written under `/data/rpc45_json_diagnostic.log` with only selected numeric fields. These edits are **not checked in** and should not be treated as durable across a Supervisor App rebuild. The deployed persistent setting was operator-confirmed `true`; interval remained 60 s.

**Next investigation when resumed:** compare RPC failure timestamps and `1000015` events with wireless backhaul/router logs at the remote property; ideally test temporary direct Ethernet to the router. Avoid assuming packet loss or Nabto service outages without independent evidence.

### Recommended next development gate (priority)

**3A + 2E + 5C: persist and test the now-proven DEV4 polling/diagnostic implementation in the canonical repository source.** Compare the checked-in App runtime with the running container, incorporate narrowly scoped non-secret RPC status/timing/worker-reuse logging under source control, add offline regression tests and build/parity checks, then verify the packaged App survives a normal rebuild/restart with consistent five-sensor v1 snapshots and Dataalder/grace behavior. This prevents the valuable live diagnostic work from being lost on the next image replacement. After this, proceed with 2D/3B credential/IPC token lifecycle and the 2A/2B → v2/seven-address expansion gates; see [architecture roadmap](architecture-maintenance-plan.md) and [installation readiness](remote-install-readiness.md).

## DEV4-to-DEV5 release candidate — 22 November 2026

After the installed DEV4 runtime gate passed (10/10 baseline files, persistent worker 1, authenticated v1 HTTP 200, five values, snapshot age 0.5 s), the operator ran the **read-only versioned-update environment gate**, which returned `VERSIONED_UPDATE_PREFLIGHT: PASS` and exit code 0:

- Running/manual Supervisor App version `0.1.0-dev4`; installed local source manifest also dev4; no update currently offered (expected).
- `persistent_session: true`, `poll_seconds: 60`; Docker container running without published host ports.
- No occupied DEV5 stage or DEV4 source-backup transaction path; available source filesystem space **6921 MiB**.
- Supervisor backup inventory contains **8 backups**. This count is not proof of a new rollback backup for the next release.

A separate **`0.1.0-dev5` App candidate** has been staged on the draft `dev4-source-parity-onboarding-20261122` PR #4 branch to preserve DEV4 RPC semantics and put metadata-only diagnostics in permanent source. The build workflow and version contract use dev5. `scripts/dev5_upgrade_transaction.py` and `scripts/run_dev5_upgrade_from_deck.sh` implement a commit-pinned source-archive preflight and an explicit staged/backup Supervisor update that preserves the live persistent options; the update leaves the App **stopped**, requiring an independent start and smoke test. Offline fixture tests validate the transaction with a fake Supervisor.

**Updated status:** The operator executed both `--preflight` and `--apply` from pinned commit `65ba9cb79ca9785aee8eb760435b00926ac1a687`, with matching 20-file source archive SHA256 `3bb6cde83eb986175b640059efdc8262b5778fe730b0a0973617594527977e0e`. The DEV4 source backup was retained, DEV5 offered/installed through Supervisor, and persistent options preserved. `INSTALLED_DEV5_STOPPED: PASS`, `DEV5_UPGRADE_RESULT: PASS`, exit 0. **DEV5 is installed but has not yet been started.** The Supervisor backup was *requested* and must be verified by inspecting new backup metadata. Next gate: `scripts/run_dev5_post_install_from_deck.sh`, which checks the 20 installed file hashes, source rollback copy, newly created Supervisor backup and Home Assistant's six registered entities, before any start. See [DEV5 diagnostic upgrade](dev5-diagnostic-upgrade.md).

## DEV5 and official Home Assistant MCP — live verified 22 November 2026

The distinct DEV5 App update and follow-up read-only post-install gate passed. The source-only installer used the pinned commit `65ba9cb79ca9785aee8eb760435b00926ac1a687`. Supervisor backup **`60e96ffb`** (2026-11-22T11:15:18.036512Z) was verified to include the DEV4 App. All 20 DEV5 source blobs match, persistent options remain unchanged, and the previous DEV4 source backup exists. The first-start operator script verified `SUPERVISOR_DEV5_STARTED: PASS` but terminated prematurely due to a shared SSH stdin stream: do not construe its exit code 0 as a complete Docker/IPC gate. A corrected independent-SSH read-only gate exists in `scripts/run_dev5_live_verify_from_deck.sh` and its fake-SSH early-EOF tests passed.

**New direct observation through the connected Home Assistant MCP integration:** `genvex_remote` config entry reports `loaded`; Home Assistant update entity reports installed/latest version **`0.1.0-dev5`**. The six live sensor entities were all readable, including five numeric measurements and Dataalder. Snapshot observed values were supply 7.6 °C, outdoor 4.5 °C, exhaust 5.1 °C, extract 7.6 °C, humidity 65.0%, and Dataalder 0.5 min. The captured log window through approximately 13:42 local time on 22 November showed approximately one successful read per minute, typically **0.03–0.04 s**, using the **same persistent SDK PID 98**. Intermittent `RPC45_DIAGNOSTIC rpc_status=26` errors still occurred approximately every six minutes (e.g. 13:25:58 and 13:32:12 local), and the following scheduled call succeeded using PID 98. No Genvex Core system-log warnings/errors were returned by the queried filter. Home Assistant Core version `2026.11.1`, HAOS `18.5`, architecture `aarch64`.

**Meaning:** The DEV5 App demonstrably resumed live polling and Home Assistant sensors are updating. This is stronger than mere entity registry presence, but the exact authenticated internal Docker IPC response/status was not directly tested through MCP. Home Assistant MCP provides state/log/health reads, **not** a generic SSH/Docker command execution mechanism. The separate HAOS Ops MCP bridge would be required for terminal operations. Keep the independent-SSH IPC gate available as a separate engineering acceptance test.
