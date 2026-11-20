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


## 2B follow-up — catalog lookup, all known values and HA disabled entities (2026-11-20)

**User proposal:** Identify the device model from the gateway, look up the known capabilities in a catalog, read all safely supported values, and optionally expose advanced sensors as disabled Home Assistant entities (similar to Shelly).

### What the code can already tell us

**Upstream Optima 270 declares 17 datapoints** in its `_datapoints` table, and all 17 appear in `getDefaultDatapointRequest()`. **Only the five listed below are verified by this project's authenticated remote RPC45 runs.** The other **12** are legitimate *source-defined read-only candidates*, **not remotely validated**. Sources: [upstream Optima 270 model](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py); [project Phase 1 remote evidence](remote-phase1-sensor-validation-2026-11-19.md).

| Upstream key | obj | Address | Source scaling | Remote RPC45 |
| --- | ---: | ---: | --- | --- |
| TEMP_SUPPLY | 0 | 20 | (raw - 300)/10 °C | **Verified** |
| TEMP_OUTSIDE | 0 | 21 | (raw - 300)/10 °C | **Verified** |
| TEMP_EXHAUST | 0 | 22 | (raw - 300)/10 °C | **Verified** |
| TEMP_EXTRACT | 0 | 23 | (raw - 300)/10 °C | **Verified** |
| HUMIDITY | 0 | 26 | raw % | **Verified** |
| TEMP_FROSTPROTECTION | 0 | 24 | (raw - 300)/10 °C | **Candidate only** |
| DUTYCYCLE_SUPPLY | 0 | 18 | raw/100 (display unit requires checking) | **Candidate only** |
| DUTYCYCLE_EXTRACT | 0 | 19 | raw/100 (display unit requires checking) | **Candidate only** |
| RPM_SUPPLY | 0 | 35 | raw rpm | **Candidate only** |
| RPM_EXTRACT | 0 | 36 | raw rpm | **Candidate only** |
| PREHEAT_PWM | 0 | 41 | raw/100 (display unit requires checking) | **Candidate only** |
| REHEAT_PWM | 0 | 42 | raw/100 (display unit requires checking) | **Candidate only** |
| BYPASS_ACTIVE | 0 | 53 | raw; boolean semantics not yet independently verified | **Candidate only** |
| BYPASS_ANALOG | 0 | 40 | raw; units/scaling need review | **Candidate only** |
| ALARM_OPTIMA270_1 | 0 | 114 | raw alarm word; bit meanings need model-specific decoding | **Candidate only** |
| ALARM_OPTIMA270_2 | 0 | 115 | raw alarm word; bit meanings need model-specific decoding | **Candidate only** |
| ROTOR_SPEED | 0 | 50 | raw rpm | **Candidate only** |

Note: `obj=0` is the default assigned by [upstream base model](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/basemodel.py). **Do not confuse** datapoint address 42 (reheat PWM) with command/RPC **ID 42**, which is a different read-only *setpoint list* operation, still unverified remotely. The upstream Optima270 model also lists **11 default setpoint read entries**, but their remote operation and safe semantics have not yet been established. Do not enable them in the first remote expansion.

A hypothetical 17-item RPC45 request is **not** proven to work just because the five-item request worked: gateway response size, list limits, partial failures, ordering and polling cost must be validated in a separately authorized, bounded read-only test. Until then, retain the stable five-item batch.

### Device model lookup from metadata

1. Use the already source-defined/read-only **RPC 17 `ping.json`**, with an explicit metadata field allowlist (`Model`, `Devicenumber`, `SlaveDevicenumber`, `SlaveModel`, `Version`). Do not log the sensitive optional `UserNames:` field or full raw response.
2. Look up the numeric tuple in an audited model selector (source example: [GenvexNabtoModelAdapter.translateToModel](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/genvexnabto_modeladapter.py), which maps `Model=2010` and `Devicenumber=79265` to Optima270, plus other model-specific combinations).
3. Match model + applicable firmware/hardware quirks against a **reviewed** capability profile. The upstream model definitions are an excellent seed, but are not a device-reported list of remote-supported parameters.
4. If the identity tuple is unknown or cannot be independently validated, **do not choose a fallback Optima 270 profile** or query guessed addresses. Mark unsupported/unknown and request a separately reviewed model profile.

