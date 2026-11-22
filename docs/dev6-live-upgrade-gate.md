# DEV6 live deployment gate — DEV5 → DEV6 (prepared, not executed)

## Objective

Validate the **exact pinned** 0.1.0-dev6 App source and update the existing
`local_genvex_nabto_remote` under Home Assistant Supervisor without
changing its existing credentials, 60-second poll interval, persistent mode
or the five-value RPC45 snapshot contract.

This gate is prepared for HAOS OS 18.5, Supervisor 2026.11.0 and installed
App 0.1.0-dev5. The current HA config entry is loaded on Core 2026.11.1.

## Operator workflow

Obtain a reviewed 40-character SHA from the combined integration PR's HEAD.
Run the pinned `scripts/run_dev6_upgrade_from_deck.sh` on Steam Deck with
`--preflight <SHA>` first. The script clears the terminal before printing
the final consolidated diagnostic output. The preflight downloads a source-only
GitHub archive to temporary Steam Deck storage, recreates the deterministic App
source archive, transfers only source plus the candidate transaction script
into a private temporary HAOS path and performs read-only validation.

After accepting the preflight output, run the same pinned script at the
**same SHA** with `--apply <SHA>`. This intentionally:
1. Validates the old App as *started* 0.1.0-dev5 with persistent mode,
   60-second polling, one preserved private IPC token and an exact 20-file
   source fingerprint matching the installed DEV5 release.
2. Requires a 20-file, hash-verified, safe-regular-file 0.1.0-dev6 archive;
   stages it and re-verifies the installed DEV5 source after stopping the App.
3. Retains the complete old local App source at
   `/mnt/data/supervisor/apps/local/.genvex-remote-dev5-source-backup`.
4. Reloads the Supervisor store; requires the DEV6 update to be offered;
   asks Supervisor to update using `--backup`.
5. Verifies the new App is **stopped** and its options exactly equal those
   before the update. The transaction does **not** start or reload the App.

After confirming a successful stopped-version gate, start with the standard
`ha apps start local_genvex_nabto_remote` operator action. A separate
post-start live acceptance via HAOS MCP + Home Assistant entities must
verify continuous read-only RPC45 success, SDK worker reuse, five sensors,
Data Age and 0 unexpected container restarts.

On a failure after the App is stopped, do not try further unreviewed source
swaps; use the retained DEV5 local source and Supervisor-created backup in a
reviewed recovery step. Existing production credentials remain in App-private
storage or Supervisor options, never in this source archive.

## Offline verification

```bash
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py' -v
python3 scripts/check_remote_runtime_parity.py --check
bash -n scripts/run_dev6_upgrade_from_deck.sh
```

The fake Supervisor tests cover archive path/hash validation, complete DEV5
source fingerprints, no-stop preflight, refused stale/altered DEV5 source,
retained options, stopped update and shell clear-output behavior.

## Separate future gates

- DEV7 Core pairing on the installed Core 2026.11.1 requires the experimental
  HA integration zip from combined PR #9 and a dedicated integration reload.
  This is **not** part of the App update gate.
- DEV8 fan-duty projection remains disabled by default until gateway values
  are compared against the official Genvex Connect UI.
- No pull request is merged automatically by this procedure.
