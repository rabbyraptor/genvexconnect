# Genvex Connect documentation

**Latest verified live milestone: DEV8, 22 November 2026.** The separate Genvex Remote App `0.1.0-dev8` and HA integration `0.2.0` were deployed together on HAOS ARM64. The Optima 270 remote connection returned **17/17 raw RPC45 sensors**, alongside five existing scaled sensors and a data-age sensor (**23/23 entities available**).

- [Live DEV8 deployment and exact 17-register readings](dev8-live-verification-2026-11-22.md) — most recent installation evidence
- [DEV8 combined release and test gate](dev8-4-combined-release-gate.md) — source packaging, preflight, offline and live acceptance plan
- [Main README](../README.md) — current public-facing architecture, capabilities, limitations and repository map
- [DEV8 staging pull request #16](https://github.com/rabbyraptor/genvexconnect/pull/16) — development changes; not the released LAN HACS integration

## Current remote development references

| Document | Focus |
| --- | --- |
| [DEV8 live verification](dev8-live-verification-2026-11-22.md) | Installed versions, real 17 raw register values, 23 entities, worker reuse and remaining live tests |
| [DEV8.1 recovery](dev8-1-recovery-gate.md) | Supervisor IPC token rotation and bounded retry; offline-validated |
| [DEV8.2 register evidence](dev8-2-register-evidence-gate.md) | Readability and interpretation evidence for all 17 candidate addresses |
| [DEV8.3 all raw registers](dev8-3-all-raw-registers.md) | Optional v3 snapshot, 17 raw diagnostics, v1 preservation and partial-RPC behavior |
| [DEV8.4 combined release](dev8-4-combined-release-gate.md) | Full-path tests, packaging, fixed-version source transfer, installer and deferred fault-injection |
| [Optima 270 read command reference (DA)](optima270-nabto-read-command-reference-da.md) | Legacy read-only commands and datapoints |
| [RPC45 expansion test matrix](remote-optima270-rpc45-expansion-testmatrix.md) | Original source-known candidates and seven-address prototype |
| [IPC architecture](remote-runtime-ipc-security.md) | Authenticated App-to-Core snapshot bridge |
| [Verified facts ledger](remote-nabto-verified-facts.md) | Dated protocol research and prior observations |

## Earlier milestones and background

The [engineering timeline](STATUS.md) and the [historical archive](archive/README.md) document the progression from DEV1 through the original DEV4/DEV5 experiments. Some older status sections reflect their original observation date and are **not current installation state**. Prefer [DEV8 live verification](dev8-live-verification-2026-11-22.md) for the installed Remote App version, register coverage and entity counts.

Additional references:

- [Remote installation readiness notes](remote-install-readiness.md) — historical/current readiness considerations; cross-check against DEV8 live evidence
- [DEV4 source parity/onboarding](remote-dev4-source-and-onboarding.md) — earlier source and pairing gates
- [DEV5 diagnostic upgrade](dev5-diagnostic-upgrade.md) — historical source migration and backup
- [Architecture/maintenance roadmap](architecture-maintenance-plan.md) — broader design and maintenance topics
- [Existing five-sensor plan](remote-ha-entity-plan.md) — initial entity design, prior to v3 expansion
- [Nabto documentation/resources](remote-nabto-resources.md) — legacy upstream and vendor references

## Implementation entry points

- [Existing HACS LAN integration](../custom_components/genvex_connect/)
- [Remote backend and test models](../experimental/genvex_remote/)
- [Remote Home Assistant integration](../experimental/home_assistant/README.md)
- [ARM64/QEMU HAOS App](../genvex-nabto-remote/)
- [Source packaging and versioned release runner](../scripts/)
- [Historical scripts](../scripts/archive/README.md)

The existing LAN/HACS integration and the experimental Remote App remain distinct. Confirmed remote support currently covers the **one tested Optima 270 setup**; production distribution of the proprietary SDK and controlled live fault-injection are still pending.
