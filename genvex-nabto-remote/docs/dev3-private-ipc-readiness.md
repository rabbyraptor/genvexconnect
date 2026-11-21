# DEV3 private IPC bridge — deployment gate

**Status: real one-shot Core-container IPC proven; no persistent listener, App startup, integration installation, or unattended polling is authorized by this document.**

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

These were originally entirely local fake-data tests. **A later successful
real-device RPC45 -> ephemeral private bridge -> Core-container HTTP read
is documented below.** That one-shot test is not permission to start a
persistent App listener or install the integration.

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

The existing codebase already contains a callable `SnapshotHTTPServer`
(`polling_http_server.py`) and a polling runtime, but neither is active
while the installed DEV2 App remains stopped. This phase does not enable
that server, enroll/rotate tokens or deploy an unattended poller. It establishes
which safeguards a later implementation must satisfy and preserves the
existing evidence of intermittent SDK session-stage and RPC45 failures.

## Inert HTTP adapter candidate: completed offline gate

The source-only module `runtime/ipc_web_candidate.py` now creates
an **unbound** aiohttp application and handler around our existing
`snapshot_api.handle_read_request` and `ipc_auth.authorize_read`.
The same file is mirrored into `experimental/genvex_remote/`.
It is **not imported or executed** by the App's current `run.sh`
or bootstrapping code. No `run_app`, `TCPSite`, `web.run_app`,
socket bind, port exposure, or background task is included.

The handler authenticates before inspecting routes or consulting
the snapshot state; only an exact GET of `/v1/snapshot` may retrieve
a five-value validated response. It rejects unexpected methods,
query strings and request bodies (including chunked bodies). Unknown
or mismatched tokens return a redacted 401, invalid routes a redacted
404, bodies a 413, and missing/invalid snapshots a redacted 503.
The snapshot callback is synchronous and must return an already
validated, fail-closed snapshot state; it never performs an RPC itself.

`experimental/home_assistant/tests_core/test_real_ipc_web_candidate.py`
exercises the actual candidate handler without opening a socket.
The dedicated real-Core CI run `44850577962` **passed**; the
DEV3 contracts and HAOS App candidate offline checks also passed.
This proves handler input/output safety under those offline fixtures,
not safe host binding, credential provisioning or network operation.

The native HAOS App image does not yet have a reviewed `aiohttp`
runtime dependency, and the candidate is not wired into any App
entrypoint. Before enabling the IPC listener, review the exact
Supervisor network namespace, port reachability, per-install token
lifecycle, App version separation and rollback. The initial
authenticated socket test must be bounded, read-only and explicitly
operator-approved. Persistent polling requires separate authorization.

## Manual single-RPC45 IPC smoke test (operator-run, no installation)

The practical test is now implemented as
`runtime/ipc_once.py` and the existing
`scripts/haos_live_once_operator.py --ipc-once` switch. It reuses the
**known-good stopped DEV2 image solely as an ephemeral, manually
started Docker test container**. It does not install a new Supervisor
App or modify existing App options, the LAN integration, or private
profile files.

- Prompts for the same three Nabto values in the SSH TTY; passes them
  via stdin to the container. They never enter argv/env/App options.
- Calls `SDKSnapshotAdapter.poll_once()` **exactly once** (85-second
  SDK deadline, 110-second Docker deadline) and requires a valid complete
  five-sensor snapshot.
- Generates a random temporary bearer token **inside the container**,
  starts the existing minimal `SnapshotHTTPServer` on
  `127.0.0.1:0` **inside that container only**, and makes three local
  TCP requests: missing token -> 401, valid token -> 200 with the
  validated snapshot, then after clearing the in-memory snapshot ->
  503. No host ports or Supervisor service endpoints are published.
- Stops the listener, clears the snapshot, exits the container and
  runs the operator's force-remove cleanup. No unattended polling,
  retries, read/write controls or persistent changes.

The command is a useful intermediate between fake-data tests and
future internal App-to-HA networking. It demonstrates an actual Nabto
read and actual local HTTP requests in the same isolated runtime, but
it **does not** establish HA Core-to-App connectivity across the
Supervisor network. That will be a separate later deployment task.

## Operator live success and private Docker network regression

The operator ran `--ipc-once` on HAOS and confirmed:
`PASS: one RPC45 snapshot validated; private loopback IPC 401/200/503
verified`, followed by successful isolated container removal and DEV2
remaining stopped. This validates the physical-device -> vendor SDK/QEMU
-> RPC45 -> five-value snapshot -> container-local authenticated HTTP
pipeline. There was exactly one live read and no polling.

