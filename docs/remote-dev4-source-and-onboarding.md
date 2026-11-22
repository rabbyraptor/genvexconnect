# DEV4 onboarding and source-parity work — 22 November 2026

**Status:** source-only development plan and offline primitives; not yet an installable end-user onboarding flow.
**Branch:** `dev4-source-parity-onboarding-20261122`; merge only after CI and DEV4 source reconciliation.

## Grounded current state

- HAOS has operator-verified five read-only measurements plus a sixth Dataalder sensor, a private bearer-authenticated App snapshot endpoint, and intermittent Nabto RPC45 code 26 / event 1000015 under a persistent worker. See [STATUS.md](STATUS.md).
- The running `0.1.0-dev4` App contains `persistent_sdk_adapter.py` and `persistent_rpc45_worker.py`, **which are missing from the checked-in `genvex-nabto-remote/runtime/` snapshot** (currently version `0.1.0-dev2`). Source changes alone cannot claim DEV4 reproducibility.
- The running container contains temporary diagnostic additions for timing, worker PID, numeric SDK response status and JSON event metadata. The shared source-level timing/status logging in this branch is only a *partial* source reconciliation; capturing the nested Nabto event safely requires inspecting the deployed worker before porting code.
- Persistent runtime options: `persistent_session: true`, `poll_seconds: 60`. Existing HA entity IDs and five-value snapshot schema v1 must remain stable.

## Source gate — 3A + 2E + 5C

1. Use `experimental/genvex_remote/` as the canonical location for runtime modules shared with the App. `python scripts/check_remote_runtime_parity.py --check` checks bundled copies; `--sync` explicitly regenerates only shared modules. App-only bootstrap/profile/worker files are exempt.
2. Log only UTC timestamp, RPC45 success/failure, elapsed seconds, optional SDK integer status/elapsed milliseconds and worker PID. Do not log raw SDK responses, exceptions, passwords, hostnames, profile paths or identity fields. No extra retries or changes to polling semantics.
3. Source-packaging now uses deterministic gzip headers and zeroed tar timestamps. The `remote-app-offline` workflow tests parity, no-secret packages and byte reproducibility.
4. **Remaining DEV4 gate:** obtain and review the complete deployed `persistent_sdk_adapter.py`, `persistent_rpc45_worker.py`, `polling_runtime.py`, `app_bootstrap.py`, `snapshot_state.py` and `config.yaml` (code only; no options/profile/secret material), compare to source, port the strict worker frames/error JSON redaction and persistent lifecycle, and run offline parity/worker tests. Then build an App image from the tested commit and verify restart/snapshot/grace behavior on HAOS. Do not label an image DEV4 until the source is reconciled.

## Onboarding goal — 2D + 3B

Target user experience: install separate Remote App/integration, enter the authorised gateway identity and account login **once**, and see validated sensors without copying certificate files or bearer tokens manually.

### Separate three credential classes

| Credential | Source and lifetime | Intended destination |
| --- | --- | --- |
| LS Control/Nabto account password | User-entered during one-time registration; transient | Verified, pinned legacy CA registration transaction only |
| Encrypted Nabto key/certificate and key unlock secret | Provisioned once, rotated through a reviewed credential generation | App-private `/data`; never Home Assistant entity state or logs |
| 256-bit internal snapshot bearer token | Per-install token with staged rotation and no manual copy | App-private token and HA integration config entry through a verified authenticated handoff |

**Current onboarding:** `genvex-nabto-remote/runtime/profile_provision.py` imports an existing certificate/key with atomic no-replace. `experimental/genvex_remote/profile_store.py` supports versioned generations; `enrollment_service.py` has a fake-transport trusted-CA verification candidate. These are *different* storage conventions; do not connect them to running App until a single target store and migration/rollback policy are chosen. The legacy LS Control CA trust anchor and a production enrollment transport are not yet independently verified.

### Implementation in this source branch

- The separate HA config flow derives `EXPECTED_APP_ENDPOINT` internally rather than asking the user to type a URL. Existing saved entries retain their already-pinned endpoint.
- `experimental/genvex_remote/ipc_token_store.py` is an **offline** private App token initialization primitive with symlink, ownership, mode and no-clobber checks, and tests. It does not transfer tokens to Core, rotate live credentials or change the current App bootstrap. Production App bootstrap still reads `ipc_token` from Supervisor options.
- The verified user-facing handoff is **not yet implemented**. In particular, a discoverable unauthenticated HTTP endpoint must not be used to obtain or set a shared bearer token. The App-to-HA trust boundary remains a separate design gate.

### Required before automatic onboarding

1. Verify, with fake credentials on a disposable HAOS test instance, which Supervisor/Core service can authenticate an App-to-Core pairing/secret handoff and precisely what permissions it has. Official Supervisor API documentation: [App endpoints](https://contributors.home-assistant.io/apps/supervisor-api/apps/) and [authentication/roles](https://contributors.home-assistant.io/apps/supervisor-api/).
2. Define install, restart, pair, revoke and rotate state transitions for App and HA config entry. Require proof of ownership/authorization; never ship an unauthenticated pairing endpoint.
3. Reconcile one App-private credential store and the trust-verified legacy CA enrollment flow. Run offline tests for interrupted writes, duplicate onboarding, stale tokens, wrong device, failed registration and non-disclosure of sensitive material.
4. Validate on HA Core with a fake App and fake accounts before real enrollment. Deploy changes to the user's live DEV4 App only as a separate tested gate.

## Execution order

**First:** obtain deployed DEV4 sources and merge/retest the missing persistent worker. **Second:** reproducible package + image/CI proof. **Third:** complete the authenticated pairing and credential lifecycle design with a fake HAOS test. This is the blocking order for a trustworthy installable release; sensor v2 expansion can remain separate.
