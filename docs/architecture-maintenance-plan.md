# Maintenance and architecture plan — Genvex Connect / HAOS

**Created:** 2026-11-20  
**Branch:** `remote-nabto-connection`  
**Scope:** Experimental Remote App, experimental HA integration, source-level research and packaging only.  
**Status:** Approved roadmap; individual tasks may be researched and tested offline without activating new gateway requests or migrating real credentials.

## Non-negotiable isolation rules

- **2C — Existing LAN integration is protected.** No edits to `custom_components/genvex_connect/`, its configuration, dependent `genvexnabto==1.5.4` library, established entities, or a running LAN installation. The sole exception is a strictly necessary change, explicitly assessed and separately approved *before* implementation. Read-only source inspection is allowed.
- Preserve the running `local_genvex_nabto_runtime_test` v0.5.0 App and its pre-existing encrypted Nabto profile. Do not start, stop, reinstall, rebuild, or alter it as part of this roadmap.
- The experimental `local_genvex_nabto_remote` v0.1.0-dev1 remains stopped and manual-boot after the successful F2.5 diagnostic mount attestation. No live polling, new CA enrollment, real credential import or arbitrary Nabto RPC calls without separate operator approval.
- Prefer offline source inspection, synthetic fixtures, local unit tests and explicitly read-only code changes; never commit keys, tokens, identifying account/device values, private app captures or proprietary binary artifacts.
- Each implementation step must have focused tests, clear source-of-truth ownership, documented compatibility implications and an independently reversible deployment plan. Existing entity unique IDs and the current validated five-reading RPC contract remain stable until a versioned migration is reviewed.

## Priority register

| ID | Topic | Priority / phase | Required outcome | State |
| --- | --- | --- | --- | --- |
| **2A** | Canonical sensor + capability model | Critical / now | Typed, source-grounded catalog; no App/HA change until v2 contract | **Offline prototype + CI PASS; adoption pending** |
| **2B** | Read-all / metadata / discovery Nabto RPC research | Critical / now | Distinguish known-address RPC45 batching from ping metadata and true device enumeration | **Offline research + safe model-lookup prototype; enumeration remains unproven** |
| **2C** | Protect working LAN integration | Permanent prohibition | No source/config/deployment modifications without separate strict-necessity approval | **Enforced** |
| **2D** | Private profile and credentials consolidation | Critical / review now | Reconcile three existing offline mechanisms; verify copy-only, safe no-clobber, crash recovery, permissions, secret lifecycle and single production entry point | Planned |
| **2E** | Automate shared-runtime packaging | High / now | Single authoritative Python source, reproducible App packaging, CI parity and contract checks | Planned |
| **3A** | Polling, freshness and internal dataflow | Critical / research now | Clarify App vs HA 60-s clocks, latency, TTL, errors/retries, per-group atomicity and unavailable semantics | Planned |
| **3B** | IPC authentication and token lifecycle | High / research now | Secure per-install provision, delivery, storage and rotation, endpoint scope and trust boundary; no user token copy/paste in final UX | Planned |
| **3C** | LAN/Remote entity identity and duplicates | Later | Stable device/entity IDs, coexistence and future migration without breaking HA history/automations | Deferred |
| **4** | Unified transport/domain architecture | Later target | Adapter boundary for LAN and remote, shared capability contract only when justified by actual multi-model evidence | Deferred |
| **5A** | Documentation hygiene | High / now | One architecture/status index; distinguish tested, installed, experimental, historical; identify and retire outdated instructions | Planned |
| **5B** | Build/licensing/distribution | High / before production | Pin/check SDK downloads and image dependencies; resolve proprietary SDK redistribution, performance and QEMU deployment | Before release |
| **5C** | Regression, CI and lifecycle tests | High / continuous | Offline contract/model tests, HA Core import/flow/entities test, recovery/restart/soak/resource tests | Continuous |

## Execution sequence and gates

