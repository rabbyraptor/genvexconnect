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

## Authority map

| Concern | Authoritative source now | Consumers or duplicates | Decision and next owner |
| --- | --- | --- | --- |
| Runtime shared Python modules | `experimental/genvex_remote/*.py` selected by `scripts/check_remote_runtime_parity.py` | 18 byte-identical checked-in copies in `genvex-nabto-remote/runtime/` | Keep source directory authoritative and checked-in mirror as deployment artifact; task 2 should improve the source/sync workflow **without introducing runtime imports across App packaging boundary**. |
| Five verified RPC45 reading keys, scaling and addresses | `experimental/genvex_remote/sensor_model.py` (`SENSORS`) | Mirrored `runtime/sensor_model.py`; **separate inline `SENSORS`** in `runtime/persistent_rpc45_worker.py`; `HA const.py` | Runtime model is the present executable authority. Task 3 should remove or mechanically validate independently authored register/scaling duplicates. |
| Twelve optional RPC45 keys and addresses | `experimental/genvex_remote/raw_registers_v3.py` (`OPTIONAL_REGISTERS`) | Mirrored App file; HA `const.py` `RAW_REGISTERS`; `HA raw_interpretation.py` address tuples; DEV9 release script address tuple | Treat `raw_registers_v3.py` as current runtime contract. Task 3 introduces one *reviewed* canonical catalog/projection; keep raw states and ordering stable. |
| RPC42 stage | `genvex-nabto-remote/runtime/persistent_rpc45_worker.py` read request (object 0, address 7) | App/HA v4 validators; `scripts/package_dev9_combined.py` release manifest | Read-only selected stage 0–4, **not** measured speed, RPM or flow. Task 3 should centralize the request metadata while preserving independently validated v4 envelopes. |
| Meaning and evidence of raw values | `experimental/home_assistant/custom_components/genvex_remote/raw_interpretation.py` | HA `sensor.py`; `docs/dev8-*...` historic evidence | Keep evidence distinct from hardware identity. 18/19 UI-matched display formula is `raw / 100`, not measured airflow. Other source-only candidates remain explicitly unverified. |
| Home Assistant visible entity inventory and translation keys | `experimental/home_assistant/custom_components/genvex_remote/const.py` + `sensor.py` | `strings.json`, `translations/da.json` | HA presentation owns labels, unique IDs and entity setup, *not* RPC meaning. Preserve 24 entity identities and opt-in behavior. |
| Snapshot v1 / v3 / v4 payloads | `experimental/genvex_remote/snapshot_contract.py`, `raw_registers_v3.py`, `raw_snapshot_v4.py`; mirrored App files | Independent HA-side validators `snapshot.py`, `raw_snapshot_v3.py`, `raw_snapshot_v4.py` | Explicit boundary: authoritative wire schema is runtime source; HA validates without trusting runtime. Avoid sharing unvalidated objects across process boundaries. |
| App options | `genvex-nabto-remote/config.yaml` | `runtime/app_bootstrap.py`; HA `const.py`, options flow and config flow | App manifest is installed-option source; bootstrap enforces semantics; HA selection independent. Task 4 aligns defaults, flags, compatibility checks and tests. |
| Release versions and manifest | `genvex-nabto-remote/config.yaml`; `HA manifest.json` | `scripts/package_dev9_combined.py` hardcoded versions, addresses and release name; DEV8 counterpart | Task 4/7 should derive or validate against manifest values, retain reproducible packaging and immutable DEV9 baseline. |
| CI and testing | `.github/workflows/remote-{nabto,app}-offline.yml` plus tests under `experimental/genvex_remote/`, `experimental/home_assistant/tests/`, `genvex-nabto-remote/tests/` | Dev-specific packaging and upgrade scripts | CI currently has legacy branch/path filters; task 7 should consolidate workflows and run relevant offline gates on `overnight-refactoring`. |
| Human technical status | **This file** for architecture ownership; `docs/overnight-refactoring-log.md` for sequential work and decisions | `docs/README.md`, `docs/STATUS.md`, older maintenance plan (several still state DEV8/DEV2) | Task 5 corrects current status entry points and labels historical DEV docs as historical; avoid treating archived gates as live baseline. |

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
