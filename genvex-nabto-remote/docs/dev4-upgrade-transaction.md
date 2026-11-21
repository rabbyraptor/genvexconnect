# DEV4 install transaction, P.2/P.3 baseline and next gate

## Operator-verified preflights

P.2: PASS. Installed App version DEV3, state started, manual boot,
private hassio Docker network, no host-published ports, Home Assistant
Core running, one `genvex_remote` config entry, five numeric sensor
entities with stable entity-ID signature `2be9240972de0a9d`,
backup outside the integration component folder, and no legacy
backup folder inside `custom_components`. App restart count 0.

P.3: PASS. All 23 installed DEV3 source files exactly match the pinned
Git object content from commit
`d7ad38a60991cca1a4f4b3af677ee501d749f74c`, with
manual boot, private network, no published ports, running-state
agreement, and free DEV4 transaction paths.

## DEV4 upgrade operator

- `scripts/run_dev4_upgrade_from_deck.sh --preflight` validates a
  pinned DEV4 source package, transfers only source files and a
  checksum, then re-verifies the installed DEV3 source and host state.
- `--apply` repeats that validation; it then stops the dedicated
  App, re-verifies DEV3, atomically saves DEV3 source as
  `.genvex-remote-dev3-source-backup`, installs the DEV4 source, and
  uses `ha store reload` plus `ha apps update ... --backup`.
- After update, the App must be stopped/manual and at
  `0.1.0-dev4`. The `persistent_session` option must be
  false or absent. The script never starts the App.
- The transfer directory and local temporary sources are removed by
  the launcher. On error, a sanitized failure category is printed.
- The upgrade and archive validators are exercised with fake
  Supervisor and file-system fixtures by
  `test_dev4_upgrade_transaction.py` in the DEV3 read-only
  remote contracts workflow. The App binary build has already passed
  ARM64 CI with DEV4 code. No real upgrade has happened.

## Post-upgrade gates

1. Verify Supervisor backup inventory and installed DEV4 version,
   stopped/manual state, and disabled persistent mode.
2. Manually start DEV4 in default (one-shot) mode. Verify the same five
   Home Assistant sensors and fresh snapshots/availability.
3. Change only `persistent_session` to true through App options,
   verify that the installed worker is the sole RPC45 poller, and
   repeat the five-entity live smoke.
4. Compare mutually exclusive 30-minute windows for legacy DEV3-style
   polling and the persistent worker, recording complete HTTP
   snapshots, 503 counts, freshness, process continuity and SDK errors.

No reliability improvement claim is justified until those exclusive
windows are measured.