### Stage 1 — Discovery and model foundation (2B → 2A + initial 5A)
1. Inspect existing official Nabto 4/Micro, LS Control and project source only. Identify whether the system can (a) fetch a batch of **known** addresses, (b) discover the set of **supported** addresses, (c) report firmware/model/interface information, and (d) discover **reachable gateway identifiers**. These are four different capabilities.
2. Record the evidence status of each operation: observed live, source-defined only, convention/demo only, or unknown. No guessed query IDs, address-range scans, write opcodes, live probes, or SDK invocations during source investigation.
3. Build an offline, transport-neutral, **source-grounded** starter catalog for the five already verified Optima 270 readings, with semantic keys, obj/address, scaling, type, unit and proof status. Keep it outside active integration/runtime packages. Verify by unit tests with synthetic samples and an explicit compatibility mapping to existing five snapshot keys.
4. Only add other models/readings after examining authentic source definitions and validating their read-only availability. Do not manufacture entities for unverified addresses.

**Stage 1 acceptance:** A written 2B result with links and uncertainty; standalone 2A catalog + passing offline tests; no active integration/App changes.

### Stage 2 — Data contract and polling (3A)
Design a versioned contract for numeric, boolean, enum and diagnostic readings with per-group success/availability and timestamps. Preserve the *current* strict five-numeric schema v1 until a separate v2 contract and backward-compatibility tests are ready. Review App polling vs Home Assistant coordinator timing and staleness.

### Stage 3 — Source/build automation (2E + 5C)
Choose a single canonical runtime package and machine-generated App copies; fail CI on drift. Avoid broad structural rewrites of running components.

### Stage 4 — Credential and IPC safety (2D + 3B)
Review existing `profile_provision.py`, `profile_store.py`, `remote_profile_atomic_prototype.py` and runtime bootstrap. Produce one audited import/rotation workflow plus explicit App↔HA authentication/token lifecycle. **Real keys and live enrollment remain separately gated.**

### Stage 5 — Documentation and acceptance (5A + 5C)
Resolve current vs archived guidance, test in isolated fake-data contexts, and document status and outstanding risks. Only then resume the ongoing F2.6 remote provisioning work and live-runtime development with separate permissions.

### Deferred design constraints (3C + 4)
Preserve space for physical device identity across transports, model/capability-specific adapters and stable HA entity IDs. Do not merge or refactor the working LAN integration.

## Current verified baseline (not newly retested by this plan)

- The isolated HAOS x86_64/QEMU legacy Nabto SDK has successfully performed **read-only RPC 45** with exactly five known Optima 270 addresses (20, 21, 22, 23, 26). A batch of known addresses is **not** an enumeration of capabilities.
- Separate authenticated App-to-container HTTP tests, offline runtime/source tests and F2.5's private `/data` mount verification have passed as recorded in the existing development documents.
- The new `genvex_remote` HA integration is still an experimental scaffold, not an installed production integration.
- See [verified facts](remote-nabto-verified-facts.md), [phase-one sensor validation](remote-phase1-sensor-validation-2026-11-19.md), [F2 private profile design](remote-phase-f2-private-profile-design.md) and [HA entity plan](remote-ha-entity-plan.md). Older documents may contain superseded milestone descriptions.

## Task completion ledger

Update this section as tasks finish; a committed plan or passing synthetic tests alone is not permission to change installed Apps.

| Task | Completion evidence | Outstanding gates |
| --- | --- | --- |
| 2B | [Research and Shelly comparison](remote-device-discovery-2b.md), [offline model selector](../experimental/genvex_remote/model_lookup.py), [synthetic tests](../experimental/genvex_remote/test_model_lookup.py), [CI PASS](https://github.com/rabbyraptor/genvexconnect/actions/runs/44795217541). Upstream Optima270 model declares 17 read-only datapoints; just 5 are remotely verified | Live model signature validation, authorized incremental verification of 12 source-defined candidates, and original manufacturer enumeration interface (if one exists) remain pending; never scan |
| 2A | [Typed prototype](../experimental/genvex_remote/capability_catalog.py) and [tests](../experimental/genvex_remote/test_capability_catalog.py); [GitHub Actions run #64](https://github.com/rabbyraptor/genvexconnect/actions/runs/44791766493) passed with both cryptography versions | Single canonical source adoption, v2 multi-type contract, model validation and actual HA Core entity generation |
