# DEV8.2 — Optima 270 RPC45 register evidence and release gate

**Staging:** `dev8-staging` / draft PR #16. **Scope:** only the isolated
development inventory and offline tests. No source from DEV8.2 is installed
on HAOS, nor is DEV8.1 merged/deployed separately.

## Prior live results (not repeated)

Earlier recorded tests, all from 20 November 2026:

1. Five established active RPC45 values at addresses `20,21,22,23,26`
   are used by the deployed v1 integration.
2. One *Steam Deck* authenticated RPC45 batch for the other twelve
   model-defined addresses `24,18,19,35,36,41,42,53,40,114,115,50`
   succeeded, returning 12 signed int16 values in 358 ms.
3. One *Steam Deck* seven-item batch `20,21,22,23,26,18,19`
   succeeded; the same fixed seven-item RPC45 pattern also succeeded
   once on *HAOS ARM64/QEMU* with seven complete values in 1,275 ms.
4. The source-scaled `18=6000/100=60 %` and `19=5800/100=58 %`
   matched an earlier, **non-simultaneous** official Genvex Connect
   display. This is supporting evidence for *fan control duty*,
   **not** a simultaneous measurement of physical RPM or airflow.

Primary evidence:
- [12-register live result](remote-optima270-rpc45-expansion-testmatrix.md#live-verifikation-alle-12-kildebaserede-kandidater-i-én-batch-2026-11-20)
- [Seven-address ARM64/QEMU success](remote-nabto-verified-facts.md#haos-arm64-qemu-seven-address-live-rpc45-success--2026-11-20)
- [Archived seven-address result](archive/remote-optima270-seven-snapshot-v2-live-verification.md)

## Three release tiers

| Tier | Addresses | Verified | Release decision |
| --- | --- | --- | --- |
| A — existing HA measurements | `20,21,22,23,26` | Live RPC and supported physical meaning | Keep as the five enabled v1 sensors |
| B — fan-control duty candidate | `18,19` | RPC-readable in Steam Deck and HAOS/QEMU; prior official UI numerically consistent | Offline v2 candidates, **not** added to running HA yet; compare live simultaneously before release |
| C — raw-only candidate | `24,35,36,41,42,53,40,114,115,50` | RPC-readable in one twelve-register batch | **No HA entity** until meaning, units, hardware presence and zero/sentinel interpretations are verified |

Tier C details:

- `24` gave raw `0`, source-scaled `−30 °C`; **not** proof of a
  physically connected frost sensor or unique T8/T9 assignment.
- `35=2432` and `36=2268` are source-labeled fan RPM but need
  independent verification at more than one fan speed.
- `41,42,53,40` gave zero; zero may mean inactive, absent, or another
  hardware-dependent state. Do not expose a definitive bypass/heater flag.
- `114,115` gave zero; do not infer absence of alarms or decode bitmasks
  until semantics are independently established.
- `50` gave `10`, but whether this corresponds to physical rotor
  hardware is unresolved.

The read-only RPC45 *register address* 42 above is **not** the RPC42
setpoint-read command. RPC42 remains unverified remotely, and the write RPC43
is out of scope.

## Implemented offline

`experimental/genvex_remote/dev8_register_evidence.py` derives an
evidence-aware 17-register inventory from the existing five-value approved
catalog and 12-entry source mapping. It distinguishes remote *readability*
from *meaning*, preserves exact raw signed int16 values and only marks the
five previously released values as `ready_for_ha`. The two fan-duty
keys are **explicitly optional candidate projections**, not deployable
entities. The other ten can never enter the proposed seven-value set.

`test_dev8_register_evidence.py` enforces fixed address/key order, 17 unique
addresses, exact 12-value signed-int16 shape, preservation of zero values
without boolean/alarm/temperature inference, alignment with existing v1
planner and inert seven-address v2 draft, and strict opt-in behavior.

The existing five-address production planner, installed runtime,
`/v1/snapshot`, Home Assistant entity setup and DEV8.1 recovery are not
changed by this substep.

## Remaining gates

1. **DEV8.3:** decide which additional readings, if any, get enabled
   after semantic validation. Integrate a versioned v2 IPC contract while
   retaining the v1 five-sensor identities and data availability.
2. Before enabling fan-duty entities, compare the values *simultaneously*
   against the official Genvex Connect UI at more than one ventilation
   setting. Do not present them as measured fan speed or RPM.
3. Keep Tier C raw-only until independent physical and hardware validation;
   a successful read is insufficient.
4. **Combined package:** run full offline regression and code parity checks,
   then perform the single agreed HAOS deployment and live acceptance,
   including optional-data failure isolation, app restart and token rotation.

### Offline tests

```sh
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
```

**Status:** DEV8.2 source implementation complete subject to passing CI.
