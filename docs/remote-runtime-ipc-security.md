> **Status note (21 November 2026):** Read this as a design/evidence record. Later bounded adapter and synthetic IPC experiments are summarized in [current status](STATUS.md). Some earlier descriptions below predate the later prototypes.

# Security decision: Home Assistant ↔ Nabto Runtime IPC

**Status: staged code and isolated tests; NOT a deployed production HA Core integration.** A standalone [token-checking primitive](../experimental/genvex_remote/ipc_auth.py) and [offline tests](../experimental/genvex_remote/test_ipc_auth.py) have now been staged; there is still no listener, shared-secret delivery, transport, or device enrollment endpoint. As of 2026-11-20, no authenticated IPC exists. The source-only HA scaffold intentionally uses `UnconfiguredReader` and therefore cannot manufacture live data.

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

- **RESOLVED FOR THE TESTED PATH:** the user's authenticated remote RPC45 succeeded on a disposable Docker bridge container (five readings, status 0); Supervisor lifecycle and internal IPC remain unverified.
- Can the App and HA Core establish and rotate a truly private shared secret without manual terminal steps? Requires an explicit onboarding design. Do not ship an unauthenticated snapshot endpoint.
- The actual **legacy LS Control Nabto CA trust anchor** is not independently pinned; user password enrollment remains disabled.
- The actual x86_64 SDK has not accepted a *new* CA-issued key from our automated Python code, only the pre-existing profile.
- The legacy SDK redistributability is not established.

## Disposable bridge networking validation — VERIFIED 2026-11-20

[`scripts/run_haos_bridge_remote_rpc_test.sh`](../scripts/run_haos_bridge_remote_rpc_test.sh) is a host-side development test. It starts a **temporary container from the exact already installed Nabto runtime image** using `--network bridge`, `--read-only`, a volatile `/tmp` tmpfs, no mounts or exposed ports, capabilities dropped and `no-new-privileges`. It first checks DNS from inside that isolated network. It then copies only the existing encrypted certificate + key from the protected host profile into the temporary tmpfs and prompts locally for the pre-existing unlock passphrase without echoing it. The same tested QEMU Python probe performs **one five-address read-only RPC45**. Shell cleanup deletes the disposable container (and its tmpfs). The original running App and host profile are left unchanged.

**VERIFIED result:** the user's Raspberry Pi HAOS test returned bridge DNS PASS and authenticated Nabto SDK startup/resources/session/interface/RPC statuses all **0**, five read-only sensor values, a **1,212 ms** RPC, and close/shutdown statuses **0**. The disposable container was removed. This proves the specific authenticated remote path works without host networking, while **not yet** proving Supervisor App/Core IPC or restart behavior.

**Interpretation:** a successful *authenticated* RPC in bridge mode provides evidence that the remote Nabto path does not depend on Docker host networking on this specific HAOS setup. DNS success alone is **not sufficient**. A failure can be due to blocked outbound UDP/relay, Docker DNS/firewall, an incorrect profile input or external connectivity; avoid broad architecture conclusions from an unclassified failure. The script is a development-only diagnostic and not a production credential-delivery solution. It has now run successfully on HAOS using the user's existing authorized device and encrypted profile.

## Read-only authenticated snapshot handler — staged 2026-11-20

[`snapshot_api.py`](../experimental/genvex_remote/snapshot_api.py) now includes the **socket-free** handler core for `GET /v1/snapshot`. It requires the existing prototype's bearer token validator, rejects all other paths/methods, accepts only a fresh/complete matching-device snapshot via `snapshot_contract.py`, and returns only the five public sensor fields (no secrets or arbitrary SDK data). Failures use fixed 401/404/503 JSON responses. [Offline tests](../experimental/genvex_remote/test_snapshot_api.py) cover allowed read, missing/wrong token, unauthorized routes, wrong device, stale data and secret-field rejection.

**Not a deployed server.** No listener, exposed port, token provisioning or transport encryption is implemented yet. Do not connect this prototype to the existing host-network test App; the trusted production App network and authenticated secret lifecycle remain gates.

## Two-container isolated HTTP proof — staged, NOT YET VERIFIED

[`scripts/archive/run_haos_ipc_two_container_test.sh`](../scripts/archive/run_haos_ipc_two_container_test.sh) creates a **temporary `--internal` Docker bridge** and two disposable read-only containers from the existing runtime image. It uses synthetic sensor measurements only. [`ipc_demo_server.py`](../experimental/genvex_remote/ipc_demo_server.py) is deliberately a **fake-only** `/v1/snapshot` service with no Nabto import; [`ipc_demo_client.py`](../experimental/genvex_remote/ipc_demo_client.py) requests over container-to-container HTTP. The script generates a per-run 256-bit token using Python `secrets`, copies it into tmpfs **without placing the token in shell argv or the process environment**, and checks: missing token 401, incorrect token 401, correct token 200 and five complete validated values. It uses no published ports, host mounts, live Genvex session, CA enrollment or user secrets; both containers, the private network and temporary files are removed on exit. Because the bridge is internal, its HTTP traffic has no internet path. **This test does not establish secure automatic token provisioning or production network isolation** and does not start in the installed App.

