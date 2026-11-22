# Remote Nabto development status

**Updated:** 22 November 2026. **Branch:** `remote-nabto-connection`.  
**Scope:** experimental remote Nabto Micro / Nabto 4 work for Genvex Connect Optima 270 on Home Assistant OS (ARM64). This is the current status summary; detailed dated evidence remains in [verified facts](remote-nabto-verified-facts.md) and [the archive](archive/README.md).

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
