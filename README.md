# Genvex Connect — Home Assistant integration

Home Assistant integration development for **Genvex Connect and Nilan gateways**. The repository contains two **separate** paths:

- **Genvex Connect (LAN)** — the existing, Marketplace-compatible LAN integration in [`custom_components/genvex_connect/`](custom_components/genvex_connect/), using [GenvexNabto](https://github.com/superrob/genvexnabto) to communicate with supported gateways over local UDP / legacy Micro Nabto.
- **Genvex Remote (experimental)** — a separate HAOS App and `genvex_remote` Home Assistant integration for authenticated **remote, read-only** RPC45 access using the proprietary legacy Nabto Micro SDK. Successfully deployed and live-verified on one **Genvex Optima 270** running Home Assistant OS ARM64. This is **not** a public Marketplace release or a claim of remote support for every LAN-compatible controller.

[![Home Assistant installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.genvex_connect.total)](https://github.com/rabbyraptor/genvexconnect)

## Current remote milestone — DEV9 (23 November 2026)

The remote integration is live-verified on **one Optima 270 / HAOS ARM64** installation. The pinned comparison baseline is DEV9 commit `e0f2f462`; this branch adds refactoring, documentation and localization improvements that have **not** been separately deployed to HAOS.

| Capability | Verified DEV9 baseline |
| --- | --- |
| Genvex Remote App | `0.1.0-dev9`, persistent Nabto Micro SDK session |
| Separate HA integration | `0.3.0`, authenticated private read-only snapshot client |
| Scaled RPC45 readings | **5/5** — four temperatures and humidity |
| Raw RPC45 diagnostics | **17/17** signed-int16 values (5 baseline + 12 optional) |
| Selected ventilation stage | **RPC42 object 0 / address 7**, integer **0–4** or unavailable; not RPM/physical airflow |
| Data-age diagnostic | One independently registered entity |
| Entity inventory with v4 and raw v3 enabled | **24/24** (5 + 17 + 1 + 1) |
| Pairing | Automatic Supervisor token retrieval or manual IPC token |
| Confirmed fan-command display | RPC45 18/19 `raw / 100` corresponds to official UI display at one measured stage; this is **not** measured airflow |
| Remote writes | **Not verified and not enabled** |

Current source architecture and development changes are recorded in the [architecture owner map](docs/overnight-architecture-baseline.md) and [development log](docs/overnight-refactoring-log.md). The [Micro Nabto protocol library](docs/micro-nabto-protocol-library.md) catalogs all **currently source-known** RPC operations, 17 datapoints and 12 active read/write setpoint-address pairs; a documented write address does **not** imply an implemented write transport. Earlier [DEV8 evidence](docs/dev8-live-verification-2026-11-22.md) is historical.

### Remote data path

```text
Optima 270 → legacy encrypted Nabto Micro (x86-64 SDK under QEMU)
    → persistent read-only worker: RPC45 (5 + 12), RPC42 (stage 0–4)
    → Genvex Remote HAOS App: strict versioned v1/v3/v4 snapshots
    → private authenticated HTTP IPC
    → Home Assistant genvex_remote integration: 24 distinct entities
```

The remote implementation communicates through the legacy SDK, **not** by proxying the phone app. The existing Marketplace-compatible LAN integration remains independent.

### Sensor names and icons

Newly registered/imported Remote sensors use Home Assistant's **per-user language-aware entity translations**, with English and Danish names and catalog-specified default MDI icons. Localized raw diagnostic labels distinguish individual RPC45 addresses. Entity `unique_id` values are unchanged; manually renamed entities remain under the user's control. The translation files are synchronized from register metadata using `scripts/sync_remote_entity_localizations.py --sync`, validated by `--check`.

### Snapshot and recovery boundaries

- All five RPC45 baseline values must validate before a snapshot is published. An optional twelve-register read failure leaves the five readings valid; optional candidates become **unavailable**, not fabricated zeroes.
- V4 adds the selected RPC42 stage while retaining the v1/v3 projections. `None` for the stage means unavailable, while stage `0` is a valid reading.
- The coordinator tracks the original gateway sample age with a bounded grace window. Automatic Supervisor pairing can recover an IPC-token change after a bounded unauthorized response.
- Only one tested remote Optima 270 configuration is demonstrated. Source-known register labels or setpoint *write addresses* for other hardware are not proof of installed components or remote write support.

## Install the existing LAN integration

**Home Assistant 2026.11+:** Open **Settings → Marketplace** and look for **Genvex Connect** (or add it as a custom repository if supported). Existing older HACS installations are migrated to Marketplace by Home Assistant. The old standalone HACS installation is no longer used on 2026.11+. Alternatively, copy [`custom_components/genvex_connect/`](custom_components/genvex_connect/) into your Home Assistant `config/custom_components/` directory and restart.

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

This table describes the **LAN integration only**. Remote DEV9 has been live-verified specifically on Optima 270.

## Experimental remote development and setup

The remote implementation is maintained separately; installing the LAN integration does **not** enable remote access. It requires an isolated HAOS App, a provisioned legacy client profile, an authenticated private App-to-Core connection, and the separate `genvex_remote` component. The tested DEV9 deployment uses a versioned, checksum-verified source package; refactoring-branch source changes remain separate from the installed baseline.

For an **already provisioned development installation**, enable `persistent_session: true`, `raw_registers_v3: true` and `fan_level_v4: true` in the Remote App; enable raw-register and fan-level v4 options in the separate HA integration. Automatic Supervisor pairing remains supported.

This is a development/test procedure, **not** a general installation guide or a released Marketplace remote feature. See [DEV9 architecture](docs/overnight-architecture-baseline.md), [work log](docs/overnight-refactoring-log.md) and historical [DEV8 live verification](docs/dev8-live-verification-2026-11-22.md). Public distribution of the legacy proprietary SDK remains subject to separate licensing/packaging decisions.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`custom_components/genvex_connect/`](custom_components/genvex_connect/) | Existing Marketplace-compatible LAN integration |
| [`experimental/genvex_remote/`](experimental/genvex_remote/) | Canonical shared remote runtime, schemas, evidence and offline tests |
| [`genvex-nabto-remote/`](genvex-nabto-remote/) | Isolated HAOS App, native ARM64 orchestration and x86-64 SDK worker |
| [`experimental/home_assistant/`](experimental/home_assistant/) | Separate, now live-tested `genvex_remote` HA integration and tests |
| [`scripts/package_dev9_combined.py`](scripts/package_dev9_combined.py) | Deterministic DEV9 App + HA source archive with SHA256 manifest |
| [`scripts/check_remote_contracts.py`](scripts/check_remote_contracts.py) | Offline validation of App/HA options and version contracts |
| [`docs/`](docs/README.md) | Evidence, architecture, test gates and historical notes |

## Offline developer checks

From the repository root:

```sh
python3 scripts/check_remote_runtime_parity.py --check
python3 scripts/check_remote_contracts.py
python3 scripts/sync_remote_entity_localizations.py --check
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py'
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py'
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py'
python3 -m compileall -q experimental/genvex_remote experimental/home_assistant genvex-nabto-remote/runtime
python3 scripts/package_dev9_combined.py
```

The CI also performs Home Assistant validation and native ARM64 App-image builds. These tests do not substitute for a sustained gateway connection test.

## License

The project code is licensed under [GPL-3.0](LICENSE). The proprietary legacy Nabto SDK is a separate dependency; its redistribution rights and production release packaging are not established by this repository. All use is provided without warranty.