A separate **real Docker networking** workflow
`.github/workflows/dev3-real-docker-ipc.yml` subsequently passed:
GitHub Actions run `44851772005`. It launches one temporary
`python:3.12-slim` HTTP server container and one independently
isolated client container on a Docker **`--internal`** bridge with a
DNS name, synthetic device ID, fake token and fake sensor readings.
The client tests real TCP across container network namespaces,
including missing/wrong tokens returning 401 and the correct token
returning a complete validated 200 snapshot. No host port is
published; both the test container and network are destroyed.

**Scope:** These are *two complementary tests*, not the same live
end-to-end network transaction. On the user's HAOS the actual Nabto
snapshot has so far only been served to a client in the **same**
ephemeral container. The real two-container transport was verified
with **fake** data on a separate CI machine. The next field step
tests local HAOS network reachability (before any HA Core registration).

## HAOS real Core-container private-network test (fake-only; operator step)

A small host-side operator now exists at
`scripts/haos_core_ipc_network_operator.py`. It does not require any
Nabto identity or device secrets and makes **zero RPC45 calls**.

- Locates the running `homeassistant` container and inspects its actual
  Docker networks, selecting the Supervisor `hassio` bridge when
  present or one unambiguous non-default local bridge.
- Reuses the already built, locally pinned App image with a fake-only
  `offline_ipc_network_smoke.py` server, attached temporarily to that
  network with an unpredictable DNS alias. It publishes **no port**.
  The source file is mounted read-only from a root-owned staging path.
- Executes a read-only Python stdlib client **inside the running HA Core
  container** using `docker exec -i homeassistant python3 -` without
  changing any Home Assistant files, registry, integration or process.
  The client checks real TCP/DNS resolution of the temporary alias,
  rejects missing and wrong fake tokens (401), validates a synthetic
  complete five-value response with the correct fake bearer token
  (200), and rejects an unknown route (404).
- Retries only local fake TCP readiness up to five times, never SDK
  reads; immediately force-removes the temporary server container
  on either success or failure.
- Uses only synthetic readings/device identity and a test token
  embedded in test source. No real credentials or physical gateway
  interaction is involved.

This test specifically isolates the previously unverified link from
the **real HA Core container** to a private server on the **same
Supervisor bridge**. The results will not be considered verified on
HAOS until the operator runs this test and supplies its sanitized
output. The existing real-Core and two-Docker-container CI tests
remain complementary, not substitutes for this device-specific check.

## HAOS Core private-network operator: confirmed PASS (2026-11-21)

The operator provided actual HAOS inspection results:

- `CORE_NETWORK_MODE: host`, `CORE_NETWORKS: ['host']`
- `CORE_RUNNING: True`
- `HASSIO_NETWORK: bridge local`

The first private IPC test assumed Core was a bridge-network
participant, and failed during preflight. The corrected operator
discovers the temporary runtime container's private bridge IPv4 address
and executes the client from the running Core container, which shares
the host's network namespace. The actual operator output was:

```text
TEST: private Supervisor network; fake-only IPC; no Nabto requests
PASS: HA Core container reached authenticated private IPC; 401/200/404
```

This is now an **on-device verified** network/authentication boundary,
not just a CI simulation. The real Nabto SDK -> snapshot -> HTTP and
real Core -> private HTTP network paths have both passed individually.
The combined real SDK -> private App HTTP -> real HA Core sensor entity
lifecycle is **not yet** proven as one live end-to-end transaction.

All relevant DEV3 read-only, HAOS candidate, private Docker IPC,
formatting and real HA Core entity CI checks passed at
`45f5b0a5de5c6a5af9ee7ae051953b28d5c69b19`.
The generic repository HACS validation workflow remains unrelated
to this DEV3 runtime acceptance gate.

## One real RPC45 -> private IPC -> actual Core container (prepared, not yet run)

The next operator-driven integration test has now been implemented:

- `runtime/ipc_core_live_once.py` receives the same local-TTY Nabto
  credentials **and a per-run random 256-bit IPC token over stdin**.
  It makes exactly **one** SDKSnapshotAdapter.poll_once() call, validates
  the complete five-sensor result, and starts the existing authenticated
  SnapshotHTTPServer on port 18275 of the isolated container for a
  maximum of 60 seconds after the read. It has **no SDK retry or
  background poller** and clears the snapshot when the service exits.
- `scripts/haos_core_live_once_operator.py` uses the same existing
  pinned local image, read-only profile mount and mandatory profile/
  image preflight, but attaches its temporary disposable container to
  the previously verified HAOS `hassio` Docker bridge. It does not
  publish any host port or install anything.
