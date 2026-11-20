# Security decision: Home Assistant ↔ Nabto Runtime IPC

**Status: design gate, NOT deployed.** A standalone [token-checking primitive](../experimental/genvex_remote/ipc_auth.py) and [offline tests](../experimental/genvex_remote/test_ipc_auth.py) have now been staged; there is still no listener, shared-secret delivery, transport, or device enrollment endpoint. As of 2026-11-20, no authenticated IPC exists. The source-only HA scaffold intentionally uses `UnconfiguredReader` and therefore cannot manufacture live data.

## Evidence about Home Assistant App networking

- Home Assistant's [App communication guide](https://contributors.home-assistant.io/apps/guides/communication/) explains that Apps typically reach each other over the Supervisor-managed internal network by App hostname and internal service port. **Other Apps may be able to access that port**; private Docker networking is not a substitute for endpoint authentication.
- The [App environment documentation](https://contributors.home-assistant.io/apps/reference/environment/) explains the distinction between default internal network and `host_network`.
- Home Assistant published [GHSA-gh5m-4m97-c95h](https://github.com/home-assistant/core/security/advisories/GHSA-gh5m-4m97-c95h) about unauthenticated internal App endpoints unintentionally exposed by host-network assumptions. Do **not** expose a management or enrollment endpoint on the current v0.5.0 test App with `host_network: true`.

## Proposed bridge (not yet implemented)

1. Keep **existing** v0.5.0 experimental App `genvex_nabto_runtime_test` untouched. Do not add any network listener to that App or publish a port. Remote authenticated RPC45 already works in the isolated QEMU process.
2. For a separate production runtime App, **prefer `host_network: false`**, no published host ports, and an internal-only authenticated API with strict separation of `GET /v1/snapshot` and one-time enrollment. First verify Nabto remote connectivity without host networking: the previous local UDP discovery needed host networking, but the remote connection may not. Do **not assume** this until tested.
3. Protect every request with a high-entropy, per-install secret or equivalent verifiable identity, including reads; token comparison must be constant-time. Avoid exposing tokens in query parameters, entity attributes, log messages, Home Assistant state, or broad Supervisor App options. Integration and App must have a documented secure way to provision/rotate the shared secret; **that mechanism is not yet resolved**.
4. Restrict enrollment to the trusted integration backend, with user initiation, one-time password handling, rate limiting, response limits, CA pinning, CSRF protections for any optional web UI, no secrets in exception text and no fallback to an unauthenticated route.
5. Return **only** the exact versioned five-sensor snapshot JSON. No SDK raw output, credentials, certificate, private key, user details, logs, or arbitrary RPC APIs. Configured device ID must match. Enforce freshness on both App producer and HA consumer.
6. A worker must serialize SDK RPCs and bound timeouts. On failure publish health/error *without previous readings*; HA marks entities unavailable. The [read-only polling worker](../experimental/genvex_remote/polling_worker.py) and [Home Assistant snapshot validator](../experimental/home_assistant/custom_components/genvex_remote/snapshot.py) are source-only scaffolds.
7. Test with App restarts, HA Core restart, wrong/replayed tokens, read vs enrollment permissions, no-LAN/no-relay transport, invalid/mismatched snapshots, stale results, rate limits and CPU/RAM under repeated polls.

## Blocking unknowns

- Does authenticated remote Nabto RPC45 continue to work with `host_network: false`? Requires an isolated HAOS App test (no production key migration).
- Can the App and HA Core establish and rotate a truly private shared secret without manual terminal steps? Requires an explicit onboarding design. Do not ship an unauthenticated snapshot endpoint.
- The actual **legacy LS Control Nabto CA trust anchor** is not independently pinned; user password enrollment remains disabled.
- The actual x86_64 SDK has not accepted a *new* CA-issued key from our automated Python code, only the pre-existing profile.
- The legacy SDK redistributability is not established.

## Next offline acceptance gate

The next [combined HAOS development test](../scripts/run_haos_remote_dev_tests.sh) also discovers `test_ipc_auth.py`. It should verify random token generation, exact matching, missing/wrong-token rejection and non-disclosure of secrets in error strings. **A token alone is not sufficient authorization for account enrollment**: rotation, storage, authenticated provisioning, request-level permissions, transport encryption and replay handling remain unresolved. Do not expose a runtime API in the existing `host_network: true` App.

## Next user-visible milestone

A separate, authenticated internal bridge that can serve one real RPC45 batch and survive restarts. Only after that works should the HA scaffold move from `experimental/home_assistant/` to a normal installable `custom_components/genvex_remote/` directory.
