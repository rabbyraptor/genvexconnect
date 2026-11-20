# Genvex Remote — experimental HAOS App (Nabto Micro 4)

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
control RPC. **The live polling path has not been activated in this App.**

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

## Next approval boundary

Offline tests for diagnostic bootstrap, IPC isolation and synthetic-only
responses already exist. The installed `dev2` App must stay stopped while
static/runtime-readiness checks are performed. An on-HAOS diagnostic start
requires **separate explicit approval**, a fresh preflight that establishes
empty credentials and no private profile/token without printing any of their
values, a tight time/cleanup plan, and verification that the App ends stopped.
Do not run live Nabto, migrate profiles, modify the working LAN integration,
or treat synthetic values as real sensor readings.

Known gaps: secure profile onboarding, production distribution of the separate
HA integration, live SDK/remote runtime validation, private App-to-Core DNS,
and end-to-end soak tests. A backup inventory entry is not equivalent to a
verified restore path.

See `docs/remote-app-update-safety-plan.md` and
`docs/remote-phase-f2-private-profile-design.md`.