The separate HA integration's [`AuthenticatedSnapshotReader`](../experimental/home_assistant/custom_components/genvex_remote/runtime_client.py) now has a bounded, fail-closed HTTP consumer with injected session/endpoint/token, but `UnconfiguredReader` remains the active default. Its [mock tests](../experimental/home_assistant/tests/test_runtime_client.py) do not run inside real HA Core. Cleartext HTTP with a bearer token is **not an approved production design** without a documented, appropriate isolation or encryption boundary.

## Verified isolated IPC test — 2026-11-20

The user executed [`run_haos_ipc_two_container_test_v2.sh`](../scripts/run_haos_ipc_two_container_test_v2.sh) successfully on HAOS. The results show scripts staged into writable tmpfs on **both** read-only containers, no-internet private Docker bridge, correct rejection of absent/incorrect bearer token, and correct parsing of a five-value authorized **synthetic** response. The script printed `PASS: ISOLATED TWO-CONTAINER TOKEN IPC`. This confirms that the disposable test topology works. **It does not establish production security, real SDK-to-HTTP output, automatic token sharing, or HA Core connectivity.**

[`test_worker_api_contract.py`](../experimental/genvex_remote/test_worker_api_contract.py) now provides an offline unit-level contract across the fake read-only RPC callback, serial poller, atomic state, authenticated snapshot handler and strict parser. It explicitly rejects cached old data after a failed RPC. The new tests are **not yet verified on the Pi**.

## Real Nabto RPC45 to HTTP: one-shot bridge candidate — UNTESTED (2026-11-20)

A [single-use HAOS diagnostic runner](../scripts/archive/run_haos_live_rpc_to_ipc_test_v1.sh) is now staged. It launches two disposable read-only containers from the **already installed** Nabto runtime image on an isolated **non-internal** Docker bridge (outbound internet must remain available for remote Nabto), with no published host ports. It copies the existing client certificate and encrypted key only to the server container's tmpfs and requests the existing unlock passphrase through hidden terminal input. No CA registration, credential rotation, write RPC or installed App modification is attempted.

The [separately staged SDK probe](../experimental/genvex_remote/probe_remote_snapshot.py) is derived from the previously verified read-only RPC45 probe. It emits a single strict `GENVEX_READONLY_SNAPSHOT=` JSON record **after** all five readings are decoded and close/shutdown succeed. The runner validates that record with `snapshot_contract.py`. The [one-shot HTTP fixture](../experimental/genvex_remote/ipc_live_once_server.py) serves only this one approved snapshot, after token authentication, and the [second container's client](../experimental/genvex_remote/ipc_live_once_client.py) checks missing/wrong tokens and validates all five actual values, device ID and freshness. On exit, both containers, their temporary key material, snapshot, token and Docker bridge are removed. The private test token travels only by stdin/file, not as argv or environment.

**Important limits:** This is a manual **one-time** end-to-end diagnostic, not a continuously running poller or genuine Home Assistant Core process. The test has **not yet run** on the user's Pi. It intentionally uses an unencrypted HTTP test interface on a temporary dedicated Docker bridge: do not ship this exact fixture as a production service. The previous authenticated Nabto bridge test and fake two-container IPC test **passed separately**, but their combined operation remains unverified until the user runs this script. The legacy CA trust anchor, automatic enrollment, secure token provisioning, persistent App packaging and real HA Core integration still block end-user deployment.

### New staged polling lifecycle — not deployed

[`polling_service.py`](../experimental/genvex_remote/polling_service.py) provides a source-only 60-second default poll loop over the existing serialized read-only worker and fail-closed snapshot state. It has immediate first poll, safe shutdown/cancellation, no overlapping reads, no catch-up bursts and no last-good snapshot after stop or failed read. [Offline tests](../experimental/genvex_remote/test_polling_service.py) have been added for startup, duplicate-start rejection, failures, cancellation, recovery and validation. **These new tests have not been executed on HAOS**. It has no actual QEMU/SDK reader, no HTTP listener, no credential persistence, no reboot startup orchestration and no authenticated Home Assistant Core integration. The demonstrated one-shot real RPC→HTTP bridge has *not* yet been converted into a continuously running production service.

## Next offline acceptance gate

The next [combined HAOS development test](../scripts/run_haos_remote_dev_tests.sh) also discovers `test_ipc_auth.py`. It should verify random token generation, exact matching, missing/wrong-token rejection and non-disclosure of secrets in error strings. **A token alone is not sufficient authorization for account enrollment**: rotation, storage, authenticated provisioning, request-level permissions, transport encryption and replay handling remain unresolved. Do not expose a runtime API in the existing `host_network: true` App.

## Next user-visible milestone

A separate, authenticated internal bridge that can serve one real RPC45 batch and survive restarts. Only after that works should the HA scaffold move from `experimental/home_assistant/` to a normal installable `custom_components/genvex_remote/` directory.
