# 2A — Typed sensor and capability catalog (offline prototype)

**Date:** 2026-11-20  
**Status:** The initial prototype is checked into the experimental source tree and has passed existing GitHub offline CI. No production App/HA integration consumes it yet.

## Scope

The new [capability_catalog.py](../experimental/genvex_remote/capability_catalog.py) is an isolated, transport-independent, read-only model. It knows source-backed semantic sensor keys, RPC object/address, scaling, measurement type, HA representation hints and evidence status. It does not import Nabto SDK or Home Assistant, issue RPCs, discover sensor inventories, transfer certificates, or create entities.

### Optima 270 validated starter profile

| Stable key | RPC | obj | Address | Decode | HA representation |
| --- | ---: | ---: | ---: | --- | --- |
| supply_air | 45 | 0 | 20 | (raw - 300) / 10 | sensor, temperature °C |
| outdoor_air | 45 | 0 | 21 | (raw - 300) / 10 | sensor, temperature °C |
| exhaust_air | 45 | 0 | 22 | (raw - 300) / 10 | sensor, temperature °C |
| extract_air | 45 | 0 | 23 | (raw - 300) / 10 | sensor, temperature °C |
| humidity | 45 | 0 | 26 | raw | sensor, humidity % |

These are the *only* remotely verified readings declared in the profile. The address/scale definitions come from the [upstream Optima 270 model](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py); their authenticated remote read status comes from [our Phase 1 evidence](archive/remote-phase1-sensor-validation-2026-11-19.md). The profile's capability enumeration flag remains **unverified**.

## Validated behavior

- An explicit model selector rejects unknown profiles; unknown devices cannot silently use Optima 270 addresses.
- An immutable list preserves the verified five-item request order; no address-range generation is available.
- Strict signed-int16 decoding rejects malformed, partial or extra data; batch failure never returns partial readings.
- The initial semantic keys and numeric decodes match the existing five-value snapshot schema v1.
- Boolean and enum decoder paths have **synthetic-only** tests with fake addresses. They are not declared as supported device readings.
- The existing runtime sensor_model.py, snapshot_contract.py, probe and HA integration are **unchanged**.

## Test evidence

[GitHub Actions offline suite](https://github.com/rabbyraptor/genvexconnect/actions/runs/44791766493) passed on commit 4f6168297ef050628aecc9e6095ddae51c538f5b with Python 3.12 and cryptography 46.0.4 / 47.0.0. The new [catalog unit tests](../experimental/genvex_remote/test_capability_catalog.py) check v1 parity, address order, validation and synthetic types. This is **not** a live HAOS, Home Assistant Core or device discovery test.

## Remaining gates

1. Use [2B evidence](remote-device-discovery-2b.md) to choose the right model based on authenticated numeric metadata only after a separate approved verification; never publish account-related ping fields.
2. Agree on a **versioned typed snapshot contract v2** and separate failure groups; preserve strict v1 until downstream readers have compatibility tests (3A).
3. Make the catalog the single source of truth for the App and HA entity definitions through automatic packaging (2E), rather than introducing another permanent code copy.
4. Expand sensor support only with source-backed, independently tested remote read-only capabilities; no arbitrary query IDs or register scans.
5. Run real Home Assistant Core entity and config-flow tests, plus identity/stability review, before allowing dynamic entity creation.
