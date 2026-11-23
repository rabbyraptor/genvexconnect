> **Archived evidence (21 November 2026).** This is a dated investigation or completed milestone, not the current operating instructions. See [current status](../STATUS.md).

# Optima 270 — seven-address snapshot v2 live verification

**Observed:** 2026-11-20 (user-supplied Steam Deck console output).  
**Evidence:** one authorized remote, read-only RPC45 operation, not a deployed HAOS service.

## Observed run

- Branch checkout updated by fast-forward from `52f6b9a` to `3957716`.
- Offline preflight succeeded, without opening a Nabto session.
- Live runner: `scripts/run_optima270_seven_snapshot_v2_from_deck.sh --execute-live`.
- Exactly one fixed RPC45 batch: `obj=0`, ordered addresses `20,21,22,23,26,18,19`.
- RPC status `0`; observed elapsed time `396 ms`.
- Returned raw signed integers: `368,308,322,378,67,6000,5800`.
- Interpreted baseline: supply air `6.8 °C`, outdoor air `0.8 °C`, exhaust air `2.2 °C`, extract air `7.8 °C`, humidity `67 %`.
- Source-scaled optional values: supply fan duty `60 %`, extract fan duty `58 %`.
- Output marker `GENVEX_READONLY_SNAPSHOT_V2` emitted only after successful decode, session close status `0`, SDK shutdown status `0`.
- Temporary test profile cleanup was **attempted** (not independently audited).

## Evidence boundary

This verifies a complete seven-item single read-only remote RPC and end-to-end v2 payload creation on the Steam Deck's x86_64 SDK test path. It does **not** establish the same seven-item live call on HAOS ARM64/QEMU, deployed App-to-Core v2 HTTP communication, unattended lifecycle, repeated polling reliability, or correct physical interpretation of fan percentages against the official Genvex UI. The baseline five measurements preserve the existing v1 contract and sensor identities. The v2 provider/HTTP consumer remains experimental.

Do not record operator account identity, device ID, hostname, credentials, full SDK JSON, or keys in repository documentation.

## Next safe implementation gates

1. Update now-stale offline-only descriptions in v2 source docs; keep v1 production runtime unchanged.
2. Run offline regression and source-parity tests for v2 provider, strict snapshot parser, HTTP bearer authorization and HA seven-entity projection.
3. Verify guarded single-shot v2 RPC in isolated HAOS/QEMU environment separately before enabling background polling.
4. Validate fan-duty semantics against authorized official UI before describing them as a definitive physical speed or measured RPM.
5. Never add write RPCs or unverified source-only addresses to production polling.
