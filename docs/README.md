# Genvex Connect development documentation

**Current verified remote baseline: DEV9 · 23 November 2026.** The separate Genvex Remote App `0.1.0-dev9` and HA integration `0.3.0` are verified together on one Optima 270 / HAOS ARM64 setup. With the v4 stage and v3 diagnostics enabled, Home Assistant has **24 entities**: 5 scaled measurements, 17 RPC45 signed-int16 raw diagnostics, one data-age diagnostic and one RPC42 selected ventilation stage (0–4). Automatic and manual IPC pairing remain available. Experimental refactoring commits on `overnight-refactoring` are **not** automatically deployed to HAOS.

## Current authoritative references

| Document | Owns |
| --- | --- |
| [Architecture and source-of-truth decisions](overnight-architecture-baseline.md) | Runtime/HA responsibility, trusted snapshot boundary and authority table |
| [Overnight refactoring work log](overnight-refactoring-log.md) | Changes, tested results, commits, blockers and task status |
| [Micro Nabto protocol library](micro-nabto-protocol-library.md) | Source-known RPC 2/17/42/43/45, Optima 270 register catalog and future model extension |
| [Setpoint source evidence](references/optima270_micro_nabto_setpoint_catalog.json) | Source-derived read/write addresses and separate remote verification flags |
| [Remote verified facts](remote-nabto-verified-facts.md) | Historical network/protocol observations with their dates |
| [Main repository README](../README.md) | Public summary, current DEV9 remote capabilities and LAN/remote separation |
| [Engineering status and history](STATUS.md) | DEV9 overview, then explicitly historical DEV1–DEV8 milestones |

## Working source and tooling

- [Canonical remote runtime and tests](../experimental/genvex_remote/) — source of RPC definitions and snapshot contracts
- [Separate HA integration](../experimental/home_assistant/) — sensor identities, language translations and coordinator
- [HAOS App](../genvex-nabto-remote/) — persistent legacy SDK transport and authenticated IPC
- [Local register/command lookup](../scripts/lookup_micro_nabto.py) — read-only JSON catalog queries
- [Translation sync](../scripts/sync_remote_entity_localizations.py) — generate/check language-specific sensor names
- [Runtime parity and release contracts](../scripts/check_remote_runtime_parity.py) — shipping-copy parity; use alongside `check_remote_contracts.py`

## Historical milestones — evidence, not current installation state

These are retained as dated engineering records. Their DEV8/DEV2 versions, entity counts and open gates must not be interpreted as describing the current DEV9 deployment.

- [DEV8 live verification (23 entities before stage integration)](dev8-live-verification-2026-11-22.md)
- [DEV8.1 recovery](dev8-1-recovery-gate.md)
- [DEV8.2 raw-register evidence](dev8-2-register-evidence-gate.md)
- [DEV8.3 raw v3 snapshot contract](dev8-3-all-raw-registers.md)
- [DEV8.4 combined release gate](dev8-4-combined-release-gate.md)
- [Older read-only Optima 270 reference](optima270-nabto-read-command-reference-da.md) — predates verified remote RPC42; use the newer library for present capabilities
- [Legacy RPC45 expansion matrix](remote-optima270-rpc45-expansion-testmatrix.md)
- [IPC security background](remote-runtime-ipc-security.md)
- [Architecture/maintenance roadmap](architecture-maintenance-plan.md)
- [Historical archive](archive/README.md)

## Interpretation boundary

A source-model address is not proof of a present physical sensor, working remote operation or permitted write. All currently identified RPC43 write-address pairs are documented **as metadata only**. The verified remote integration remains read-only; no remote write transport is enabled. The existing HACS LAN integration in [`custom_components/genvex_connect/`](../custom_components/genvex_connect/) is separate from this experimental remote system.