- On the observed `homeassistant` host-network configuration, the
  operator discovers the temporary container's actual private bridge
  IP address. Inside **the running HA Core container**, it invokes
  Python stdlib `http.client` over the actual private TCP link, using
  a single token and device ID delivered by stdin, checking 401 for
  absent/wrong tokens, 200 with complete *real* RPC45 readings and
  a fresh timestamp, and 404 for an unknown route. Sensor values are
  deliberately never printed.
- The operator retries only the read-only Core-side TCP probe while
  waiting for the **single** SDK read to complete, with a 112-second
  overall deadline. In a `finally` block it force-removes the
  exact disposable container and waits for the Docker CLI to exit.
  Neither Nabto secrets nor the IPC token appear in Docker argv/env,
  Supervisor App options, Home Assistant storage or Docker logs.
- This runs a real private HTTP transaction from the Core container,
  but does **not** create HA sensor entities yet. The existing isolated
  real-Core configuration-entry tests cover those entity transitions
  separately.

Bundled runtime source mirrors
`experimental/genvex_remote/ipc_core_live_once.py`; no App
entrypoint or HA integration startup is wired to this one-shot module.
The CI gate includes mock-SDK single-flight/cleanup tests and the
**actual** stdlib Core client against a real local authenticated TCP
listener with a synthetic snapshot. At revision
`d24ee7e27c20936c3fe59f3d0a73ef99dba29687`, the DEV3
read-only remote contracts workflow `44892646302` passed.

**The remaining on-device step requires the operator to stage the
two new files and run the one-shot SSH command.** Never describe the
full live link as passed until that sanitized output has been seen.

## First combined HAOS attempt: inconclusive, diagnostic path corrected

An operator executed the first combined real SDK -> private bridge -> Core
one-shot after staging the pinned candidate. The host-side preflight
passed and prompted for the three Nabto values, but reported only:

```text
LIVE CORE ONCE: one RPC45 -> validated private HTTP -> Core read; no polling
BLOCKED: real Core IPC test incomplete; no readings disclosed
```

The original launcher discarded all runtime stdout and collapsed any
exception, SDK failure or HTTP timeout into the same message. Therefore
the cause of this attempt **cannot be inferred from the available output**.
In particular, this is not evidence that a live RPC45 snapshot failed or
that the Home Assistant network was unreachable.

The launcher was revised to:

1. Capture only a bounded, fixed diagnostic marker from the isolated
   runtime (the raw vendor probe remains private), and report specific
   allowlisted `SDK_*` failure categories; never echo arbitrary child
   stdout, stderr, secrets or readings.
2. Have the runtime emit `IPC_READY` only **after** a real RPC45
   snapshot passes validation and the authenticated private HTTP
   listener starts. The host waits for this marker over Docker's
   attached stdout rather than repeatedly contacting Core while the
   SDK connection is still in progress.
3. Make the Core HTTP request timeout a bounded recoverable client-side
   attempt, not a reason to abort the whole single-RPC test. The
   original 112-second host deadline and one-SDK-call maximum remain.
4. Distinguish a failed container launch, an SDK session/RPC problem,
   a missing private address, a Core TCP failure and a successfully
   expired private listener that Core failed to read.
5. Regression-test the exact readiness pipe with a real, temporary
   Python subprocess, allowlisted error classification, cleanup,
   token handling, and HTTP timeout handling, without a real SDK.

The user needs to **stage both** the revised
`runtime/ipc_core_live_once.py` and
`scripts/haos_core_live_once_operator.py` for the next attempt.
The previous revision is not informative enough to retry.

## Combined live HAOS Core IPC gate: PASSED (operator, 2026-11-21)

The operator re-staged the corrected host launcher (including the
`recovery_policy.py` bind mount), then performed one manually authorized
real-device test from an interactive SSH TTY. The exact successful
terminal evidence was:

```text
LIVE CORE ONCE: one RPC45 -> validated private HTTP -> Core read; no polling
PASS: one RPC45 snapshot ready for private Core read
PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP
```

This is the **first successful combined live end-to-end network test**
on the operator's actual HAOS host: physical Genvex Optima 270 via
legacy Micro Nabto SDK/QEMU -> exactly one validated read-only RPC45
snapshot -> temporary authenticated HTTP server bound inside a
disposable container on the private `hassio` bridge -> HTTP client
executed within the **running** `homeassistant` Core container.
The Core client verified missing and wrong bearer token return 401,
a correct token returns 200 with a fresh complete five-reading
snapshot, and an unknown path returns 404. No sensor values, device
ID, identity, key or token were printed.

