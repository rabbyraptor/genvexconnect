# Development scripts

Run scripts from the **repository root** unless a script explicitly says otherwise. This directory holds current and still useful diagnostic entry points; superseded versioned scripts live in [archive/](archive/README.md).

## Recommended offline/development gates

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
