# HAOS local App: controlled diagnostic-only installation plan

Status: **source staged and Supervisor discovery verified; build/install NOT executed**.
This plan is intentionally
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

## Supervisor discovery verified (20 November 2026)

**Phase B source staging and Supervisor catalog discovery completed on HAOS.**
The source exists at `/mnt/data/supervisor/apps/local/genvex_nabto_remote`.
Supervisor's own container can read `config.yaml`, and its
`SCHEMA_APP_CONFIG` validation accepts the slug, version and experimental stage.
The file scanner finds both the new remote source and the original runtime-test
source. After the explicit **`ha store reload`** command, the user verified:

- `ha apps info local_genvex_nabto_remote`: `available: true`,
  `installed: false`, `build: true`, `arch: [aarch64]`,
  `stage: experimental`, `host_network: false`, `version_latest: 0.1.0-dev1`,
  `state: unknown`.
- Existing `local_genvex_nabto_runtime_test`: `state: started`,
  `version: 0.5.0`, untouched.

**Important:** `ha apps reload` is not a supported CLI subcommand and did not
refresh the catalog. Use **`ha store reload`** for local source discovery,
then `ha apps info local_genvex_nabto_remote` to verify.
There is no need to alter the App manifest or touch timestamps to fix this.
The new App is **not installed, built by Supervisor, or started**. Phase C
(build/install without start) still needs separate explicit user approval,
and Phase D (synthetic-only start) needs yet another approval. No real Nabto
connection or credential provisioning has been authorized.

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

**Phase C: Supervisor build/install (separate user approval; discovery complete).**

- Discovery is already verified with `ha store reload` and
  `ha apps info local_genvex_nabto_remote`. Do not repeat staging.
- Before installing, recheck free disk space, RAM, image-build prerequisites,
  and confirm the existing runtime-test App is still started.
- Select only `local_genvex_nabto_remote` for installation.
- Supervisor builds the image from this App's Dockerfile since no
  `image:` is configured. It may need network access and extra
  free disk space. The imported development image is not reused by
  this automatically.
- Install **without** starting. `boot: manual_only` prevents automatic boot
  startup, but verify the App remains stopped after installation; do not assume
  an install command cannot trigger a start.
- After installation, inspect the new App's `installed`, `state`, and version;
  confirm the existing `local_genvex_nabto_runtime_test` is still running
  version `0.5.0`. Do not enter credentials or copy certificate/key files.
- If the build fails, stop and inspect the new App's logs and disk usage before
  any cleanup. Never prune unrelated Docker resources or modify the old App.

**Phase C decision record (20 November 2026):** User requested a pros/cons
assessment, **not authorization to install**. Benefits: tests Supervisor's
actual ARM64/QEMU build, dependency resolution and App lifecycle, exposing
HAOS-only failures that source-only tests cannot detect. Costs/risks: several
GB of disk, CPU/RAM pressure on Raspberry Pi 4, possible failed build and
residual cache, and no evidence of stable real Nabto connectivity from an
installed App. Recommendation: proceed only after read-only resource/security
preflight and explicit user approval; installation must remain separate from
Phase D synthetic startup and any later live RPC45 testing.

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
