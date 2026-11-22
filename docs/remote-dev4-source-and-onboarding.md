# DEV4 onboarding and source-parity work — 22 November 2026

**Status:** DEV4 source reconciliation candidate, offline tests and onboarding primitives; not yet an installable end-user onboarding flow.
**Branch:** `dev4-source-parity-onboarding-20261122`; merge only after CI, deployed-source comparison and review.

## Grounded current state

- HAOS has operator-verified five read-only measurements plus a sixth Dataalder sensor, a private bearer-authenticated App snapshot endpoint, and intermittent Nabto RPC45 code 26 / event 1000015 under a persistent worker. See [STATUS.md](STATUS.md).
- The original base branch `remote-nabto-connection` contains an earlier App source snapshot (`dev2`). The complete DEV4 persistent adapter, native worker, startup mode-switch and related offline tests were recovered from the existing GitHub branch `feature/dev4-persistent-session` and staged into this candidate, with source manifest set to `0.1.0-dev4`. Whether these files match the **currently deployed** container after its temporary patches still requires independent comparison.
- The source candidate now includes metadata-only RPC45 timing/worker PID logs, integer SDK status, and bounded extraction of the nested numeric event (e.g. `1000015`) into a private file, plus fake-SDK tests. It deliberately does **not** copy the live container's ad-hoc diagnostic implementation verbatim; the shipped source implementation must be tested and compared before live deployment.
- Persistent runtime options: `persistent_session: true`, `poll_seconds: 60`. Existing HA entity IDs and five-value snapshot schema v1 must remain stable.

## Source gate — 3A + 2E + 5C

1. Use `experimental/genvex_remote/` as the canonical location for runtime modules shared with the App. `python scripts/check_remote_runtime_parity.py --check` checks bundled copies; `--sync` explicitly regenerates only shared modules. App-only bootstrap/profile/worker files are exempt.
2. Log only UTC timestamp, RPC45 success/failure, elapsed seconds, optional SDK integer status/elapsed milliseconds and worker PID. Do not log raw SDK responses, exceptions, passwords, hostnames, profile paths or identity fields. No extra retries or changes to polling semantics.
3. Source-packaging now uses deterministic gzip headers and zeroed tar timestamps. The `remote-app-offline` workflow tests parity, no-secret packages and byte reproducibility.
4. **Remaining DEV4 gate:** the persistent SDK worker is now in source, with its strict RPC frames and tests. Run the offline suite and native ARM64 image build from this branch. Then compare the candidate files to the **installed** source using `scripts/export_haos_dev4_sources_readonly.sh` (code only; no options/profile/secret material), review deliberate differences, and verify fresh snapshots, restart and grace behavior on HAOS before deployment. The source manifest saying `dev4` is not proof that the tested artifact matches the installed App.

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

**First:** complete CI and compare this DEV4 candidate with deployed source. **Second:** prove reproducible package and ARM64 image + App/HA snapshots under fake and live lifecycle gates. **Third:** complete authenticated pairing and credential lifecycle with a fake HAOS test. This is the blocking order for a trustworthy installable release; sensor v2 expansion can remain separate.

## Installed DEV4 source comparison — 22 November 2026, 11:41 CET

Operator provided a code-only TAR from `/opt/genvex-remote/runtime/` containing the exact ten files selected by `scripts/export_haos_dev4_sources_readonly.sh`. The archive was read without deployment or remote commands; all ten Python files parse successfully. Compared **Git blob SHA-1** of each archived file against the same filename under `genvex-nabto-remote/runtime/` at PR #4 commit `9ca0fe9`:

- **Exact match (7/10):** `app_bootstrap.py`, `polling_runtime.py`, `persistent_sdk_adapter.py`, `sdk_snapshot_adapter.py`, `polling_http_server.py`, `snapshot_contract.py`, `ipc_auth.py`.
- **Expected, intentional source drift (3/10):** `polling_service.py` (runtime's ad-hoc timing/PID log versus source's bounded metadata log), `snapshot_state.py` (runtime's exception-type/stage diagnostic versus source's integer-only SDK status/elapsed metadata), and `persistent_rpc45_worker.py` (runtime's nested field-type diagnostic versus source's bounded numeric Nabto event extractor).
- **Installed file Git blob hashes for audit only:** `polling_service.py` `2a5dffff25feb51a4cd108e68a47d16f7de594e7`; `snapshot_state.py` `1726a3234931f6488f964eff2aa1c56bdac60131`; `persistent_rpc45_worker.py` `a865fb7d59d57fed7bbbcf8c264b7ee9f71781d2`. These are hashes of **code only**, not private `/data` files.
- Both SDK worker execution and public snapshot contract are unchanged in semantics: one session, serial RPC45, fixed five-address response, validated v1 snapshot, unchanged 60-second poll interval. The differences are diagnostic metadata handling.
- **Decision:** retain the new source diagnostics instead of copying ad-hoc runtime patches. Require a fresh image lifecycle test before upgrading the installed App.

This confirms that the recovered DEV4 implementation matches the deployed source everywhere except the explicitly introduced diagnostics. It does **not** prove that a rebuilt candidate has been installed, restarted, or that automatic onboarding is operational.

