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
