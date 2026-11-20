# Genvex Remote — active documentation

**Verified on HAOS:** SDK 4.9.11 via QEMU, live read-only RPC 45 batch (5 sensors), native ARM64 OpenSSL and Python cryptography 47.0.0, and **51/51 offline Python unit tests passed** on 2026-11-20 in 6.308 seconds. Offline tests used fake CA credentials, not real enrollment. No functioning HA UI remote integration exists yet.

## Current engineering sources

| Document | Role |
| --- | --- |
| [Verified facts](remote-nabto-verified-facts.md) | Authoritative observed results and remaining limitations |
| [UI and certificate architecture](remote-ha-ui-onboarding-architecture.md) | No-terminal setup design |
| [First five HA entities](remote-ha-entity-plan.md) | Read-only sensors and runtime bridge plan |
| [Resource catalogue](remote-nabto-resources.md) | Vendor documentation, protocol references and relevant GitHub repositories |
| [Reconstructed read-only RPC 45](reconstructed-readonly-query45-2026-11-19.md) | Proven query structure and tested addresses |
| [Sensor phase-one validation](remote-phase1-sensor-validation-2026-11-19.md) | Remote single and batched read evidence |
| [Archived research](archive/README.md) | 17 historical documents, traces, hypotheses and prior investigations |

## Development code

- [Isolated Home Assistant UI/sensor scaffold (not installed)](../experimental/home_assistant/README.md)
- [Serial read-only RPC 45 polling worker](../experimental/genvex_remote/polling_worker.py)
- [Offline Python certificate/enrollment and sensor code](../experimental/genvex_remote/enrollment_service.py)
- [Automated native HAOS offline test runner](../scripts/run_haos_offline_enrollment_tests.sh)
- [Isolated HAOS runtime App](../haos-apps/genvex-nabto-runtime-test/DOCS.md)

The LAN `genvex_connect` component has not been changed. Never treat experimental remote writes as verified.
