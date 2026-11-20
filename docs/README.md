# Genvex Remote — active documentation

**Verified on HAOS:** SDK 4.9.11 via QEMU, live read-only RPC 45 batch (5 sensors), native ARM64 OpenSSL and Python cryptography 47.0.0, and **51/51 offline Python unit tests passed** on 2026-11-20 in 6.308 seconds. Offline tests used fake CA credentials, not real enrollment. No functioning HA UI remote integration exists yet.

## Current engineering sources

| Document | Role |
| --- | --- |
| [Verified facts](remote-nabto-verified-facts.md) | Authoritative observed results and remaining limitations |
| [Architecture maintenance roadmap](architecture-maintenance-plan.md) | Approved 2A–5C priorities, isolation rules, stage gates and progress |
| [2B device discovery investigation](remote-device-discovery-2b.md) | Metadata vs known-address RPC45 batch vs unverified capability enumeration |
| [UI and certificate architecture](remote-ha-ui-onboarding-architecture.md) | No-terminal setup design |
| [First five HA entities](remote-ha-entity-plan.md) | Read-only sensors and runtime bridge plan |
| [Resource catalogue](remote-nabto-resources.md) | Vendor documentation, protocol references and relevant GitHub repositories |
| [Runtime IPC security](remote-runtime-ipc-security.md) | Internal App-to-HA authentication, host-network exposure and production bridge design |
| [Reconstructed read-only RPC 45](reconstructed-readonly-query45-2026-11-19.md) | Proven query structure and tested addresses |
| [Sensor phase-one validation](remote-phase1-sensor-validation-2026-11-19.md) | Remote single and batched read evidence |
| [Archived research](archive/README.md) | 17 historical documents, traces, hypotheses and prior investigations |

## Development code

- [Isolated Home Assistant UI/sensor scaffold (not installed)](../experimental/home_assistant/README.md)
- [Offline typed Optima 270 capability catalog (2A)](../experimental/genvex_remote/capability_catalog.py) and [synthetic/compatibility tests](../experimental/genvex_remote/test_capability_catalog.py)
- [Serial read-only RPC 45 polling worker](../experimental/genvex_remote/polling_worker.py)
- [Single HAOS offline validation script](../scripts/run_haos_remote_dev_tests.sh)
- [Two-container disposable IPC test](../scripts/run_haos_ipc_two_container_test.sh) (fake sensor values and private test network only)
- [Offline Python certificate/enrollment and sensor code](../experimental/genvex_remote/enrollment_service.py)
- [Automated native HAOS offline test runner](../scripts/run_haos_offline_enrollment_tests.sh)
- [Isolated HAOS runtime App](../haos-apps/genvex-nabto-runtime-test/DOCS.md)

The LAN `genvex_connect` component has not been changed. Never treat experimental remote writes as verified.
