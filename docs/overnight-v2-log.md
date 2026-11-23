# Overnight v2 — verified audit and change log

**Branch:** `overnight-v2`  
**Frozen audit parent:** `overnight-refactoring` commit `ed166488361f04d23816cef38fd3c2ea46ed760b`.  
**DEV9 originally installed baseline:** `e0f2f46214a0561515f7bb4fda5841e481b3abbe`.  
**Scope:** Source, unit tests, CI and repository documentation only; no HAOS deployment or remote SDK/hardware tests.

The full [v1 sequential work log](overnight-refactoring-log.md) and its conclusions were read at the start, then the current v2 code tree, critical runtime/HA modules, translation sources and CI workflows were reviewed. This log records *actual* follow-up changes rather than repeating plans.

## Audit progress

| Workstream | Status | Main follow-up |
| --- | --- | --- |
| 1 Architecture / one source of truth | **Complete** | Removed separate manually maintained icon/English-label tables; per-register metadata is authoritative |
| 2 Code refactoring | **Complete** | Corrected coordinator measurement/diagnostic union typing; verified snapshot and request projections are still shared |
| 3 RPC command/register/model catalog | **Complete** | Model-specific icon/name lookup, stable model-qualified keys, stricter metadata and model-ID validation |
| 4 Version/configuration contracts | **Complete** | Corrected HA manifest GitHub links; release contract now fails stale links |
| 5 Documentation | **Complete** | Replaced current HACS installation language with Marketplace 2026.11+, preserved historical technical file/action names |
| 6 Reliability/error handling | **Complete** | Audited SDK lifecycle and snapshot invalidation; stronger model metadata fail-closed checks and negative tests |
| 7 Packaging/installation | **Partially resolved** | Unified source gates now test Marketplace root LAN-vs-Remote separation; public repository Issues/topics and SDK release require independent actions |
| 8 Integrated quality and final handoff | **In progress** | Verify final CI and publish v2 diffstat and complete report |

## Actual changes grouped by decision

### Authority and future models — workstreams 1, 2 and 3
- `RPC45Register` now owns its meaningful default `icon` and English `name` in the same canonical constructor as its register address, DA label, physical class, scale and evidence. The former `RPC45_DEFAULT_ICONS` and `RAW_ENGLISH_NAMES` remain **derived compatibility projections**, not additional independently editable tables.
- `rpc45_default_icon(key, model_key=...)` resolves by model; `rpc45_translation_key(model_key, key)` preserves Optima 270's existing `raw_<key>` names while namespacing another model. `scripts/sync_remote_entity_localizations.py` derives EN/DA names and validates icons from each model's actual specifications, rather than checking a global Optima 270 dictionary.
- The canonical catalog was copied **byte identically** into the runtime and HA shipping projections. `_validate_protocol_library` rejects duplicate model register addresses/keys, mismatched model identifiers, malformed address/types, missing labels and missing semantic icons. The coordinator's generic type reflects scaled floats **and** raw/fan-stage integers.
- New synthetic-model regression tests explicitly reuse one Optima 270 key/address but supply different names/icons; invalid model metadata fails before source generation. Existing 24 sensor keys and stable HA IDs are preserved.
- No activation of undocumented RPC43 operations. There remain five source-identified opcodes, 17 verified raw RPC45 values, 12 source-known active RPC42/RPC43 read/write address pairs and 9 inactive source entries.

### Configuration and official Marketplace contract — workstreams 4, 5 and 7
- Corrected `genvex_remote/manifest.json` `documentation` and `issue_tracker` from obsolete `rabbyraptor/genvex-remote` to actual `rabbyraptor/genvexconnect`. `scripts/check_remote_contracts.py` checks project manifest links to prevent regression.
- Official [Home Assistant Marketplace technical documentation](https://contributors.home-assistant.io/marketplace/how-it-works/) confirms built-in Marketplace starts with HA 2026.11 while **`hacs.json` and `hacs/action` keep their historical technical names**. Root documentation, HA README, scripts guide and source status were corrected to distinguish this.
- `scripts/check_marketplace_scope.py` checks that root `hacs.json` and `custom_components/genvex_connect` belong to **LAN** only; separate experimental `genvex_remote` and HAOS App do not silently get advertised or installed as the LAN Marketplace package.
- `scripts/remote_release_gate.py` and its unit tests include the new scope check, and both offline CI workflows include `overnight-v2` branch triggers. `.github/workflows/hacs.yaml` is now displayed as **Marketplace repository validation**, while continuing to use the publisher-supported `hacs/action`.
- Old DEV1–DEV9 technical histories and earlier v1 audit remain accessible; v2 facts are recorded here and in `overnight-v2-report.md`.

### Reliability and acceptance — workstreams 6 and 8
- Reviewed existing persisted worker exit/recovery, cancellation, no-credential logging, read-only RPC42/45, v1/v3/v4 snapshot validators and 0-vs-null fan-level distinctions. The earlier `overnight-refactoring` tests for worker exits and shutdown invalidation are retained.
- Added error-path coverage for new model identity and incomplete/incorrect register presentation metadata; missing model facts cannot silently become an imported sensor with an incorrect icon.
- Offline source package gate remains deterministic and checks SHA256; old DEV9 release and live installation were not modified.

## CI at the post-code audit point

- [App candidate 45099966326](https://github.com/rabbyraptor/genvexconnect/actions/runs/45099966326): **SUCCESS**; 190 App tests + 148 HA tests, Marketplace scope, release configuration, catalog copy parity, localized sensor metadata and DEV9 combined source archive/SHA256 (49 members).
- [Remote offline 45099966406](https://github.com/rabbyraptor/genvexconnect/actions/runs/45099966406): **SUCCESS**; 365 source tests + 148 HA tests, separately in both configured cryptography matrix environments.
- Formatting and hassfest checks **SUCCESS** at the same code checkpoint.
- Historical early-commit red CI runs were caused by temporarily unmatched canonical/shipping file copies during incremental commits; final code checkpoint passed parity.
- Marketplace validator remains blocked on repository-wide GitHub configuration: Issues disabled, no valid topics. This **does not** mean that the Remote App or Marketplace package is ready for public distribution. This is **partially resolved** and requires separate repository release decisions.
- **No live HAOS validation** of new v2 code was performed.

## Handoff requirements
1. Verify final branch HEAD, parities and post-documentation CI.
2. Freeze and report Git changes **relative to `ed166488`** and optionally relative to `e0f2f462`. Do not estimate metrics.
3. Publish `docs/overnight-v2-report.md`; mark task 8 complete only after a factual report exists.
