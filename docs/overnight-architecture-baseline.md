# DEV9 architecture baseline and source-of-truth decisions

**Status:** Decision record for `overnight-refactoring`, task 1 (2026-11-23).  
**Immutable comparison baseline:** `e0f2f46214a0561515f7bb4fda5841e481b3abbe`.  
**Scope:** Experimental *remote* path only. The existing LAN integration at `custom_components/genvex_connect/` is intentionally out of scope.

This document is the authoritative **architecture/ownership map** for the overnight branch. It does *not* replace executable contracts. Later tasks must update this map if they change ownership.

## Current production-shaped data path

```text
Genvex Optima 270
  ↕ encrypted Nabto Micro / legacy SDK (x86_64 under QEMU)
genvex-nabto-remote/runtime/persistent_rpc45_worker.py
  ├─ RPC45: 5 verified scaled readings + 12 optional raw candidates
  └─ RPC42: object 0, address 7, selected ventilation stage 0–4
  ↕ private worker framing / persistent SDK adapter
genvex-nabto-remote/runtime/{raw_registers_v3,raw_snapshot_v4,
  raw_snapshot_state_v4,snapshot_api_v4,...}.py
  ↕ authenticated read-only App HTTP IPC; /v1, /v3, /v4 snapshots
experimental/home_assistant/custom_components/genvex_remote/
  runtime_client.py → coordinator.py → snapshot/raw_snapshot_v3/raw_snapshot_v4.py
  → const.py, raw_interpretation.py, sensor.py
  ↳ 5 scaled + 17 raw RPC45 + 1 data-age + 1 RPC42 stage = 24 entities
```

The App/HA boundary is a *serialized snapshot contract*, not an in-process import. Preserve independent input validation and the private IPC boundary.

## Authority map (updated after tasks 2–4)

| Concern | Authoritative source now | Consumers or duplicates | Decision and next owner |
| --- | --- | --- | --- |
| Runtime shared Python modules | `experimental/genvex_remote/*.py` + `scripts/check_remote_runtime_parity.py` | Checked-in App runtime mirrors and HA copy of `register_catalog.py` | The checker now enforces byte-identical source/App/HA register catalog, and preserves App-only worker/bootstrap modules. |
| Five verified RPC45 reading keys, scaling and addresses | `experimental/genvex_remote/register_catalog.py` (`RPC45_BASELINE`) | `sensor_model.py` and App mirror project `SensorSpec`; worker's legacy tuple and HA `const.py` derive from the same specs | Five keys, addresses, scaling/units and stable sensor IDs are unchanged. The worker has no separate handwritten baseline list. |
| Twelve optional RPC45 keys and addresses | `experimental/genvex_remote/register_catalog.py` (`RPC45_OPTIONAL`) | `raw_registers_v3.py`, HA `const.py`, HA evidence module and DEV9 packaging | Ordering and raw signed-int16 contract remain identical; runtime/App mirror and HA catalog projection are checked. |
| RPC42 stage | `register_catalog.py` (`RPC42_FAN_LEVEL`, read-only object 0/address 7/range 0–4) | App worker RPC42 request and decoder; HA fan sensor metadata; package manifest | Independent v4 input validators continue to enforce the range and protocol boundary; no writes added. |
| Meaning and evidence of raw values | `register_catalog.py` (evidence category, provisional notes, optional source-display divisor) | HA `raw_interpretation.py` renders attributes; raw sensor stays unitless | Fan 18/19 display conversion remains `raw / 100` without physical airflow claims; other source-only entries remain explicitly unverified. |
| Home Assistant visible entity inventory and translation keys | `experimental/home_assistant/custom_components/genvex_remote/const.py` + `sensor.py` | `strings.json`, `translations/da.json` | HA presentation owns labels, unique IDs and entity setup, *not* RPC meaning. Preserve 24 entity identities and opt-in behavior. |
| Snapshot v1 / v3 / v4 payloads | `experimental/genvex_remote/snapshot_contract.py`, `raw_registers_v3.py`, `raw_snapshot_v4.py`; mirrored App files | Independent HA-side validators `snapshot.py`, `raw_snapshot_v3.py`, `raw_snapshot_v4.py` | Explicit boundary: authoritative wire schema is runtime source; HA validates without trusting runtime. Avoid sharing unvalidated objects across process boundaries. |
| App options | `genvex-nabto-remote/config.yaml` for installed defaults and schema; App bootstrap enforces runtime dependencies | `app_bootstrap.APP_DEFAULTS` is a checked projection; HA `pairing_options.py` selects its own opt-in | `scripts/check_remote_contracts.py` and CI reject default/schema drift. Manual and automatic pairing both retain fan v4 and imply raw v3; App still requires persistent mode. |
| Release versions and manifest | App `config.yaml` and HA `manifest.json` individually own their installed versions; catalog owns RPC inventory | `scripts/package_dev9_combined.py` derives versions, RPC45 list and RPC42 stage from those authorities | DEV9 archive filename and release tag remain pinned for this release; deterministic manifest/hash verification retained. |
| CI and testing | `.github/workflows/remote-{nabto,app}-offline.yml`, test modules, parity checker and configuration gate | Source/App/HA offline contracts and combined release packaging | Workflows include `overnight-refactoring`; new tests lock RPC45 URL payload, register catalog order/evidence, v3/v4 snapshot projection and both pairing modes. |
| Human technical status | **This file** for architecture ownership; `docs/overnight-refactoring-log.md` for sequential work and decisions | `docs/README.md`, `docs/STATUS.md`, older maintenance plan (several still state DEV8/DEV2) | Task 5 corrects current status entry points and labels historical DEV docs as historical; avoid treating archived gates as live baseline. |

## Micro Nabto protocol library (task 3 extension, 2026-11-23)

