# DEV5 metadata diagnostics — staged versioned update

**Status:** source-only candidate `0.1.0-dev5`. No DEV5 code has been installed on HAOS. This is an update of the live DEV4 persistent runtime.

## Verified DEV4 starting state — 22 November 2026

- Running and source App version: `0.1.0-dev4`. Manual boot, no published host ports, persistent session enabled, 60-second polling.
- Installed source baseline: 10/10 identical to captured live code and syntax valid.
- Exactly one persistent worker; authenticated IPC returns HTTP 200 with five v1 values and fresh snapshot (age 0.5 seconds).
- 6,921 MiB free; eight Supervisor backups inventoried; future source stage and backup paths are unoccupied.
- Periodic RPC status 26 persists, with automatic recovery; no cause has yet been proven.

## Why DEV5?

The new package retains the DEV4 SDK and five-value v1 snapshot semantics while replacing temporary runtime-container logging with source-controlled UTC RPC45 timing, outcome, worker PID, optional numeric SDK status/elapsed_ms and bounded numeric JSON error events. Raw SDK error strings, tokens and credentials are not logged.

`genvex-nabto-remote/config.yaml`, the ARM64 image CI label and packaging tests use version `0.1.0-dev5`. A separate version is necessary for Supervisor to offer a real update.

## Update transaction

Scripts:

- `scripts/preflight_haos_dev4_versioned_upgrade_readonly.sh` — operator PASS; verifies *installed* DEV4 and environment, not the candidate archive.
- `scripts/run_dev5_upgrade_from_deck.sh --preflight <commit-sha>` — downloads a *commit-pinned* source tree, produces a deterministic SHA256-verified archive, transfers it to a temporary private directory, validates it with HAOS system tar, verifies installed DEV4/source/options/backups capability, then cleans up. Does not stop the App.
- `scripts/run_dev5_upgrade_from_deck.sh --apply <same-commit-sha>` — repeats preflight, stages and validates DEV5 source, stops DEV4, rechecks source/state, saves old source to `.genvex-remote-dev4-source-backup`, promotes DEV5 source and invokes Supervisor Store reload + `ha apps update local_genvex_nabto_remote --backup`. Checks the new App version, manual/stopped state and compares the *full options dictionary in memory*, ensuring the active persistent session and IPC token survive. It never prints credentials and never starts the new App.

`--apply` is opt-in, not part of normal CI. A transaction failure *after* the source swap needs inspection; the script preserves the old source backup and does not silently roll back or restart. The update tool's backup flag confirms the backup was *requested*; verify the resulting Supervisor backup inventory separately.

## Acceptance criteria after manual update

1. DEV5 is installed, `stopped` and `manual`, prior source backup exists, a new Supervisor backup is verified and all options are preserved.
2. Start DEV5 explicitly and verify one persistent worker, authenticated HTTP 200/five validated values, and the existing six HA entities (five readings + Dataalder).
3. Confirm graceful single-worker recovery after future status 26 events. The numeric event log must contain only timestamp/status/event, not raw `body`, `header` or `detail` strings.
4. Leave the six-minute Nabto connection investigation documented but separate. The DEV5 change does not claim to cure event `1000015`.

The Core Supervisor token parser and private IPC storage are **offline onboarding groundwork only**. Automatic pairing and Nabto certificate enrollment are not activated in DEV5.


## Actual DEV5 source/Supervisor transaction — operator result

**22 November 2026, pinned commit `65ba9cb79ca9785aee8eb760435b00926ac1a687`: PASS.**

The operator ran both `--preflight` and `--apply` from Steam Deck, with deterministic source archive SHA256 `3bb6cde83eb986175b640059efdc8262b5778fe730b0a0973617594527977e0e` and 20 packaged source files. The apply output confirmed:

- `DEV4_STOPPED_AND_RECHECKED: PASS` and `SOURCE_SWAP_DEV5: PASS`.
- `DEV4_SOURCE_BACKUP: RETAINED` and `DEV5_OFFERED: PASS`.
- `SUPERVISOR_UPDATE_WITH_BACKUP: REQUESTED`.
- `INSTALLED_DEV5_STOPPED: PASS`, `PERSISTENT_OPTIONS_UNCHANGED: PASS`.
- `DEV5_UPGRADE_RESULT: PASS`, `STEAM_DECK_EXIT_CODE: 0`.