This **does not** prove the permanent Home Assistant integration has
registered live entities. The Core-side client was a temporary
`python3 -c` stdlib probe, not the custom component coordinator.
No config entries, device registry, entity registry, App options,
network ports, or polling settings were changed. The disposable
container was force-removed by the launcher; the DEV2 App remained
stopped/manual. This proves live network transport and schema, not
unattended operational stability or production security.

Before the successful run, the initial launcher hid the actual
runtime startup error; a safe offline import test showed that
`live_once` and `ipc_core_live_once` could not import because
`recovery_policy.py` was missing from the disposable container's
bind mounts. The launcher was fixed in
`10883fbfdfe9b1428a1984f87912617d65861e74`; the operator
confirmed `PASS: missing dependency mount corrected` and the
subsequent live run passed.

**Next development gate:** create a reversible, nonpersistent
live-Core entity integration test using the actual HA coordinator,
snapshot reader and five sensor entities against this already
validated private network bridge. The user must separately authorize
any installation of a persistent App/integration or automatic polling.

## Real HA integration over real TCP in CI; ephemeral live class-probe prepared

On 2026-11-21, the dedicated Home Assistant Core 2026.11.2 workflow
verified **15 passing isolated tests** (including
`tests_core/test_real_tcp_config_entry.py` and
`tests_core/test_real_inmemory_live_client.py`).

1. The real `SnapshotHTTPServer` listens on `127.0.0.1` with an ephemeral
   port in a CI runner. A test-only resolver maps the **unchanged, pinned**
   HA integration endpoint to that loopback address. The *actual*
   `AuthenticatedSnapshotReader`, `GenvexRemoteCoordinator`, config
   entry and five registered real-Core sensor entities consume HTTP 200,
   then fail closed over HTTP 503 and 401, then recover over HTTP 200.
   Every measurement and token in this test is synthetic.
2. A separate CI subprocess tests the **exact new one-shot HA class-probe**
   against real loopback TCP while running the pinned Home Assistant
   libraries. It injects reviewed Python sources into the ephemeral
   interpreter's import namespace, makes one actual coordinator read
   through the pinned endpoint plus strict test DNS mapping, and checks
   all five sensor class projections without saving or installing the
   integration. Its first draft exposed an implicit HA ConfigEntry context
   dependency: the coordinator now accepts an explicit `config_entry`
   argument from normal integration setup. Real Core and SDK-free offline
   tests have been updated accordingly.
3. The earlier manually confirmed live HAOS test validated exactly one
   real Micro Nabto RPC45 -> short-lived private HTTP -> running Core
   **container** stdlib HTTP client. Combining it with the new in-memory
   HA class-probe on the actual HAOS host requires a **new operator-run
   one-shot test**. A CI pass is not evidence that this new field test
   has already happened.

The new standalone operator is
`scripts/haos_core_live_entity_once_operator.py`. It reuses the
existing temporary Docker launcher and its fixed private HTTP tests,
then asks an independent Python interpreter **within the running
`homeassistant` container** to import five reviewed HA component source
files in memory and validate one additional authenticated HTTP read using
the actual production reader/coordinator/sensor classes. These imports
do **not** mutate the running HA Core interpreter, register entities
in its state machine, install an integration, add an App, change
Supervisor options or start polling. The temporary Docker listener
exists only for up to 60 seconds and is force-removed on completion.

**Staging gate:** Use one reviewed, pinned Git commit. Copy
`scripts/haos_core_live_entity_once_operator.py` into
`/tmp/genvex-dev3-once/` as root mode 0600; copy exactly
`const.py`, `runtime_client.py`, `snapshot.py`,
`coordinator.py` and `sensor.py` from
`experimental/home_assistant/custom_components/genvex_remote/`
into root-owned `/tmp/genvex-dev3-once/ha_component/`
(directory 0700, individual files 0600).
No private credentials or sensor data are staged. The earlier
successful, reviewed staging files for the original live operator
must remain present; the original DEV2 App/image/profile remains
stopped/manual/read-only. The operator prompts for the same three
private credentials only in the interactive terminal and passes
them via Docker stdin, not command line/environment/files.

**Operator execution after explicit consent:**

```sh
ssh -tt -p 22222 root@rabbyshome.duckdns.org \
  python3 /tmp/genvex-dev3-once/haos_core_live_entity_once_operator.py
```

Successful fixed output adds:
`PASS: real snapshot validated by actual HA reader, coordinator and five sensor classes`
after the existing two successful single-RPC Core transport markers.
This checks the production class implementation **inside an ephemeral
Core-container interpreter**, not state registration in the running
Core process; the latter remains separately blocked on secure App
provisioning, HAOS App DNS reachability and a reviewable reversible
installation plan. Any automatic RPC polling, persistent token
provisioning, unattended App startup and UI onboarding remain
separate future authorization gates.
