# Overnight v2 — independent review of all eight tasks

**Audit date:** 23 November 2026  
**Current code:** [overnight-v2](https://github.com/rabbyraptor/genvexconnect/tree/overnight-v2)  
**Branch parent:** `overnight-refactoring` at `ed166488361f04d23816cef38fd3c2ea46ed760b`  
**Frozen v2 statistics checkpoint:** `66b31f2de3b3dd08911ddb1ff72c4aff060ad731`  
**Original hardware baseline:** DEV9 `e0f2f46214a0561515f7bb4fda5841e481b3abbe`

## Executive result

All eight v1 workstreams were reviewed against the actual v1 branch, source code, documentation, tested CLI/HA contracts, public Marketplace requirements and GitHub CI evidence.

The v2 changes correct actual regression risks and mistakes introduced or missed in v1: unowned duplicate sensor icon/name tables, model-nonspecific metadata lookup, missing tests for a second model, incorrect HA manifest repository links, stale HACS installation terminology, a missing Marketplace distribution boundary and absent automatic v2 CI triggers.

The working DEV9 installation is unchanged; **no live HAOS deployment or hardware validation** is claimed for v2.

## Eight-workstream audit and impact

| Original task | V2 result | What was inspected and corrected | Impact |
| --- | --- | --- | --- |
| **1. Architecture and single source of truth** | **Complete** | Moved all 17 semantic icon mappings and the 12 optional English register names directly onto canonical `RPC45Register` entries. The former exported icon/name dictionaries are now derived projections. Checked byte-identical canonical/App/HA mirrors. | Register address, meaning, presentation and provenance now have one authored owner, also for future models |
| **2. Structural code refactoring** | **Complete** | Rechecked shared RPC45 encoding, v1/v3/v4 snapshot projections, HA entity identity and per-user translations; updated coordinator typing to `dict[str, float | int]` because raw registers and fan levels are integers. | Clearer API contract without a wire protocol or entity-ID change |
| **3. Command and model catalog** | **Complete** | Added model-aware `rpc45_default_icon(key, model_key=...)` and `rpc45_translation_key(model_key, key)`; enforced duplicate-address/key validation, matching model IDs, non-empty language labels, `mdi:` icons and valid addresses. Verified a synthetic second model can reuse an Optima 270 address/key with different metadata; unverified writes remain disabled. | Prevents cross-model icon/name contamination while preserving 24 existing DEV9 sensor keys |
| **4. Configuration and versions** | **Complete** | Fixed `genvex_remote/manifest.json` `documentation` and `issue_tracker` URLs pointing to an obsolete repository; release contract now checks their expected repository/path. Existing App and HA versions remain manifest-owned. | Wrong repository links now fail the offline release gate |
| **5. Documentation and cleanup** | **Complete** | Updated README, docs index/status, HA and script guides for Home Assistant **Marketplace** on HA 2026.11+. Original v1 report is clearly marked historical; the old technical identifiers `hacs.json` and `hacs/action` remain correctly named where used. | Current installation and distribution terminology is accurate without erasing dated evidence |
| **6. Robustness and error handling** | **Complete (reviewed)** | Re-reviewed canceled/terminated worker handling, session reuse, strict snapshot schemas, 0-vs-null fan stages and fail-safe cache invalidation. Added invalid-model/missing-icon negative tests; existing worker and polling failure tests remain. No ungrounded live behavior changes. | More rigorous fail-closed source metadata, while existing runtime recovery contracts remain tested |
| **7. Release and installation** | **Partially resolved** | Added `scripts/check_marketplace_scope.py` to the unified release gate; updated both App/Remote workflows to run on `overnight-v2`; renamed the historical action's visible workflow to *Marketplace repository validation* without changing its supported `hacs/action` implementation. | Source archives and Marketplace LAN-vs-Remote boundaries are checked; public Marketplace repository settings, proprietary SDK distribution and live release are still outside this branch |
| **8. Integration, tests and final report** | **Complete** | Verified current CI and the DEV9→v2/overnight→v2 commit comparisons; saved this report and the [v2 change log](overnight-v2-log.md). | Auditable handoff with actual metrics and remaining release limits |

## Precise v2 change size at frozen checkpoint

GitHub compare API: `ed166488… → 66b31f2d…`

| Metric | v2 relative to overnight v1 |
| --- | ---: |
| Commits | **31** |
| Files touched | **22** |
| New files | **2** |
| Modified files | **20** |
| Deleted files | **0** |
| Lines added | **432** |
| Lines removed | **198** |
| Net lines | **+234** |

For complete project context, compare `e0f2f462… → 66b31f2d…` gives **128 commits**, **57 touched files**, **20 new**, **37 modified**, **+3,762 / −536 lines** and **net +3,226 lines**. These are Git file/line counts, *not* counts of eliminated duplicated logic, nor claims of runtime performance improvements.

The report and subsequent log finalization commits are intentionally **excluded** from these frozen checkpoint metrics; use a fresh GitHub compare for continuously updated head statistics.

## Automated verification, with evidence

**Post-code checkpoint** `94e4e5a7…` (all code changes included; subsequent commits were docs only):

- [App offline candidate — run 45099966326](https://github.com/rabbyraptor/genvexconnect/actions/runs/45099966326): **SUCCESS**, 190 App tests and 148 HA tests, combined DEV9 archive (49 members) and SHA256 verification, manifest/version/default checks, code mirror parity and sensor localization checks.
- [Remote Nabto offline — run 45099966406](https://github.com/rabbyraptor/genvexconnect/actions/runs/45099966406): **SUCCESS** for cryptography 46.0.4 and 47.0.0, each with 365 source tests plus 148 HA tests, including synthetic second model and negative metadata checks.
- Formatting and hassfest: **SUCCESS** at the same source checkpoint.
- `scripts/remote_release_gate.py --check`: includes project link/Marketplace ownership, source mirrors, App/HA options and EN/DA translations. `--package` also verifies deterministic DEV9 combined archive and SHA256.
- HACS legacy technical-name validator: renamed in display to **Marketplace repository validation**, but continues to fail on **repository Issues disabled** and **no valid GitHub topics**. These are real metadata limitations and do not invalidate the offline source/HA tests.

### Verified Marketplace distinction

Home Assistant's current developer documentation states the Marketplace is built in beginning with **2026.11** and still uses the legacy publishing metadata `hacs.json` and `hacs/action`. The Marketplace integration layout is **one HA integration per repository**. The root `custom_components/genvex_connect` remains the LAN package. The separate `experimental/home_assistant/custom_components/genvex_remote` + HAOS App are not made publicly installable simply by passing the legacy-named validator.

Official sources:
- https://contributors.home-assistant.io/marketplace/how-it-works/
- https://contributors.home-assistant.io/marketplace/reference/repository-structure/
- https://contributors.home-assistant.io/glossary/hacs/

## Outstanding work and boundaries

1. **Public Marketplace repository metadata:** GitHub Issues are disabled and repository topics empty. Changing them is a **repository-wide administrative change**, not a modification confined to `overnight-v2`; left pending instead of changing settings shared with `main`.
2. **Remote App distribution:** the legacy proprietary Nabto Micro SDK has separate redistribution and binary platform constraints. The current tests create **source release archives**, not a publicly approved and verified SDK distribution.
3. **HAOS upgrade/acceptance:** `overnight-v2` was not installed on live HAOS. Releasing requires an intentional App + integration update and separate on-device verification, not an inferred result from source-only CI.
4. **Future controllers:** the library is model-extendable and the translation generation supports independent model metadata; the live HA integration still targets the tested Optima 270 only. Adding another controller needs real device verification, updated model selection and an explicit entity/runtime registration path.
5. **Unverified writes:** source-known RPC43 read/write setpoint address pairs are metadata only. There are no enabled write calls, and source-model interpretations do not establish installed hardware.

## Reproduction / developer entry points

```bash
python scripts/check_remote_runtime_parity.py --check
python scripts/sync_remote_entity_localizations.py --check
python scripts/check_remote_contracts.py
python scripts/check_marketplace_scope.py
python scripts/remote_release_gate.py --check
python scripts/remote_release_gate.py --package
```

Code and history:
- [v2 work log](overnight-v2-log.md)
- [Source ownership map](overnight-architecture-baseline.md)
- [Micro Nabto command and register lookup](micro-nabto-protocol-library.md)
- [v1 historical report](overnight-refactoring-report.md)

**Conclusion:** The v2 branch has materially reduced future multi-model and localization drift risk and corrected distribution/documentation errors without changing read-only DEV9 behavior. All testable source workstreams were reverified. Public repository/SDK publication and live acceptance remain explicitly partial.
