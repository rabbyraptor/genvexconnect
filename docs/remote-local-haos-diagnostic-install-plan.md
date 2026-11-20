# HAOS local App: controlled diagnostic-only installation plan

Status: **prepared, NOT executed on HAOS**. This plan is intentionally
separate from any existing Genvex LAN integration or the earlier
`genvex_nabto_runtime_test` App.

## Verified host observations (20 November 2026)

- Architecture: `aarch64`.
- Supervisor host storage: `/mnt/data/supervisor`.
- Existing local App source root:
  `/mnt/data/supervisor/apps/local`.
- New App container `app_local_genvex_nabto_remote`: not present.
- Existing `app_local_genvex_nabto_runtime_test`: running, must remain untouched.
- Development ARM64 image was imported, but import **does not install** a
  Supervisor-managed App.
- Available disk: approximately 9.2 GiB; available memory: approximately
  2.3 GiB at audit time, both subject to change.
- Home Assistant Core resolves `local-genvex-nabto-runtime-test`, not
  `app_local_genvex_nabto_runtime_test`.

## Intended source package

GitHub offline CI emits a development-only artifact
`genvex-remote-local-app-source` consisting of:

1. `genvex-nabto-remote-local-app-source.tar.gz`
2. `APP_SOURCE_SHA256SUMS`

The archive has a single top-level folder `genvex_nabto_remote`,
with only `config.yaml`, `Dockerfile`, `run.sh` and regular
`runtime/*.py` files. Symlinks, secret files, profiles, options JSON,
keys and certificates are intentionally not included. Source packaging
is checked in CI and the checksum is computed there.

The prepared Steam Deck script
`scripts/stage_remote_diagnostic_app_source.sh` checks the SHA256
and inspects each archive member before doing anything remotely.
Its default *explicit* mode `--preflight` only verifies the archive
and confirms the new target folder does not already exist.
`--stage` requires a separate positive operator decision. It streams
the archive over SSH to a **hidden** new temporary directory inside
the confirmed local App root, then moves its new App folder to the
fixed target. It refuses to overwrite an existing folder or symlink.
It does not reload Supervisor, install, build or start an App.

## Acceptance stages and approval boundaries

**Phase A: offline source validation – no HAOS modification.**

- Verify GitHub Actions source checks and uploaded artifact.
- Verify the archive checksum and allowlist locally.
- Run the staging script with `--preflight`, which also makes a
  read-only existence check on HAOS.
- Inspect the App's security-critical options:
  `boot: manual_only`, `stage: experimental`,
  `host_network: false`, `tmpfs: true`,
  `diagnostic_only: false`, no published ports or shared mounts.

**Phase B: stage source (requires user approval).**

- Run `--stage` against the exact reviewed artifact.
- Confirm only
  `/mnt/data/supervisor/apps/local/genvex_nabto_remote`
  was created. No existing directories are modified.
- No Supervisor store reload or App installation in this phase.

**Phase C: Supervisor discovery/build/install (separate user approval).**

- Via Settings > Apps > Install app, use Check for updates, select
  Local apps and inspect `Genvex Remote (experimental)`.
- Supervisor builds the image from this App's Dockerfile since no
  `image:` is configured. It may need network access and extra
  free disk space. The imported development image is not reused by
  this automatically.
- Install **without** starting. Startup on boot is forbidden by
  `boot: manual_only`.

**Phase D: explicit synthetic-only start (separate user approval).**

- In the new App's configuration set `diagnostic_only: true`.
  Leave all four `device_id`, `identity`, `unlock_secret`,
  `ipc_token` fields **empty**. No profiles or keys must be created.
- Manually start only this new App. Any nonempty credential, existing
  App-private profile or token must prevent diagnostic startup.
- Never set `host_network: true` or publish port `18275`.

**Phase E: only read-only HAOS acceptance.**

Use `scripts/verify_haos_remote_diagnostic_readonly.sh`, which checks
Docker network mode, no host ports, connection to `hassio`, and
Core-to-App DNS/HTTP. Expected outcomes:
`GET /v1/diagnostic` -> 200, exact marked synthetic JSON;
`GET /v1/snapshot` -> 404, even with a token.
The script does not request actual sensor data, send secrets or
alter HAOS. Stop the experimental App after the acceptance test.

**Unfinished later work:** App-private Nabto credential enrollment,
separate IPC bearer token delivery to the HA integration,
on-device authenticated real RPC45, restarts and failure recovery.
The working LAN integration must remain untouched. No live Nabto
connection is authorized by any phase above.

## Documentation and known limitations

Official Home Assistant instructions:

- https://contributors.home-assistant.io/apps/first-app/
- https://contributors.home-assistant.io/apps/how-apps-work/
- https://contributors.home-assistant.io/apps/guides/testing/
- https://contributors.home-assistant.io/apps/reference/configuration/

This is a development experiment, not a production-ready HAOS App.
A successful Docker fake-only test does not establish live Nabto
connectivity or real Supervisor DNS until Phase E.
