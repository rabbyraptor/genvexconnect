# Genvex Connect — Home Assistant integration

Home Assistant integration development for **Genvex Connect and Nilan gateways**. The repository contains two **separate** paths:

- **Genvex Connect (LAN)** — the existing, HACS-installable integration in [`custom_components/genvex_connect/`](custom_components/genvex_connect/), using [GenvexNabto](https://github.com/superrob/genvexnabto) to communicate with supported gateways over local UDP / legacy Micro Nabto.
- **Genvex Remote (experimental)** — a separate HAOS App and `genvex_remote` Home Assistant integration for authenticated **remote, read-only** RPC45 access using the proprietary legacy Nabto Micro SDK. Successfully deployed and live-verified on one **Genvex Optima 270** running Home Assistant OS ARM64. This is **not** a public HACS release or a claim of remote support for every LAN-compatible controller.

[![Home Assistant installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.genvex_connect.total)](https://github.com/rabbyraptor/genvexconnect)

## Current status — 22 November 2026

| Capability | Status |
| --- | --- |
| Existing LAN integration | Available through HACS; separate from the remote implementation |
| Remote connection to an Optima 270 | **Live verified** through legacy Nabto Micro on HAOS ARM64 |
| HAOS App | **`0.1.0-dev8` installed and running** on the verified test system |
| Separate HA integration | **`0.2.0` installed and loaded** as `genvex_remote` |
| Standard read-only sensors | **5/5** available: supply, outdoor, exhaust and extract air temperatures, plus humidity |
| Optional diagnostic raw registers | **17/17** available with real numeric values via v3 snapshot |
| Data-age sensor | **1/1** available; tracks original sample age |
| Total entities with raw v3 enabled | **23/23** available (5 scaled + 17 raw + 1 data-age) |
| Persistent Nabto worker | **Live verified**; the same SDK process handled consecutive RPC45 polls |
| Token refresh and failure recovery | Offline regression-tested; controlled live fault injection still pending |
| Long-duration v3 stability | Further live observation required |
| Remote write/control operations | **Not implemented** |

The combined DEV8 source package was installed from pinned commit
[`027dbf8`](https://github.com/rabbyraptor/genvexconnect/commit/027dbf807e4eb2a04c2d52b01e64c09420b083b4), with the App and HA component updated together. The operator installation gate passed, and subsequent Home Assistant checks found all 23 entities available.

**Live evidence:** [DEV8 installation and 17/17 raw-register verification](docs/dev8-live-verification-2026-11-22.md). **Development PR:** [DEV8 staging, draft #16](https://github.com/rabbyraptor/genvexconnect/pull/16).

These results establish the operation of **one tested remote Optima 270 installation**, not a generic plug-and-play installer or an endorsement of unsupported controllers.

## How the remote integration works

```text
Genvex Optima 270 + Connect gateway
       │
       │  Authenticated, encrypted Nabto Micro remote connection
       ▼
Legacy Nabto SDK (x86-64, proprietary)
       │  Runs in QEMU x86-64 on an ARM64 HAOS host
       │  One persistent SDK process and session
       │
       ├── RPC45 read #1:  5 mandatory registers
       └── RPC45 read #2: 12 optional registers
       │
       ▼
Genvex Remote HAOS App (0.1.0-dev8)
       │  Serial polling every 60 seconds (configured test interval)
       │  Validates readings and maintains versioned snapshots
       │
       ├── /v1/snapshot  5 scaled readings
       └── /v3/snapshot  5 scaled + 17 unscaled signed-int16 raw values
       │
       │  Private App-network HTTP; bearer-token authentication
       ▼
Genvex Remote Home Assistant integration (0.2.0)
       │  Authenticated snapshot reader + DataUpdateCoordinator
       │  Optional automatic IPC token retrieval from Supervisor
       ▼
Home Assistant entities (5 + 17 + 1 = 23 in v3 mode)
```

This is **not** a translation layer through the iPhone/Android Genvex Connect app, nor is it a clean-room implementation of the entire Nabto protocol. The proprietary x86-64 SDK handles the Nabto session, encryption and RPC transport; our code implements the persistent worker, RPC45 requests, validation, HTTP snapshot interface and Home Assistant entities. The original mobile app is not involved in the data path.

### Why reads are fast

A cold SDK start and first v3 read took **10.71 seconds** in a recorded live run. The next polling cycle took **0.07 seconds**, while reusing the same worker PID. This timing covers the App's polling/snapshot update (including the two RPC45 requests); it is **not** a guarantee of network latency or the delay until every HA entity refreshes.

The App polls the gateway on its own schedule and caches a validated snapshot. Home Assistant fetches that snapshot over the private App network, without opening another Nabto session for each entity.

### Live-verified RPC45 registers

The five baseline addresses are used for the existing scaled readings. In optional **v3 raw mode**, those five plus twelve additional, previously observed addresses are exposed as **signed 16-bit integers with no inferred units**.

| Addresses | Raw register group | Verification |
| --- | --- | --- |
| 20, 21, 22, 23, 26 | Five baseline air/humidity readings | Live read and scaling verified |
| 24 | Frost-protection candidate | Raw reading verified; physical interpretation pending |
| 18, 19 | Supply/extract fan-control candidates | Raw readings verified; units/meaning pending |
| 35, 36 | Fan-related candidates | Raw readings verified; units/meaning pending |
| 41, 42 | Heating-related candidates | Raw readings verified; units/meaning pending |
| 53, 40 | Bypass-related candidates | Raw readings verified; states/meaning pending |
| 114, 115 | Alarm-word candidates | Raw readings verified; alarm bit meanings pending |
| 50 | Rotor-related candidate | Raw reading verified; units/meaning pending |

**Observed live v3 snapshot (22 November 2026, 21:42 CET):**

```text
20=371   21=335   22=345   23=373   26=62
24=0     18=6000  19=5800  35=2416  36=2268
41=0     42=0     53=0     40=0     114=0
115=0    50=10
```

These are measured *raw values*, not automatically percentages, RPM, alarm statuses, or temperatures. The five existing scaled measurements in the same snapshot were **7.1 °C, 3.5 °C, 4.5 °C, 7.3 °C and 62%** respectively. See the [register evidence gate](docs/dev8-2-register-evidence-gate.md) and [raw v3 contract](docs/dev8-3-all-raw-registers.md).

### Snapshot behavior and recovery

- Raw mode is **opt-in** on both the HAOS App and the `genvex_remote` integration (`raw_registers_v3: true`). It requires `persistent_session: true` in the App.
- The five baseline RPC45 registers must validate. If the separate twelve-register read fails, the existing five measurements remain available; the missing optional raw values are **unavailable, not zero**.
- The HA coordinator tracks the **original gateway sample timestamp**. Previously validated data can remain available for up to **10 minutes** during a short outage; the data-age sensor exposes that age.
- The private snapshot endpoint requires a bearer token. With Supervisor pairing enabled, HA Core can recover a changed token after an IPC **401/403** with one bounded retry. Token rotation is verified offline; a controlled live rotation remains an acceptance item.

## Install the existing LAN integration

**Through HACS:** Find **Genvex Connect**, install it, then restart Home Assistant. Alternatively, copy [`custom_components/genvex_connect/`](custom_components/genvex_connect/) into your Home Assistant `config/custom_components/` directory and restart.

**Configure:** Open **Settings → Devices & services → Add integration → Genvex Connect**. Select a discovered gateway and enter the case-sensitive email associated with the official Genvex Connect app. This connects over the **local network**.

### Previously reported LAN controller compatibility

| Controller | Gateway | Previously reported tested |
| --- | --- | --- |
| Optima 250 / 251 | External internet gateway | Yes |
| Optima 260 | External internet gateway | Not recorded |
| Optima 270 | Built in | Yes |
| Optima 301 / 312 | External internet gateway | Yes |
| Optima 314 | Built in | Not recorded |
| Nilan CTS400 / CTS602 / CTS602 Light | Nilan gateway | Yes |
| Nilan CTS602 Geo | Nilan gateway | Not recorded |

This table describes the **LAN integration only**. Remote DEV8 has been live-verified specifically on Optima 270.

## Experimental remote development and setup

The remote implementation is maintained separately; installing the LAN integration does **not** enable remote access. It requires an isolated HAOS App, a provisioned legacy client profile, an authenticated private App-to-Core connection, and the separate `genvex_remote` component. The tested DEV8 deployment used a **pinned, checksum-verified combined source package** and a reviewed HAOS installer.

For an **already provisioned development installation**, enable raw v3 by setting `raw_registers_v3: true` in the Remote App configuration while retaining `persistent_session: true`, restart the App, then enable **Expose all 17 RPC45 raw values** in the Genvex Remote integration options. Automatic Supervisor pairing is supported.

This is a development/test procedure, **not** a general installation guide or a released HACS remote feature. See [DEV8 combined release gate](docs/dev8-4-combined-release-gate.md) and [live verification](docs/dev8-live-verification-2026-11-22.md). Public distribution of the legacy proprietary SDK remains subject to separate licensing/packaging decisions.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`custom_components/genvex_connect/`](custom_components/genvex_connect/) | Existing HACS LAN integration |
| [`experimental/genvex_remote/`](experimental/genvex_remote/) | Canonical shared remote runtime, schemas, evidence and offline tests |
| [`genvex-nabto-remote/`](genvex-nabto-remote/) | Isolated HAOS App, native ARM64 orchestration and x86-64 SDK worker |
| [`experimental/home_assistant/`](experimental/home_assistant/) | Separate, now live-tested `genvex_remote` HA integration and tests |
| [`scripts/package_dev8_combined.py`](scripts/package_dev8_combined.py) | Reproducible App + HA source archive with SHA256 manifest |
| [`scripts/run_dev8_combined_from_deck.sh`](scripts/run_dev8_combined_from_deck.sh) | Pinned development HAOS preflight and single-package installer runner |
| [`docs/`](docs/README.md) | Evidence, architecture, test gates and historical notes |

## Offline developer checks

From the repository root:

```sh
python3 scripts/check_remote_runtime_parity.py --check
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py'
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py'
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py'
python3 -m compileall -q experimental/genvex_remote experimental/home_assistant genvex-nabto-remote/runtime
python3 scripts/package_dev8_combined.py
```

The CI also performs Home Assistant validation and native ARM64 App-image builds. These tests do not substitute for a sustained gateway connection test.

## License

The project code is licensed under [GPL-3.0](LICENSE). The proprietary legacy Nabto SDK is a separate dependency; its redistribution rights and production release packaging are not established by this repository. All use is provided without warranty.
