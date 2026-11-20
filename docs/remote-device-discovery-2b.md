# 2B — Does Nabto Micro expose "read all" / device capability discovery?

**Date:** 2026-11-20  
**Scope:** Offline research on the legacy Nabto 4/Micro **LS Control / Genvex Connect Optima 270** remote path.  
**Result:** A source-defined **multi-address read of known datapoints exists and is live-verified** (RPC 45). **No trustworthy universal device-side sensor enumeration or "give me all datapoint descriptions" RPC has been identified** for this gateway. Absence of evidence is *not* proof the gateway cannot implement such a query.  
**Safety:** No Nabto sessions, App starts, register probes, credential operations or controller modifications were performed for this research.

## What "get all info" could mean

| Capability | Evidence | Status for Optima 270 |
| --- | --- | --- |
| Find reachable device IDs on local network | Legacy SDK `getLocalDevices` and UDP discovery in source | Supported for finding *gateways*; **not** a sensor directory |
| Read **metadata about a device** | LS Control's authentic `ping.json` RPC ID **17** returns `Devicenumber`, `Model`, `Version`, `SlaveDevicenumber`, `SlaveModel`, `Pong` (and potentially account-related `UserNames:`) | RPC 17 already tested remotely; metadata schema is **source-verified**, but automatic model inference has **not** been separately validated against the live gateway's reported numeric fields |
| Read **many selected current values in one call** | LAN source `DATAPOINT_READLIST` opcode **45**, plus project-reconstructed RPC 45 and independent authenticated five-address batch | **Verified** for exactly `(obj=0, address)=(0,20),(0,21),(0,22),(0,23),(0,26)` |
| **Enumerate all supported datapoint names, addresses, scales and types** | No authentic manufacturer query or universal Nabto Micro introspection API found in reviewed official SDK/docs and public LS Control code | **Unknown / not demonstrated** |
| Read **interface ID/version** | Nabto CLI optional `get_interface_info.json` strict-interface convention | Can return interface identification on *implementations that provide it*; **not** a sensor list; **not demonstrated** on this gateway |
| Read `get_public_device_info.json` | Public Nabto generic demo RPC | **Demo-only example**, not evidence of an LS Control query; no device invocation authorized |

## Verified source details

### A. Nabto 4/Micro does not automatically enumerate RPCs

[Nabto TEN025, sections 5.2 and 6](https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf) documents a **client-supplied** XML RPC interface (historically `unabto_queries.xml`): each named query has a numeric opcode and typed request/response parameters. Client code installs it with `nabtoRpcSetDefaultInterface` / `nabtoRpcSetInterface` before `nabtoRpcInvoke`. This is the manufacturer's client model, **not** a remotely enumerated list of all controller parameters. More recent clients generally bundle their own interface rather than relying on a central HTML Device Driver download.