The ping metadata lookup is grounded in official [LS Control Cordova XML](https://github.com/nabto/cordova-lsc-test/blob/main/www/js/index.js), not evidence of a device-wide sensor inventory.

### Is a "largest common set of entities" a good idea?

Strictly, a catalog containing every sensor supported by **any** model is a **union** of capabilities, not a common intersection. The union is useful **internally** to share semantic names, device classes, translations and decode rules. It is **not** the set of entities to instantiate for every installation.

In the official [Home Assistant Shelly integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/shelly/entity.py), `async_setup_rpc_attribute_entities` filters declarations by actual device status keys, model, role, supported subfields and optional `removal_condition`. It registers less useful but **supported** measurements as disabled by default using entity descriptions (e.g. [Shelly sensor declarations](https://github.com/home-assistant/core/blob/dev/homeassistant/components/shelly/sensor.py)). Shelly can introspect many real reported status keys; the equivalent Nabto Micro sensor inventory is **not known**.

[HA entity registry documentation](https://contributors.home-assistant.io/core/entities/registry/) explicitly says a disabled entity remains registered but is **not active**, and an enabled entity whose live device connection fails may instead report **unavailable**. These conditions are not interchangeable. The default-enabled flag applies only when first registered; subsequent user choices must be respected. [HA's quality rules](https://contributors.home-assistant.io/core/quality-scale/entity-disabled-by-default/) recommend disabling noisy/rare diagnostic sensors at first registration, not pretending unsupported hardware exists.

**Recommended three-tier model:**

| Actual evidence | Action in HA | Rationale |
| --- | --- | --- |
| Model profile and read-only remote value **verified**, useful to most users | Create and enable by default | E.g. current five Optima 270 measurements |
| Model profile and read-only remote value **verified**, but advanced/diagnostic/noisy | Create in registry **disabled by default** | User may enable without unsupported-value surprises |
| Sensor **not supported** by the selected model/firmware, or remote capability **not verified** | **Do not create** a live entity | An inert ghost entity invites confusion; unknown is not the same as disabled |
| Supported enabled sensor fails temporarily | Keep its entity and report **unavailable** with freshness checks | Do not disable or delete transient failures |

An optional **sensor-capability catalogue in a documentation/UI preview** can show all *known potential* sensors and whether verified/supported, without creating false Home Assistant entities.

### Read all *supported* values vs enable all HA entities

**Registry disablement is not a wire-level RPC filter.** If the runtime always requests a batch of all catalog entries, it may continue contacting the device for values whose Home Assistant entities are disabled. A future scheduler needs a deliberate choice:

- Small verified group: one bounded batch may be simpler even if a few advanced HA entities are disabled; record the actual device/CPU costs.
- Larger catalog: group by verified RPC payload types, device constraints and update interval; avoid reading optional high-cost data unnecessarily; ensure HA enable/disable events do not cause unsafe adaptive range scans.
- Each individual group must have independent error/unavailable semantics so an unsupported optional measurement never invalidates the five foundational temperatures/humidity. This belongs in **3A** and a **versioned contract v2**, not a silent change to v1.

### Decision / status

**Decision proposed for the maintenance roadmap:** retain a **global semantic union catalog**, filter by **validated model capabilities**, then choose enabled/disabled **only among supported, remotely verified sensors**. A generic Micro "return all supported readings and their metadata" query remains undiscovered. This route can still produce dynamic HA entity inventories, with careful model selection and user-respecting registry defaults.

**Next evidence-gated step:** build an **offline** synthetic model-selection and planned-read manifest test, preserving all five existing keys/addresses, and prepare a separately approved read-only verification matrix for the other 12 source-defined Optima270 datapoints. Do not run a 17-item live batch, change installed Apps, query opcode 42, or send write opcode 43 without separate authorization.


## Offline executable model-selection prototype (2B follow-up)

**Implemented in experimental source only:**
- [`model_lookup.py`](../experimental/genvex_remote/model_lookup.py): takes an already-extracted RPC17 `response` object, validates just five whitelisted uint32 model/version fields, intentionally discards `UserNames:`/other fields, and applies the existing upstream **Optima270** model signature `(Model=2010, Devicenumber=79265)`.
- [`test_model_lookup.py`](../experimental/genvex_remote/test_model_lookup.py): synthetic model-selection tests for exact five verified RPC45 addresses, invalid metadata, unknown-model fail-closed behavior and no retention of account-related response fields.

The function `planned_verified_reads(...)` **returns an ordered address tuple only**, without initiating Nabto communication. This explicitly tests a safe `ping numeric metadata → source-grounded model signature → verified read-address list` planning step, **not** proof that the actual gateway has been mapped automatically in a running HAOS App. Source-derived model signatures do not validate remote capabilities by themselves.

**CI result:** [Remote Nabto offline tests](https://github.com/rabbyraptor/genvexconnect/actions/runs/44795217541) succeeded for commit `03296c65b93f1cf79e41b7847d972f68fa8697d9` (two `cryptography` versions); [formatting workflow](https://github.com/rabbyraptor/genvexconnect/actions/runs/44795217506) succeeded. These are not live-device or HA Core acceptance tests.

**Safety and next work:** First verify on a separately authorized and redacted live RPC17 response that these numeric fields map as expected; do not print, persist or transport optional account-related fields. Once model selection is reliable, plan incremental verification of the 12 model-known but remote-unverified datapoints with strict read-only gating, bounded batch sizes and separate failures. **Never create active entities for an unknown model or speculative sensor.**


## 2B next implementation milestone — catalog-based read planning

The [Optima270 expansion matrix](remote-optima270-rpc45-expansion-testmatrix.md) now identifies all **12** source-defined-but-remote-unverified RPC45 datapoints alongside the existing five verified measurements. Experimental [source-only catalog](../experimental/genvex_remote/optima270_source_only.py), [verified-only request plan](../experimental/genvex_remote/verified_read_plan.py) and [single-candidate offline-preview/opt-in test script](../scripts/probe_optima270_single_source_candidate.py) are committed as separate files. **No live RPC executed as part of the implementation.** The existing v1 snapshot, active LAN integration and HAOS Apps remain unchanged.

The request planner permits **only** the five verified source addresses in their existing order. The additional 12 remain an offline research inventory until individually approved/read-only verified. A one-candidate test harness is staged but its default mode is offline, and live mode requires separate operator approval, a bounded run and controlled credential cleanup. Do not run this probe as part of automatic HA polling or package it into the installed App.
