# Genvex Connect — Home Assistant integration

Home Assistant support for **Genvex Connect and Nilan gateways**, including controllers such as Genvex Optima 270. This repository contains two distinct development tracks:

- **LAN integration (existing):** `custom_components/genvex_connect/` uses [GenvexNabto](https://github.com/superrob/genvexnabto) for direct **local UDP / Micro Nabto** communication. This is the established HACS integration.
- **Remote integration (experimental):** a separate HAOS App and Home Assistant integration prototype use the legacy Nabto 4/Micro SDK through QEMU on ARM64 to make authenticated remote read-only RPCs. **This is not a released remote feature of the LAN integration.**

[![Home Assistant installs](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.genvex_connect.total)](https://github.com/rabbyraptor/genvexconnect)

## Current status — 21 November 2026

| Capability | Status |
| --- | --- |
| Existing LAN component | Implemented; local gateway discovery and setup using the email configured in the official app |
| Remote read-only RPC45, five Optima 270 sensors | **Live verified** on x86_64 and HAOS ARM64/QEMU |
| Remote seven-address v2 read | **Live verified on Steam Deck**; not yet a deployed seven-sensor HAOS service |
| Persistent legacy SDK adapter (DEV3) | **21 November operator test PASS:** three successive 5-value RPC45 reads, same reused worker; 10,504 / 40 / 34 ms; shutdown and restart checks PASS |
| Separate HAOS Remote App | Development App `local_genvex_nabto_remote`; last verified installed version `0.1.0-dev2` on 20 November |
| Remote HA dashboard/entities and automatic user onboarding | **Experimental scaffold only; not released or end-to-end validated** |
| Remote control/write commands | Not supported or verified |

See **[current engineering status](docs/STATUS.md)** for verified evidence, limitations, and next gates, and [documentation index](docs/README.md) for architecture/research.

## Supported controllers (existing LAN integration)

| Controller | Gateway | Previously reported tested |
| --- | --- | --- |
| Optima 250 / 251 | External internet gateway | Yes |
| Optima 260 | External internet gateway | Not recorded |
| Optima 270 | Built in | Yes |
| Optima 301 / 312 | External internet gateway | Yes |
| Optima 314 | Built in | Not recorded |
| Nilan CTS400 / CTS602 / CTS602 Light | Nilan gateway | Yes |
| Nilan CTS602 Geo | Nilan gateway | Not recorded |

The table describes existing **LAN integration** support, not remote interoperability or newly verified tests.

## Install the existing LAN integration

**HACS:** Open HACS, search for **Genvex Connect**, install the integration, and restart Home Assistant. Alternatively copy `custom_components/genvex_connect` into your HA `config/custom_components/` directory and restart HA.

**Configure:** Open **Settings → Devices & services → Add integration → Genvex Connect**. Select a discovered gateway and enter the email registered in the official Genvex Connect app (case sensitive). The integration authenticates on the **local network**.

**Remote experimental track:** Do **not** install the development App or `experimental/home_assistant` expecting plug-and-play remote devices; see [remote installation readiness](docs/remote-install-readiness.md) and [remote App notes](genvex-nabto-remote/DOCS.md).

## Repository map

| Path | Purpose |
| --- | --- |
| [`custom_components/genvex_connect/`](custom_components/genvex_connect/) | Existing LAN HACS integration |
| [`experimental/genvex_remote/`](experimental/genvex_remote/) | Remote transport, sensor models, IPC and offline tests |
| [`experimental/home_assistant/`](experimental/home_assistant/) | Separate, experimental remote Home Assistant integration |
| [`genvex-nabto-remote/`](genvex-nabto-remote/) | Separate ARM64 HAOS development App |
| [`haos-apps/`](haos-apps/) | Earlier isolated HAOS runtime test artifacts |
| [`docs/`](docs/README.md) | Current docs, evidence and research archive |
| [`scripts/`](scripts/README.md) | Current test/development entry points and [historical scripts](scripts/archive/README.md) |

## Developer checks

From the repository root:

```sh
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py'
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py'
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py'
python3 -m compileall -q experimental/genvex_remote experimental/home_assistant genvex-nabto-remote/runtime
```

These are source/offline checks; they do not open a live Nabto session. Additional HAOS runners are listed in [scripts/README.md](scripts/README.md).

## License

[GPL-3.0](LICENSE). Proprietary Nabto 4 SDK redistribution/licensing for an experimental Remote App remains a separate unresolved release requirement. All use is provided without warranty.
