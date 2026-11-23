# Overnight refactoring — consolidated delivery report

**Audit checkpoint:** `79b91632e7e7f735672df6afa6903805ef68ade2`, 23 November 2026.  
**Branch:** `overnight-refactoring` ([GitHub](https://github.com/rabbyraptor/genvexconnect/tree/overnight-refactoring))  
**Immutable before-state:** DEV9 `e0f2f46214a0561515f7bb4fda5841e481b3abbe`.  
**Deployment:** Source/CI only. The working DEV9 HAOS installation was **not** replaced or tested live with these refactoring commits.

## Task-by-task outcome

| Task | Outcome | Concrete work | Practical effect |
| --- | --- | --- | --- |
| 1. Architecture / Single Source of Truth | **Complete** | Reviewed 400-file DEV9 baseline, App/HA boundaries, 18 managed runtime mirrors, schemas, sensors and delivery gates; created `docs/overnight-architecture-baseline.md` | Clear authority boundaries; avoids refactoring purposeful App copies into broken imports |
| 2. Active-code refactoring | **Complete** | Shared v1/v3 snapshot projections, HA device registration, RPC45 request encoding, coordinator v1/v3/v4 mapping | Less repeated execution logic; preserving HTTP trust boundary, SDK lifecycle, wire payloads and entity IDs |
| 3. Model-aware Micro Nabto catalog | **Complete** | Canonical `register_catalog.py` with 17 RPC45 registers, known RPC 2/17/42/43/45 operations, 12 active read/write setpoint pairs, nine inactive source pairs, evidence tags and `ModelProfile`; 2 byte-identical shipping projections; offline JSON lookup CLI | Reliable lookup by **model + opcode + object + address**; future controller families can be added without mixing RPC namespaces |
| 4. Versions / configuration | **Complete** | Derived release versions from App/HA manifests; derived package register inventory from catalog; checked optional defaults; fixed manual IPC pairing retaining v4 fan-stage option | Reduced option/version drift and a real onboarding bug |
| Extra. Localized names and icons | **Complete** | Native HA translation keys for 17 raw diagnostic entities, English/Danish `strings.json` and translations, catalog-based semantic default icons, deterministic translation generator and offline tests | Newly created/imported entities get language-appropriate default names and meaningful icons while retaining stable IDs; user-customized names are not overwritten |
| 5. Documentation and historical cleanup | **Complete** | Updated root README, docs index/status, HA README, App DOCS and scripts guide to DEV9; dated/clearly labeled older DEV references | Current installation facts are no longer confused with DEV2/DEV8 observations |
| 6. Robustness / lifecycle | **Complete** | Detect terminated SDK worker before next poll, create a new session instead of trying closed stdio; guarantee invalidation/cleanup in `PollingService.stop` finally; fake-child regression tests | Better recovery after worker exit, no stale reading after unexpected task teardown |
| 7. Release / installation consolidation | **Partially resolved** | `scripts/remote_release_gate.py --check/--package`, shared CI steps, verified DEV9 source archive + SHA256, fail-fast source gate tests and docs. Old DEV-specific scripts kept for reproducible history | Source release flow is consolidated and tested; public HACS acceptance and proprietary SDK redistribution remain outside the completed work |
| 8. Final integration, QA and report | **Complete** | Reviewed full work log, verified code mirror parity, inspected GitHub Actions results, compared DEV9 against branch HEAD and committed this report | A single handoff with objective metrics, evidence and remaining boundaries |

## Measured change (DEV9 → audit checkpoint)

GitHub compare API `base=e0f2f462…&head=79b91632…`:

| Metric | Result |
| --- | ---: |
| Commits ahead of DEV9 | **95** |
| Changed paths | **52** |
| New paths | **17** |
| Modified paths | **35** |
| Deleted paths | **0** |
| Added lines | **3,437** |
| Removed lines | **527** |
| Net line change | **+2,910** |

These figures include documentation, tests, three intentionally identical register-catalog shipping copies and CI/tooling. **Net additional lines are not a measure of runtime complexity**: managed declarations and protective tests increase source size while replacing repeated operational definitions. The report and subsequent final log commit are not included in the frozen checkpoint.

### Breakdown by file type

| Type | Files | Added | Removed | Net |
| --- | ---: | ---: | ---: | ---: |
| Active runtime/HA sources and metadata | 25 | 1,785 | 284 | +1,501 |
| Tests | 10 | 652 | 1 | +651 |
| Documentation | 9 | 501 | 219 | +282 |
| Scripts and CI | 8 | 499 | 23 | +476 |
| **Total** | **52** | **3,437** | **527** | **+2,910** |

## Actual verification

- **App offline checks**: [GitHub Actions run 45096799091](https://github.com/rabbyraptor/genvexconnect/actions/runs/45096799091) **SUCCESS** — **189 App tests + 146 HA tests**, runtime/HA source and configuration gates, localized sensor check, deterministic combined archive and SHA256 verification (49 source members).
- **Remote Nabto offline checks**: [run 45096748400](https://github.com/rabbyraptor/genvexconnect/actions/runs/45096748400) **SUCCESS** — both cryptography matrix variants passed **364 source tests + 146 HA tests** each.
- **Formatting and hassfest**: both successful on code and documentation commits, including [formatting 45096799088](https://github.com/rabbyraptor/genvexconnect/actions/runs/45096799088) and [hassfest 45096799073](https://github.com/rabbyraptor/genvexconnect/actions/runs/45096799073).
- **Byte parity**: managed source/App runtime modules and HA catalog projection checked by CI; canonical register source and both shipping copies have the same Git blob SHA.
- **Read-only/protocol compatibility**: no SDK live requests, no hardware writes, no new control API, no modification to legacy HACS LAN component. v1/v3/v4 snapshot tests and DEV9 stage 0/null semantics retained.
- **Separate HACS blocker**: the repository's [HACS Validate run 45096817419](https://github.com/rabbyraptor/genvexconnect/actions/runs/45096817419) reports **issues disabled** and **no valid repository topics** (2/10 HACS checks fail). Both require repository settings, not code changes on this branch.

## Remaining items and decisions

1. **Public HACS metadata:** enable GitHub Issues and appropriate repository topics if publishing this repository via HACS. This is repository configuration, not a source refactor and should not be conflated with passing App/HA offline tests.
2. **Release policy:** proprietary legacy Nabto SDK redistribution/build-image licensing, signed/published release procedure and general installer remain separate decisions. Task 7 is correctly marked *partially resolved* until these are addressed.
3. **Deployment/acceptance:** these commits are **not installed on HAOS**. Before promoting to a deployed release, review the diff and perform an independently approved App + HA update. No further live tests were run in this source-only refactor.
4. **New models:** the catalog contains source-audited model boundaries, not remote verification for untested devices or RPC43 write authorization. Add source evidence, separate read-only fixtures, model-keyed sensor translations and offline gates before claiming support.
5. **Current HA language behavior:** entity translation keys defer default naming to Home Assistant's locale handling. Existing user-customized names and unique IDs remain unchanged. English and Danish resources are provided; other languages use normal HA fallback rules.

## Authoritative handoff

- [Architecture ownership map](overnight-architecture-baseline.md)
- [Sequential task log](overnight-refactoring-log.md)
- [Micro Nabto protocol library](micro-nabto-protocol-library.md)
- [DEV9 source-release gate](../scripts/remote_release_gate.py)
- [Sensor localization generation](../scripts/sync_remote_entity_localizations.py)
- [Current documentation index](README.md)

**Summary:** The DEV9 implementation is refactored, more coherent and more extensible; model/read/write metadata is centralized and safe to query offline, language-appropriate entity defaults are provided, and the source release/test gates have passed. Public HACS/release/deployment work remains explicitly separate.