The same authoritative, import-free `experimental/genvex_remote/register_catalog.py` now holds the **known protocol operation catalog**, not just current sensor addresses: 2 KEEP_ALIVE; 17 PING; 42 SETPOINT_READLIST; 43 SETPOINT_WRITELIST; 45 DATAPOINT_READLIST. This is a bounded, source-audited inventory, **not a claim of complete proprietary Nabto coverage**.

The `optima270` `ModelProfile` groups all 17 RPC45 datapoints, 12 active RPC42/RPC43 read/write setpoint-address pairs, and nine explicitly inactive source-model pairs. The lookup API `get_micro_command`, `get_model`, `get_model_register`, `get_model_setpoint` always namespaces a register by **model, RPC opcode, object and address**. The CLI `scripts/lookup_micro_nabto.py` is entirely local and displays JSON; it cannot transmit commands. All remote writes remain unverified and disabled. Evidence is crosschecked against `docs/references/optima270_micro_nabto_setpoint_catalog.json`; see [protocol library guide](micro-nabto-protocol-library.md) for exact semantics and adding models.

The two shipping copies of the catalog are still byte-identical projections, enforced by `scripts/check_remote_runtime_parity.py`. Neither snapshot validators nor existing read-only pollers need any new transport operation. The model profile is structured for adding independent future controller catalogs without mixing address namespaces or claiming source-only writes have been verified.

## Verified structural observations in baseline

- Git tree contains **400 files**; 23 App runtime Python files. Of these, **18** have corresponding files with identical Git blob SHA in `experimental/genvex_remote/`; the other five are intentionally App-only. This is *managed mirroring*, not 18 unrelated forks.
- `scripts/check_remote_runtime_parity.py` already defines the source path and App-only exclusion set and supports `--check` / `--sync`. `scripts/package_dev9_combined.py` already rejects mirror drift. Reuse these checks.
- Additional **semantic** duplication exists across four layers: the worker's inline five-register specification; `raw_registers_v3.py`; HA `const.py` and `raw_interpretation.py`; and DEV9 release metadata. Their differing responsibilities need a boundary-conscious catalog rather than blind import deduplication.
- There are **106 Python test modules** across three directories (57 experimental source, 28 App, 21 HA); this is an inventory count, **not** a fresh test-run result.
- Legacy/dev draft modules and documentation remain in the tree. Evaluate imports and package allowlists before removal; a filename containing `v2_draft` or `dev8` does not alone prove dead code.
- `docs/README.md` still describes DEV8 (23 entities); `docs/STATUS.md` describes DEV2-era installation. These are **stale documentation**, not a reason to regress the tested DEV9 implementation.

## Refactoring sequencing / conflict rules

1. **Task 1 — architecture:** establish ownership and explicitly list real drift sources; no runtime behavior changes.
2. **Task 2 — structural refactor:** simplify internal APIs/duplication without changing contracts, sensor IDs, read order, authentication, flags or subprocess lifetime. Keep App runtime mirror synced.
3. **Task 3 — register model:** implement one canonical source of register *facts* and deterministic projections at runtime and HA packaging boundaries; independent transport-facing validators remain. Verify that all 17 RPC45 and RPC42 metadata match DEV9.
4. **Task 4 — config/version:** unify declared defaults and validate feature dependencies across App, HA options and packaging; preserve upgrade compatibility.
5. **Task 5 — docs:** replace obsolete current-status claims with verified DEV9 capabilities and link this record and task log.
6. **Task 6 — lifecycle:** audit bounded errors, cancellation and cleanup while preserving successful persistent reuse. No requested live probing.
7. **Task 7 — delivery:** consolidate DEV-specific runners and add offline CI coverage for the branch; no implicit HAOS deployment.

## Invariants for every change

- Do not touch `custom_components/genvex_connect/` (original LAN integration).
- Preserve stable five measurement keys, scaling, entity unique IDs and snapshot v1 compatibility.
- Preserve optional 17 raw signed-int16 RPC45 values and their evidence categories; do not fabricate missing values or reinterpret raw alarm/rotor/hardware statuses.
- Preserve v4 RPC42 selected stage (integer 0–4 or unavailable/null), RPC45 bracketing, and independently validated v4 snapshots.
- Preserve token authentication, automatic pairing, persistent SDK-process reuse and read-only behavior.
- Code changes require appropriate offline/isolated tests and commits before the next task; no HAOS modifications, SDK live probes or network-based device tests.

## Assessment limits

This task established structure from Git tree, source contents, blob identity, manifests and offline gate definitions. It did not execute the code or tests. Future stages must record real test results rather than extrapolate them from existing CI configuration.

## Implementation after tasks 2–4

- **Task 2:** shared v1/v3 snapshot projection for both v3/v4 cache paths, unified HA device metadata and coordinator payload shaping, and one RPC45 URL encoder shared by required/optional reads. The request content, decoding/scaling, entity identity and SDK lifecycle were not changed.
- **Task 3:** `experimental/genvex_remote/register_catalog.py` owns all 17 RPC45 address/key/label/evidence facts and the single verified RPC42 stage read. Identical packaging projections are checked in App runtime and HA integration by `scripts/check_remote_runtime_parity.py --check`. The App/HA snapshot validators intentionally remain independent at the HTTP trust boundary.
- **Task 4:** App `config.yaml` and HA `manifest.json` own versions and installed defaults. Bootstrap has checked Python defaults, the release packager derives version and RPC inventory, and `scripts/check_remote_contracts.py` enforces these interfaces. HA manual-token options now retain `fan_level_v4` instead of silently discarding it.
- The original DEV9 baseline file count and duplicate observations above remain historical measurements taken **before** these changes; use the work log and a commit comparison for current statistics. Documentation consolidation across other current-status files belongs to task 5.
