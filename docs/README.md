# Remote Nabto research — documentation index

**Start here:** [Verified facts manifest](remote-nabto-verified-facts.md). This is the current status as of **2026-11-19**: authenticated remote `ping.json` succeeded on x86_64 and **on Raspberry Pi HAOS ARM64 through QEMU emulation**, and **read-only datapoint RPC 45 also succeeded on x86_64 Steam Deck** for five separate sensors (addresses 20, 21, 22, 23, 26; all SDK RPC statuses 0). One-call five-sensor batching is now also **verified on Steam Deck x86_64 (RPC status 0, 318 ms)**. **The same five-sensor RPC 45 batch is now independently VERIFIED under HAOS ARM64/QEMU (RPC status 0, 1,150 ms for one invocation).** Two additional independent HAOS batches (1,200 / 1,260 ms, both 5/5) also passed. Native ARM64, continuous polling, integration and production packaging remain open.

## Navigation

| Document | Purpose |
| --- | --- |
| [Remote HA entity bridge plan](remote-ha-entity-plan.md) | First five read-only entity specifications, offline test model, secure runtime-to-HA bridge requirements and deployment gates |
| [Verified facts manifest](remote-nabto-verified-facts.md) | Current verified results, exact SDK statuses, identity provisioning, architecture, remaining gates |
| [Phase 1: read-only sensor validation](remote-phase1-sensor-validation-2026-11-19.md) | Five verified individual RPC 45 sensor reads and one verified five-sensor batch; HAOS/QEMU batch now verified; next resilience/integration gates |
| [RPC / ARM64 next steps](remote-nabto-next-steps.md) | Read-only query discovery and Linux ARM64 validation plan |
| [Investigation journal](remote-nabto-investigation.md) | Full history and evolving hypotheses; includes older, now-superseded status statements |
| [Reconstructed read-only query 45](reconstructed-readonly-query45-2026-11-19.md) | Source-grounded LAN opcode mapping and offline candidate XML for remote telemetry |
| [Nabto TEN025 and LS Control architecture](nabto-ten025-lscontrol-rpc-architecture-2026-11-19.md) | Primary-source RPC migration, static XML and vendor-specific bridge limitations |
| [Remote RPC without Android](remote-rpc-without-android-2026-11-19.md) | HTML-DD, existing iPhone captures, vendor API documentation and limits of remote streams |
| [RPC metadata probe result](remote-interface-info-probe-2026-11-19.md) | Status 26, missing JSON diagnostics and why this does not establish gateway support |
| [Legacy Nabto HTML-DD RPC distribution](nabto-legacy-html-dd-interface-distribution-2026-11-19.md) | Official mechanism for centrally supplied `unabto_queries.xml` and read-only interface metadata |
| [Mobile app RPC resource investigation](mobile-app-rpc-resource-investigation-2026-11-19.md) | Android/iOS app identity and static extraction plan for production RPC XML |
| [Homey source vs remote RPC](homey-source-vs-remote-rpc-2026-11-19.md) | Local Optima 270 register map and why it is not a remote RPC schema |
| [RPC findings](remote-nabto-rpc-findings.md) | Earlier RPC research and open questions |
| [Nabto 4 SDK and identity research](nabto4-client-sdk-availability-and-identity-2026-11-19.md) | Upstream SDK/CA/architecture background |
| [LS Control sample app](lsc-nabto-test-app-analysis.md) | Source-level `ping.json` interface, demonstrated locally upstream and now remotely by us |
| [Cloud API observation](observed-lscontrol-cloud-api.md) | HTTPS evidence; not a replacement for remote Nabto RPC |
| [Login traffic capture](remote-login-flow-capture-2026-11-19.md) | HAR/PCAP and timing evidence |
| [Micro DATA packet structure](nabto-data-packet-structure-2026-11-19.md) | Legacy Micro wire format and evidence limits |
| [Fan speed capture](fan-speed-change-capture-2026-11-19.md) | Packet correlation, not verified write command |
| [Remote endpoint assessment](remote-endpoint-and-shelly-cloud-ip-assessment-2026-11-19.md) | IP/endpoint ownership and uncertainty |
| [HAOS isolated SDK test runtime](../haos-apps/genvex-nabto-runtime-test/DOCS.md) | QEMU/x86_64 test app on ARM64 HAOS |

The existing local Home Assistant integration remains unchanged. Do not infer that any packet-correlated control call is a verified RPC write.
