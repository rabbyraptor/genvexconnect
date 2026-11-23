# Genvex Remote — experimental HAOS App (legacy Nabto Micro)

**Current verified baseline:** `0.1.0-dev9` on one ARM64 Home Assistant OS installation with a Genvex Optima 270 controller (23 November 2026). The App uses native Python orchestration and the proprietary x86-64 legacy Nabto SDK under QEMU; the same SDK process/session is reused across authorized polls. The separate Home Assistant `genvex_remote` integration `0.3.0` consumes strictly validated snapshots.

The App is **not** the existing LAN integration and is **not** a phone-app proxy. This source project does not distribute a generic ARM64 Nabto Micro client.

## Current read-only snapshot modes

| Mode | App requirements | Snapshot result |
| --- | --- | --- |
| v1 | Normal authenticated polling | Five scaled RPC45 measurements |
| v3 | `persistent_session: true`, `raw_registers_v3: true` | V1 measurements plus five baseline and up to twelve optional signed-int16 RPC45 values |
| v4 | Both above plus `fan_level_v4: true` | V3 plus RPC42 selected ventilation stage 0–4 or null |
| diagnostic | `diagnostic_only: true` with all credentials empty and no profile/token | Deliberately synthetic `/v1/diagnostic`, never presented as live data |

The three production snapshot paths are `/v1/snapshot`, `/v3/snapshot` and `/v4/snapshot`, on the App-private host `local-genvex-nabto-remote:18275`. All require the private IPC token. HTTP reads are cache lookups, **not additional Nabto polls**. Remote RPC43 writes remain unverified/disabled even though the [protocol library](../docs/micro-nabto-protocol-library.md) records source-model write addresses.

An incomplete optional secondary read does not invalidate five mandatory measurements; missing optional register values become unavailable, not numeric zero. A missing RPC42 stage is null, distinct from valid stage 0.

## Startup and isolation

- **Live:** requires a valid twelve-digit device ID, identity, unlock secret, private IPC token, poll interval 60–3600 seconds and a provisioned App-private profile under `/data/profile`. No credentials are printed in logs or placed in RPC command arguments.
- **Persistent:** one SDK worker session performs read-only RPC45 and, when v4 enabled, RPC42; SDK startup/shutdown and worker cancellation must be bounded.
- **Diagnostic only:** mutually exclusive with any live credentials, existing profile/token and persistent flags. It exposes a separate explicitly synthetic endpoint and never starts the Nabto SDK.
- App Supervisor configuration keeps manual boot, no published host port, no `host_network` privileges and a restricted private App-to-HA IPC boundary.

## Source and maintenance

- `runtime/persistent_rpc45_worker.py` implements read-only session transport and uses source-derived addresses from `register_catalog.py`.
- `experimental/genvex_remote/register_catalog.py` is the authored source of all currently known RPC42/RPC43/RPC45 register facts. The runtime copy here is a byte-identical shipping projection.
- `scripts/check_remote_runtime_parity.py --check`, `scripts/check_remote_contracts.py` and `scripts/package_dev9_combined.py` are the offline parity, options and packaging gates.
- `docs/overnight-architecture-baseline.md` and `docs/overnight-refactoring-log.md` track the current refactoring branch and its results. The existing [historical status](../docs/STATUS.md) retains DEV2–DEV8 observations as historical records.

The proprietary SDK's distribution terms and automated live fault-injection remain separate release decisions. Code-only checks are not evidence of successful new-model remote communication.
