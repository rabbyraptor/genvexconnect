# Remote Nabto / Genvex Connect — curated source and resource catalogue

**Purpose:** single index of relevant official documentation, upstream repositories, independent implementations, verified entry points, runtime/deployment documentation and our own project evidence. **Last consolidated: 2026-11-20.**

Read [verified facts](remote-nabto-verified-facts.md) for what we actually proved, [investigation journal](archive/remote-nabto-investigation.md) for chronological research, and [architecture/UI decision](remote-ha-ui-onboarding-architecture.md) for the planned product. Links below identify resources referenced and investigated in project notes; they **do not** imply current maintenance, compatibility, permission to redistribute binaries or that every code path was executed by us.

Legend: **VERIFIED** = behavior demonstrated in our controlled tests; **SOURCE** = relevant upstream source or documented API; **REFERENCE** = context, not necessarily applicable to Optima 270; **OPEN** = compatibility, legal or behavioral question not resolved.

## 1. Directly relevant Genvex and Optima 270 sources

| Resource | Status | Value / constraints |
| --- | --- | --- |
| [superrob/genvexconnect](https://github.com/superrob/genvexconnect) | SOURCE | Existing local Home Assistant integration, config flow and entity definitions; **do not modify for remote testing** |
| [superrob/genvexnabto](https://github.com/superrob/genvexnabto) | SOURCE + VERIFIED mapping | Current local Python library used by the HA integration; source of datapoint and controller mapping |
| [Optima 270 model map](https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/models/optima270.py) | SOURCE + VERIFIED subset | Sensor addresses **20/21/22/23/26** and value conversions validated by remote RPC 45 on our device |
| [genvexnabto client implementation](https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/genvexnabto.py) | SOURCE | Local discovery, auth, UDP and device handling, **not a working remote transport** |
| [genvexnabto model adapter](https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/genvexnabto_modeladapter.py) | SOURCE | Maps raw datapoints to controller semantics |
| [Local payload protocol](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/payload.py) | SOURCE | Reconstructed read request payloads; do not equate LAN register opcodes with Nabto RPC IDs |
| [andersdissing/com.genvex.connect](https://github.com/andersdissing/com.genvex.connect) | SOURCE | Independent Homey Genvex implementation; contextual protocol mapping |
| [Genvex Connect vendor page](https://www.genvex.com/produkter/genvex-tilbehor/genvex-connect) | REFERENCE | Vendor product information |

## 2. Nabto 4 / Micro legacy SDK and RPC

| Resource | Status | Value / constraints |
| --- | --- | --- |
| [nabto/nabto-cli](https://github.com/nabto/nabto-cli) | VERIFIED runtime | CLI **v1.3.0** package supplies legacy Linux x86_64 SDK used under QEMU on HAOS |
| [nabto-cli v1.3.0 release](https://github.com/nabto/nabto-cli/releases/tag/v1.3.0) | VERIFIED runtime | Source of the exact CLI/SDK package tested; SDK reports **4.9.11** |
| [nabto-cli SDK API usage](https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp) | SOURCE | Reference for SDK session, interface registration and RPC invocation |
| [nabto/nabto4-python-wrapper](https://github.com/nabto/nabto4-python-wrapper) | SOURCE | Python binding reference and SDK usage patterns |
| [nabto_client_api.h](https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h) | SOURCE | Legacy Client SDK C API declarations used to ground Python ctypes signatures |
| [nabto/nabto-client-sdk-releases](https://github.com/nabto/nabto-client-sdk-releases) | SOURCE | Public SDK release/platform availability; **native Linux ARM64 remains unverified** |
| [nabto/cordova-lsc-test](https://github.com/nabto/cordova-lsc-test) | SOURCE + VERIFIED RPC | LS Control legacy integration sample |
| [LS Control ping.json query](https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js) | SOURCE + VERIFIED RPC 17 | Read-only RPC 17 interface used in authenticated remote ping |
| [nabto/cordova-plugin-nabto](https://github.com/nabto/cordova-plugin-nabto) | SOURCE | Legacy mobile client/plugin flow; not a standalone Python ARM64 client |
| [nabto/android-client-api](https://github.com/nabto/android-client-api) | REFERENCE | Android client source; Android ARM64 is **not** generic Linux ARM64 |
| [nabto/unabto](https://github.com/nabto/unabto) | SOURCE | Legacy Micro embedded-side protocol and packet implementation |
| [protocol defines](https://github.com/nabto/unabto/blob/master/src/unabto/unabto_protocol_defines.h) | SOURCE | Protocol constants; not a drop-in end-to-end remote client |
| [packet utility definitions](https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet_util.h) | SOURCE | Legacy wire structures and parsing |
| [unabto crypto](https://github.com/nabto/unabto/blob/master/src/unabto/unabto_crypto.c) | SOURCE | Historical embedded crypto details; not a substitute for SDK |
| [uNabto query handling](https://github.com/nabto/unabto/blob/master/src/unabto/unabto_query_rw.c) | SOURCE | Query/read-write implementation reference; **only read-only operations verified** |
| [HTML device driver](https://github.com/nabto/unabto/blob/master/apps/html_device_driver/README.txt) | SOURCE | Legacy XML/RPC interface distribution context |
| [TEN025 — Writing a Nabto API client application](https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf) | SOURCE | Legacy SDK + RPC architecture reference |
| [TEN036 — Security in Nabto Solutions](https://downloads.nabto.com/assets/docs/TEN036%20Security%20in%20Nabto%20Solutions.pdf) | REFERENCE | Historic security architecture, not a modern security endorsement |
| [Micro vs Edge](https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html) | REFERENCE | Product generations are substantially incompatible |
| [LS Control ↔ Nabto partnership](https://www.nabto.com/partners/ls-control/) | REFERENCE | Vendor context |
| [Legacy client certificate registration endpoint](https://lscontrol.nabto.com/service/register) | VERIFIED during controlled account-owned test | HTTPS POST with user's account email/password and PKCS#10 CSR returned signed certificate. RSA-1024 required by *tested SDK/profile path*; verify provider compatibility and crypto risk before unattended provisioning |

## 3. Independent Nilan/Micro Nabto implementations

| Resource | Status | Value / constraints |
| --- | --- | --- |
| [HairingX/nilan_connect](https://github.com/HairingX/nilan_connect) | SOURCE | Independent Optima 270 model handling |
| [Optima 270 mapping](https://github.com/HairingX/nilan_connect/blob/main/src/nilan_connect/_optima_270.py) | SOURCE | Cross-check sensor mapping |
| [HairingX/modbus_event_connect](https://github.com/HairingX/modbus_event_connect) | SOURCE | Alternative legacy transport implementation; verify suitability for remote rendezvous separately |
| [Micro Nabto connection](https://github.com/HairingX/modbus_event_connect/blob/main/src/modbus_event_connect/micro_nabto/_connection.py) | SOURCE | Connection logic to study; **do not assume cloud compatibility** |
| [Micro Nabto wire handling](https://github.com/HairingX/modbus_event_connect/blob/main/src/modbus_event_connect/micro_nabto/_wire.py) | SOURCE | Legacy wire parsing |
| [HairingX/ha_nilan_connect](https://github.com/HairingX/ha_nilan_connect) | SOURCE | Alternative Home Assistant integration architecture |

## 4. Home Assistant apps, integrations and QEMU

| Resource | Status | Value / constraints |
| --- | --- | --- |
| [Apps and integrations](https://www.home-assistant.io/docs/apps-and-integrations/) | OFFICIAL | Distinction: an App hosts a service; an integration provides devices/entities |
| [Integration config flows](https://contributors.home-assistant.io/core/integrations/config-flow/) | OFFICIAL | UI onboarding, auth errors, unique ID, reauthentication |
| [Integration config entries](https://contributors.home-assistant.io/core/integrations/config-entries/) | OFFICIAL | Persistent connection configuration and lifecycle |
| [Apps configuration reference](https://contributors.home-assistant.io/apps/reference/configuration/) | OFFICIAL | Runtime container configuration, options and permissions |
| [App options](https://contributors.home-assistant.io/apps/guides/options/) | OFFICIAL | Supervisor options UI -> `/data/options.json`; sensitive options need protection |
| [App ingress](https://contributors.home-assistant.io/apps/guides/ingress/) | OFFICIAL | Optional authenticated web UI via Home Assistant; not inherently required if config flow handles onboarding |
| [App internal services](https://contributors.home-assistant.io/apps/) | OFFICIAL | Supervisor-managed services and connections |
| [QEMU user-mode](https://www.qemu.org/docs/master/user/) | REFERENCE + VERIFIED runtime | Linux x86_64 SDK emulation from HAOS ARM64 |
| [Home Assistant docker-base](https://github.com/home-assistant/docker-base) | SOURCE | Base image for the isolated test app |
| [App build guide](https://contributors.home-assistant.io/apps/guides/dockerfile/) | OFFICIAL | Container packaging and architecture |
| [App testing](https://contributors.home-assistant.io/apps/guides/testing/) | OFFICIAL | App testing guidance |
| [Nabto release use in independent project](https://github.com/danibram/caleon) | REFERENCE | Other project packaging approach; independent compatibility check needed |

## 5. Adjacent vendor platform (NOT assumed compatible)

- [Genvex Smart Connect Center](https://www.genvex.com/produkter/genvex-tilbehor/smart-connect-center)
- [LS SmartConnect Center](https://lscontrol.dk/products/ls-smartconnect-center/)
- [Nabto Edge embedded SDK](https://github.com/nabto/nabto-embedded-sdk)

The newer Smart Connect Center and Nabto Edge resources are **not** evidence that the older Optima 270/Micro gateway supports their interfaces. See [research notes](archive/smartconnect-center-integration-research.md).

## 6. Project-owned implementation / evidence

| Resource | Status |
| --- | --- |
| [Working facts](remote-nabto-verified-facts.md) | Canonical verified evidence, now including HAOS remote RPC 45 |
| [Research journal](archive/remote-nabto-investigation.md) | Historical investigation with more links and discarded hypotheses |
| [RPC 45 reconstruction](reconstructed-readonly-query45-2026-11-19.md) | Source-grounded candidate interface and safe read-only investigation |
| [Five-sensor validation](remote-phase1-sensor-validation-2026-11-19.md) | Remote singles and one-shot batch evidence |
| [HAOS test runtime](../haos-apps/genvex-nabto-runtime-test/DOCS.md) | Verified container, QEMU, x86_64 Python and SDK behavior |
| [Host-only HAOS batch runner](../scripts/run_haos_local_remote_stability.sh) | Two successful authenticated read-only remote sessions, zero SSH prompts |
| [Five-sensor model and tests](../experimental/genvex_remote/sensor_model.py) | Staged for second integration; not installed or wired to a worker |
| [Entity bridge plan](remote-ha-entity-plan.md) | Sensor/HA coordination and remaining secure transport work |
| [UI + automated certificate architecture](remote-ha-ui-onboarding-architecture.md) | Proposed end-user workflow, responsibilities, lifecycle and open security gates |

## 7. Critical boundaries and unanswered questions

- **SDK licensing and binary redistribution**: public download ≠ blanket redistribution permission. Evaluate before publishing prebuilt app.
- **Legacy RSA-1024**: proven compatibility in the old tested client path, weak by present-day cryptographic expectations; do not claim modern cryptographic strength.
- **Native Linux ARM64**: no validated native legacy client yet; current solution uses QEMU.
- **No completed UI onboarding/certificate lifecycle**: the registration endpoint was used successfully by a manual test, but self-service automated registration, error handling, renewal/expiry and secure secret storage are **not implemented**.
- **No unattended polling bridge**: the current v0.4.0 app does one-shot read-only test calls, not a production service.
- **No remote write support**: do not infer write safety from read-only RPC 45.
- **No transport-path attribution**: remote success alone does not prove direct P2P vs relay.

Keep account passwords, full real device IDs/hostnames, PEM certificates, private keys, key-passphrases, user identifiers from gateway responses and captures containing secrets **out of this public resource index**. Links are to public sources only.