Official [Cordova Nabto plugin](https://github.com/nabto/cordova-plugin-nabto) documents the same interface initialization and has a separate local-device discovery function. Nabto Edge/5 documentation is **not** a valid replacement API for the incompatible legacy Micro client.

### B. LS Control supplies device identity metadata, not sensor enumeration, in its public ping

The official [Nabto/LS Control Cordova test source](https://github.com/nabto/cordova-lsc-test/blob/main/www/js/index.js) provides this authentic XML query:

- `ping.json`, numeric ID **17**, request `ping:uint32`
- Response: `Pong:uint32`, `Devicenumber:uint32`, `Model:uint32`, `Version:uint32`, `SlaveDevicenumber:uint32`, `SlaveModel:uint32` and `UserNames::raw`

**Do not log or expose the `UserNames:` field**: it can contain account-related information. Whitelist strictly necessary numeric metadata if a future dedicated implementation uses it.

The upstream [GenvexNabto model adapter](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/genvexnabto_modeladapter.py) already selects models using combinations of these numeric fields. Its known Optima 270 case is `Model == 2010` and `Devicenumber == 79265`. This selection rule is **source-derived** and must still be checked against an approved, safely redacted live metadata record before enabling automatic Remote model selection.

`ping.json` does **not** return the controller's list of supported datapoints.

### C. RPC45 can batch *known* addresses

Public [GenvexNabto read-list source](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/cmd_datapoint_readlist.py) encodes an explicit list of `obj:uint8` and `address:uint32` values, with the request count and trailing byte. The library builds the list from preselected model definitions; it does not solicit a directory of valid addresses. The project reconstructed a compatible read-only RPC45 schema and verified one successful five-value remote batch on x86_64 and ARM64/QEMU. See [phase-one validation](remote-phase1-sensor-validation-2026-11-19.md).

The upstream [Optima270 model mapping](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py) declares *additional* datapoints, but their remote RPC45 availability, batching limits, data semantics and controller firmware applicability are **not yet independently verified** by this project. **Never treat a model entry as authorization to scan all addresses or auto-enable entities.**

The same upstream library defines read-only setpoint-list opcode **42**, but its remote support is unverified, and **write opcode 43 must not be called**.

### D. The interface-info probe did not discover introspection

The project's earlier isolated `get_interface_info.json` probe returned status 26, with JSON event **2000027 = QUERY_MODEL_NO_SUCH_REQUEST**. The client had only registered `ping.json`; the missing query was rejected by the local query-model lookup. This **does not demonstrate an unsupported device query** and does not mean the controller received it.

In the official [nabto-cli source](https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp), `get_interface_info.json` is used for *optional strict checking* against `interface_id` and `interface_version_{major,minor}`, not to retrieve a list of query names or sensors. See [archived diagnostic](archive/remote-interface-info-probe-2026-11-19.md).

### E. Other generic Nabto examples are not LS Control capabilities

The [Nabto CLI demo](https://github.com/nabto/nabto-cli) uses `get_public_device_info.json` on Nabto's separate demonstration firmware. No authentic Optima 270 `get_public_device_info.json` query definition has been recovered. Do not invoke this or other demo query IDs blindly.

## Architectural consequence for HA dynamic entities

There are **two different forms** of dynamic configuration:

1. **Safe near-term option: dynamically instantiate HA entities from a trusted, model-specific catalog.** Only expose sensor entries whose exact address, scaling, type and read-only remote status are supported by evidence. A securely validated source-based `ping.json` model selector can help choose the catalog after a separate approved check. Unknown models must fail closed; never fall back to Optima 270 addresses.
2. **Later, if discovered and verified: device-reported capability inventory.** Parse only an authenticated, documented, bounded, typed and versioned response, then intersect with a reviewed allowlist. Never create writable controls or arbitrary entities from opaque untrusted remote keys.

Because no general remote sensor-directory query is established, **option 1 is the proposed foundation**. Automatic entity creation does not require device-side enumeration: the HA integration can create entities from the selected catalog and verified capability flags.

The current **strict five-reading snapshot v1** remains unchanged. Before adding boolean/enum/alarm groups, design and test an explicit versioned contract (maintenance plan 3A); a partial response must not masquerade as current data.

## Next non-invasive 2B evidence path

- Inspect an **authorized, authentic** Genvex Connect APK/IPA's static JS/XML assets or a legitimate historical LS Control HTML Device Driver package using the existing bounded offline [resource inspector](../scripts/inspect_nabto_resources.py). No unknown binaries uploaded to GitHub or run on HAOS.
- Ask LS Control for their supported, **read-only** Micro Nabto RPC query definitions and whether a device-supported capability inventory exists; distinguish device identity/firmware from sensor enumeration.
- Build a static mapping between whitelisted numeric `ping.json` fields and verified catalog profiles. Do not send a new live query until individually approved.
- Confirm whether particular *source-defined* additional read-only datapoints work, one by one, in a separate operator-approved test phase; no register-range scanning, setpoint writes or automatic discovery claims.

## Outcome and decision

**2B offline research: initial classification complete; sensor inventory capability remains unknown.** Continue 2A with an explicit typed model catalog using the five already verified Optima 270 values. The actual capability-discovery branch stays an open evidence-gated research item.
