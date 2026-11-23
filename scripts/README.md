# Development scripts

Run scripts from the **repository root** unless a script explicitly says otherwise. This directory holds current and still useful diagnostic entry points; superseded versioned scripts live in [archive/](archive/README.md).

## Marketplace scope

Home Assistant 2026.11+ uses the built-in Marketplace rather than a standalone
HACS installation. The old publisher file `hacs.json` and action `hacs/action`
remain supported technical interfaces. `scripts/check_marketplace_scope.py`
enforces that the repository's Marketplace metadata targets the original
`genvex_connect` LAN integration, **not** the separate Remote App/component.
GitHub topics and Issues are repository settings, outside this branch's package.

## Current DEV9 release workflow

The one supported **source-only** entry point for this branch is:

```sh
python scripts/remote_release_gate.py --check
python scripts/remote_release_gate.py --package
```

`--check` validates repository references, canonical runtime/App/HA mirror parity, App/HA options and version compatibility, and English/Danish sensor name/icon metadata. `--package` performs those same checks, builds the deterministic DEV9 combined source archive and verifies the archive and SHA256 manifest. Both run **without** Home Assistant OS, Nabto SDK, network or gateway access. App and remote offline CI share this gate.

When adding a register or model, edit `experimental/genvex_remote/register_catalog.py` then synchronize shipping copies and default sensor labels with:

```sh
python scripts/check_remote_runtime_parity.py --sync
python scripts/sync_remote_entity_localizations.py --sync
python scripts/remote_release_gate.py --check
```

Read-only model, RPC and register lookup is available via `python scripts/lookup_micro_nabto.py --commands` or `--model optima270 --setpoints`. **All RPC43 write definitions remain metadata only**.

Version-stamped `run_haos_*.sh` and `package_dev8_*.py` helpers are retained for historical reproducibility and existing regression tests, not advertised as the latest install procedure. Source artifacts are not auto-deployed to the running HAOS installation. See [current branch architecture](../docs/overnight-architecture-baseline.md) and [work log](../docs/overnight-refactoring-log.md).

## Historical and specialized offline/development gates

| Purpose | Entry point |
| --- | --- |
| Combined remote development tests | [`run_haos_remote_dev_tests.sh`](run_haos_remote_dev_tests.sh) |
| Offline enrollment and fake credentials | [`run_haos_offline_enrollment_tests.sh`](run_haos_offline_enrollment_tests.sh) |
| SDK adapter source-only gate | [`run_haos_sdk_adapter_offline_v3.sh`](run_haos_sdk_adapter_offline_v3.sh) |
| Remote installation preflight (latest retained) | [`run_haos_remote_install_preflight_v7.sh`](run_haos_remote_install_preflight_v7.sh) |
| V2 source preflight (latest retained) | [`run_haos_v2_offline_preflight_v2.sh`](run_haos_v2_offline_preflight_v2.sh) |
| V2 offline runtime gate (latest retained) | [`run_haos_v2_runtime_offline_v5.sh`](run_haos_v2_runtime_offline_v5.sh) |
| HAOS App source packaging used by CI | [`package_remote_diagnostic_app.py`](package_remote_diagnostic_app.py) |
| Image/offline container tests used by CI | [`test_remote_app_private_docker_network.sh`](test_remote_app_private_docker_network.sh), [`test_remote_app_private_storage_container.sh`](test_remote_app_private_storage_container.sh) |

## Specific development tasks

- **Read-only Optima 270 probes:** `run_optima270_one_read_from_deck.sh`, `run_optima270_seven_snapshot_v2_from_deck.sh`, `run_optima270_all_candidates_batch_from_deck.sh`, and the corresponding `probe_*.py` code. These are deliberately scoped; execute live only when the current test gate calls for it.
- **HAOS and IPC diagnostics:** `audit_haos_*.sh`, `run_haos_ipc_two_container_test_v2.sh`, `run_haos_live_rpc_to_ipc_test_v2.sh` and `verify_haos_*.sh`. Some are historical one-off checks but remain here because their current code/tests still reference them.
- **Completed dev2 upgrade diagnostics:** `*dev2*`, `reload_haos_dev2_store_once_v1.sh` and `upgrade_remote_local_app_source_dev2.sh` are retained for audit and compatibility with existing source tests; **not** next-step instructions.

Do not infer a production installation from a script name. Refer to [current status](../docs/STATUS.md) and [readiness](../docs/remote-install-readiness.md) before using any live runner. The scripts moved to [archive](archive/README.md) are deliberately excluded from the current entry points.