**Separate backup and post-install acceptance is pending.** A backup request is not a verified backup. The code-only gate `scripts/dev5_post_install_verify.py` checks exact Git blob hashes for all 20 installed source files against the pinned commit, the preserved DEV4 source, Supervisor App version/state/options, backup inventory expansion beyond 8, a recent partial/full backup containing the DEV4 App, and six pre-existing Home Assistant entity-registry entries. Run it from Steam Deck through `scripts/run_dev5_post_install_from_deck.sh <verified-commit>`. It has no service-start/stop/update operations.

Do **not** interpret the stopped DEV5 state as a failed installation. Start and snapshot/Dataalder smoke verification are separate gates after the backup verification.

## DEV5 post-install source/backup gate — PASS

Operator output on 22 November 2026 from `scripts/run_dev5_post_install_from_deck.sh`:

- `INSTALLED_DEV5: PASS`; `DEV5_STOPPED: PASS`; `MANUAL_BOOT: PASS`; `PERSISTENT_OPTIONS: PASS`; `CONTAINER_NOT_RUNNING: PASS`.
- `DEV5_SOURCE_20_BLOBS: PASS`: all twenty installed source files matched the exact pinned Git source blob hashes.
- `DEV4_SOURCE_BACKUP: PASS`: rollback source preserved.
- `BACKUP_COUNT_INCREASED: PASS` — inventory now **9**. `DEV4_SUPERVISOR_BACKUP: PASS`, backup ID **`60e96ffb`**, dated **2026-11-22T11:15:18.036512+00:00**. The backup metadata includes the DEV4 App.
- `HA_REMOTE_CONFIG_ENTRY: PASS`; `HA_REMOTE_SIX_ENTITIES: PASS` with six registered entities.
- `DEV5_GATE_RESULT: PASS`; Steam Deck exit code `0`.

**Next acceptance gate:** `scripts/run_dev5_first_start_from_deck.sh` explicitly starts DEV5, verifies Supervisor version/configuration, three newly packaged diagnostic-module hashes in the running container, a fresh authenticated five-value IPC snapshot, exactly one persistent SDK worker and the six existing HA registry entities. Reports only bounded metadata; no credentials or actual sensor readings. This confirms App and IPC operation; it does not independently prove HA Core has received new entity state updates.

The first-start script will not change the current polling interval or initiate direct additional RPC45 calls; it observes normal polling. If a live check fails, it returns a diagnostic category without rolling back or restarting automatically.

## First-start report — Supervisor started; remaining live gate incomplete

The operator executed the first-start script after the full read-only post-install backup/source/registry PASS. The output showed `DEV5_PRESTART: PASS`, `START_DEV5: RETURNED`, `SUPERVISOR_DEV5_STARTED: PASS` and exit code 0, but stopped **before** `DEV5_DIAGNOSTIC_IMAGE_PARITY`, `DEV5_LIVE_RESULT`, `HA_REGISTRY` and the end marker.

**Interpretation:** Supervisor confirmed the DEV5 App was started, but the missing checks were not executed/observed. The original multi-command SSH `sh -s` script could consume subsequent stdin unexpectedly, and lacked a mandatory final-result sentinel; therefore its exit 0 did not establish live acceptance. Do not rerun the start script on an already-started App.

Corrective actions:

- The historical first-start script now redirects the Supervisor start command stdin to `/dev/null` and requires a final PASS sentinel to prevent a false success if input is truncated.
- A new `scripts/run_dev5_live_verify_from_deck.sh` performs **no start/stop/update**. Instead, it uses independent SSH stdin streams for (1) Supervisor, Docker and six HA registry entries, (2) the running container's three diagnostic-source hashes, retained persistent configuration, exactly one SDK worker and fresh authenticated five-value HTTP snapshot, and (3) sanitized RPC45 logs.
- The new wrapper rejects missing end or PASS markers even if SSH returns exit code 0. Fake SSH regression tests verify that early EOF cannot produce a false PASS.

**Next live gate:** run the read-only verifier once and inspect `DEV5_RUNTIME_VERIFY: PASS` together with `DEV5_IPC_RESULT: PASS`, worker count 1 and HTTP 200. Actual post-start HA entity *state freshness* remains a separate follow-up after this passes.
