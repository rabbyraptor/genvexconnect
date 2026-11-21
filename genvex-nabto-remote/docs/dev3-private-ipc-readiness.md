# DEV3 private IPC bridge — deployment gate

**Status: source-only architecture review. No listener, App startup, or
Home Assistant deployment is authorized by this document.**

## Proven offline contracts

1. A real Home Assistant Core 2026.11.2 instance can set up the actual
   `genvex_remote` config entry, register five separate sensor states and
   one device-registry entry, transition all five to unavailable on failure,
   restore validated readings, and unload the config entry.
2. The actual `AuthenticatedSnapshotReader` sends exactly one
   `GET` to the strictly pinned Supervisor-internal URL
   `http://local-genvex-nabto-remote:18275/v1/snapshot`, with bearer
   authentication, no redirects, 8-second request timeout and a
   4096-byte response cap. A simulated HTTP 401 makes all five sensors
   unavailable; a later valid response restores all five.
3. An in-memory loopback exercise uses the existing, real
   `runtime/snapshot_api.py` and `ipc_auth.py` handlers together with
   the actual HA reader, coordinator, config entry and sensor entities.
   It covers authenticated 200, missing-SDK-snapshot 503, invalid
   transport-token 401 and full recovery without opening a socket.

These are entirely local fake-data tests. **No successful network IPC
transaction between a running HA Core process and a Nabto App has yet
been demonstrated.** Offline token and schema compatibility is not
equivalent to permission to start a listener.

## Remaining security and operational requirements

- **Secret provisioning.** The App's `ipc_token` must not be populated
  in Supervisor App options, a shell command or environment variable.
  A per-install random token must be created through a separately
  reviewed trusted workflow, be available only to the App and the
  corresponding HA config entry, and never appear in logs. Existing
  private Nabto key files must remain read-only and inaccessible to the
  HA integration. Token rotation must fail closed.
- **Binding and reachability.** Review exactly which interface/namespace
  the App may listen on. The fixed HTTP endpoint is intended only for
  the Supervisor App network, **not** the internet, LAN, host networking,
  Ingress, or a public port. The existing App's `host_network: false`
  setting must remain in force. A binding to `0.0.0.0` even in a
  container requires explicit network-scope review, authentication and
  firewall protection. Plaintext HTTP bearer traffic on the Supervisor
  bridge has security implications; assess feasible protected transport
  before enabling it.
- **No remote control surface.** Offer only a bounded, authenticated
  `GET /v1/snapshot`, returning a five-sensor validated projection or
  a redacted 401/404/503. No RPC write operation, credential enrollment,
  remote access control, files, arbitrary URL, proxy or debug endpoint.
  Authenticate before revealing route availability. Reject oversized
  requests and unexpected methods.
- **Read-only runtime lifecycle.** If later authorized to run polling,
  each attempt must use the existing isolated x86_64 Nabto SDK via QEMU
  and the known 85-second timeout, with no overlapping RPC calls.
  The prototype's last-good snapshot freshness limit is 180 seconds,
  and a known failed read immediately invalidates it. Do not present
  stale sensor values as available.
- **Isolation from working components.** Install a separately versioned
  DEV3 candidate only with explicit operator consent. Preserve a
  restorable backup, the existing LAN integration, the stopped/manual
  DEV2 App and its private profile. Do not repurpose the DEV2 App image
  or change existing profiles in place.
- **Operator gate.** Before moving beyond offline tests, explicitly
  agree on a reversible, bounded HAOS test: what will be installed,
  which ports and credentials will be used, exactly how many reads are
  allowed, observability of failures, and the rollback command.
  Persistent App startup and automated polling are separate,
  later approvals.

## Non-goals at this stage

This does not implement a socket listener, token enrollment/rotation,
an unattended Nabto poller, or any production deployment. It establishes
which safeguards a later implementation must satisfy and preserves the
existing evidence of intermittent SDK session-stage and RPC45 failures.
