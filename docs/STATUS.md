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

## Open gates / immediate next development

**DEV4 milestone (22 November):** P.6a passed following the earlier P.6 `BLOCKED_PROBE` result. The observed success was a single fresh five-sensor snapshot in manually started/non-persistent mode. The App-to-HA live transport and entity lifecycle remain unverified.

1. Reconcile the DEV3 persistent worker and its lifecycle with the checked-in SDK adapter and App runtime, and repeat failure/restart/shutdown tests without leaking credentials.
2. Verify the real App-to-HA authenticated snapshot contract and private DNS in HAOS; validate HA Core import, config flow, sensor availability and entity identities.
3. Finish private profile provisioning and IPC token lifecycle; maintain stable five-sensor v1 behavior while bringing the optional v2/7-value path under separately tested gates.
4. Validate sustained operation, recovery/soak tests, packaging parity and proprietary legacy SDK licensing/distribution before declaring remote support installable.

For the development entry points see [scripts](../scripts/README.md), [experimental runtime](../experimental/genvex_remote/), [HA scaffold](../experimental/home_assistant/README.md), [isolated App](../genvex-nabto-remote/DOCS.md) and [architecture roadmap](architecture-maintenance-plan.md).
