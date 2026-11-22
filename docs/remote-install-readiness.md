# Genvex Remote — current installation readiness

**Updated:** 22 November 2026. **Remote support is not ready for general installation.**

The existing LAN integration remains available through HACS as documented in the [repository README](../README.md). The separate `genvex_remote` HA integration and `genvex-nabto-remote` HAOS App are development prototypes.

## Proven on development systems

- Read-only Nabto Micro RPC45 five-value remote batches work through the isolated legacy x86_64 SDK under QEMU on HAOS ARM64.
- The separate Supervisor App `local_genvex_nabto_remote` was updated to version `0.1.0-dev2` in an operator-confirmed test on 20 November. Backup inventory `07337fa3` holds the previous `dev1` entry; successful restore was not tested.
- On 22 November the operator's DEV4 P.6a diagnostic returned `PASS` on App `0.1.0-dev4`: manually started, non-persistent session, first probe PASS, five sensors, fresh snapshot, exit code 0. This establishes a bounded successful live snapshot, not HA entity delivery or sustained background polling.
- On 21 November the operator's bounded DEV3 persistent-adapter run passed offline checks, SDK adapter preflight, three live 5-value RPC45 reads, worker close and DEV3 restart check. Observed read latencies: 10,504, 40 and 34 ms; process reuse was observed for reads 2 and 3.
- Synthetic diagnostic HTTP and source tests exist. Their synthetic values are not real telemetry.

## Required before an installable remote release

1. Confirm runtime/adaptor process lifetime and cleanup through repeat, failure and restart tests.
2. Finish private credential/profile and IPC token lifecycle, with no manual certificate extraction in the intended UX.
3. Verify App-to-HA DNS, token-authenticated snapshot transport and a real Home Assistant Core installation/config flow.
4. Validate sensors/units, no stale data on errors, coexistence with the existing LAN integration, and soak/reconnect behavior.
5. Resolve proprietary legacy SDK packaging and redistribution rights.

The seven-address v2 snapshot succeeded on the Steam Deck, **not** as an end-to-end HAOS/HA dashboard seven-sensor release.

## Where to continue

Start from [current status](STATUS.md), the [App development notes](../genvex-nabto-remote/DOCS.md), [active scripts](../scripts/README.md), [verified facts](remote-nabto-verified-facts.md) and [architecture roadmap](architecture-maintenance-plan.md). For the previous 20 November installation runbook see the [dated archive copy](archive/remote-install-readiness-2026-11-20.md).
