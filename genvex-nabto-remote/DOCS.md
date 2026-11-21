# Genvex Remote — experimental HAOS App (Nabto Micro 4)

> **Development update — 21 November 2026:** The installed
> `0.1.0-dev2` App was started in live read-only mode on HAOS. The
> private HTTP endpoint resolves from Home Assistant and correctly rejects
> unauthenticated requests, but authenticated snapshot reads returned HTTP 503.
> One direct DEV2 SDK attempt raised `SDKSnapshotError: SDK read failed`;
> this revision hides the specific SDK stage. The separate `feature/dev3-live-once`
> branch now packages the enhanced SDK failure classification as a **new**
> `0.1.0-dev3` App candidate. DEV3 has passed offline tests and a native
> ARM64 container-image build, but has **not** been deployed or live-tested
> against the user's gateway. Run the explicit, stop-before-update operator
> script `scripts/upgrade_genvex_remote_dev3_from_deck.sh` only when authorized.
> The App remains manual boot and is not automatically started after update.

**Status (operator-verified 21 November 2026):** The separately managed App
`local_genvex_nabto_remote` was updated to `0.1.0-dev2` on HAOS with
`ha apps update local_genvex_nabto_remote --backup`. The installed App
remained **stopped**, with **manual boot**, and no dedicated running container.
Supervisor backup `07337fa3` is listed as `partial` and its metadata
contains the previous `0.1.0-dev1` App entry. A restore and the archive's
integrity have **not** been tested. The existing working LAN integration and
separate runtime-test App must remain untouched.

## Purpose and separation

Native ARM64 Python coordinates read-only, serial RPC45 polling through the
legacy x86_64 Nabto SDK under QEMU. In live mode, the App publishes snapshots
on its dedicated private App network, at port `18275`; its HTTP endpoint is
`/v1/snapshot` and it requires a private IPC bearer token. The App exposes
no host-published port, uses `host_network: false`, and does not implement
control RPC. **In the installed DEV2 App, live polling has been started, but no valid snapshot has been confirmed.**

## Startup modes (not interchangeable)

- **Diagnostic-only:** Must be explicitly enabled by setting
  `diagnostic_only: true`, with `device_id`, `identity`, `unlock_secret`
  and `ipc_token` all empty. The bootstrap also refuses diagnostic startup
  if a private `/data/profile` or `/data/ipc-token` path exists. It then
  imports `diagnostic_http_server` rather than the SDK or polling runtime.
  The only successful diagnostic path is `GET /v1/diagnostic`, which returns
  a deliberately **synthetic, nonproduction** response. Even a request with
  an authorization header to `/v1/snapshot` returns 404. This listener binds
  within the App's Docker networking context; it is **not authenticated** and
  must not be host-published. Diagnostic-only mode does not prove live Nabto
  connectivity.
- **Live:** Requires a valid 12-digit device ID, identity, unlock secret,
  IPC token (at least 43 characters), and polling interval 60–3600 seconds.
  Before starting the polling runtime, the bootstrap validates pre-existing
  App-private `/data/profile/client.crt` and
  `/data/profile/client-encrypted.key` files. It does **not** import,
  generate, overwrite, or copy a profile from `/share` or another source.
  Secure enrollment/migration is a separate unfinished and approval-gated
  task. Password-marked Supervisor options are not hardware-backed vaults.

## Next approval boundary (updated)

The DEV3 candidate is prepared for an explicitly operator-run source-only
swap followed by a backup-enabled Supervisor App update. The update script
stops DEV2 first, verifies the installed DEV2 source hashes, retains its old
source as a separate backup, reloads the local App catalog and requests one
Supervisor update with `--backup`. It does not read/copy the private PEMs,
change Supervisor options, touch the existing LAN integration or start DEV3.
After installation the App must be explicitly started before a new read-only
SDK diagnosis. The successful ARM64 CI build alone does not prove Nabto
connectivity.

Known gaps: secure profile onboarding, production distribution of the separate
HA integration, live SDK/remote runtime validation, private App-to-Core DNS,
and end-to-end soak tests. A backup inventory entry is not equivalent to a
verified restore path.

See `docs/remote-app-update-safety-plan.md` and
`docs/remote-phase-f2-private-profile-design.md`.
