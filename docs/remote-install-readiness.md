# Genvex Remote — installation readiness (development branch)

## Current state

**Latest verified installation milestone (20 November 2026):** Following
explicit user approval, Supervisor built and installed
`local_genvex_nabto_remote` v`0.1.0-dev1` on ARM64. Logs show build start
17:29:02, build completion and successful install 17:30:34. The CLI then
reported `already installed` due to a subsequent installation attempt;
this does **not** mean the build failed. Supervisor shows
`state: stopped`, `boot: manual`, `version: 0.1.0-dev1` and the
Supervisor-built image `local/aarch64-addon-genvex_nabto_remote:0.1.0-dev1`
(reported 375 MB). No new App container appeared in `docker ps -a`.
The earlier test App remains `started` at `0.5.0`.
**Phase C is finished; do not reinstall.** The new App has not run, no
synthetic-only acceptance test has been performed, and no live Nabto connection
has been made. Separate explicit approval is required before configuring
`diagnostic_only: true` with all four identity/credential/token fields empty
and manually starting the App for synthetic-only tests. No secret enrollment,
private key migration, live RPC45 polling, or modification of the LAN
integration/older App is authorized. See [install plan](remote-local-haos-diagnostic-install-plan.md).


**Latest HAOS milestone (20 November 2026):** Local source for
`local_genvex_nabto_remote` was staged and discovered by Supervisor after
`ha store reload` (not `ha apps reload`). Supervisor validated its config and
found both local App configurations. `ha apps info` reports
`available: true`, `build: true`, `installed: false`,
`version_latest: 0.1.0-dev1`, `stage: experimental`, `arch: [aarch64]`,
`host_network: false`, and `state: unknown`. The existing
`local_genvex_nabto_runtime_test` remains `started` at version `0.5.0`.
The 126/126 source-only tests passed previously; Supervisor installation and
synthetic-only App runtime acceptance have **not** been performed. Historical
"not yet staged/discoverable" statements below describe earlier milestones.

**Current next gate:** read-only disk/RAM/build-prerequisite preflight, then
separate explicit authorization for Supervisor build/install **without startup**.
Benefits: exercise real HAOS App lifecycle, ARM64/QEMU build and dependencies.
Risks: high CPU/RAM/disk use on Raspberry Pi 4, possible failed build and
leftover Docker cache, and no proof of reliable remote Nabto connectivity.
No App credentials, certificates, private-key migration, live gateway session,
HA integration replacement, or changes to the existing test App are authorized.
Even after installation, a synthetic-only start requires a separate approval.
See [controlled diagnostic installation plan](remote-local-haos-diagnostic-install-plan.md).


**Not a supported one-click HAOS installation yet.** The existing working LAN
integration and the existing test App must not be replaced or modified.

Verified on the user's HAOS ARM64 host:
- 93/93 source-only backend tests including SDK subprocess adapter.
- One live Nabto RPC45 read was converted to an authenticated HTTP snapshot.
- An automatic polling diagnostic produced two successful real reads with two
  intervening failures. Fail-closed snapshot invalidation and eventual recovery
  worked; continuous stability was not established.

Staged, but not yet verified on HAOS:
- `experimental/genvex_remote/polling_runtime.py` runs the native Python
  scheduler and isolated x86_64/QEMU RPC45 probe. It reads a root-private JSON
  config file and a separate root-private IPC token file. No device write RPCs.
- `experimental/genvex_remote/polling_http_server.py` exposes authenticated
  `GET /v1/snapshot` on a private container network only.
- `experimental/home_assistant/custom_components/genvex_remote` is a separate
  read-only Home Assistant integration with five sensors. Its UI asks for the
  device ID, private runtime URL and matching IPC token. It does not collect
  the Nabto private-key passphrase.

## Offline acceptance check

On the HAOS host, the following script runs the complete backend test suite
runs the HA snapshot/transport tests, and compiles the HA integration without installing or restarting anything:

```sh
(
  set -eu
  umask 077
  runner=$(mktemp /tmp/genvex-preflight.XXXXXX)
  trap 'rm -f "$runner"' EXIT
  curl -fsSL \
    'https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts/run_haos_remote_install_preflight_v7.sh' \
    -o "$runner"
  sh "$runner"
)
```

The test uses an immutable source commit and fake data; no real gateway RPC
or certificate is needed.

## Remaining before recommending installation

1. Validate the above runtime/HA source acceptance suite on the HAOS ARM64 host.
2. Package the runtime as a distinct installable HAOS App, with a legal way to
   obtain the proprietary Nabto 4 x86_64 SDK. Redistribution rights have not
   been established. Do not commit or distribute the SDK binary.
3. Design private App-to-HA transport and securely provision a matching random
   IPC token. HTTP bearer tokens must never cross public/untrusted networks.
4. Add user-friendly, secret-safe profile enrollment/configuration and restart
   persistence. Vendor CA trust/pinning is still an explicit blocker for
   automatic certificate enrollment.
5. Run a bounded 60-second real RPC45 polling soak test; diagnose failed
   attempts without logging raw SDK data or secrets.
6. Test Home Assistant config flow, unavailable/recovery states, App lifecycle,
   and HAOS reboot. Preserve the existing LAN integration throughout.

## Intended architecture

```
Genvex Optima 270
  ↕ proprietary Nabto 4/Micro remote
isolated HAOS App: x86_64 SDK through QEMU, read-only RPC45
  ↓ validated five-sensor snapshot
native ARM64 polling runtime + authenticated private HTTP
  ↓ private IPC token
Home Assistant Core: genvex_remote (five read-only sensors)
```

The HA integration is **not** a translation layer for the iPhone app.
It uses its own SDK-backed Nabto client in a separate runtime.

## Preflight failure fixed 2026-11-20

The first HAOS runtime preflight executed **102 backend tests, 101 passing and one error**. The single error was `test_post_and_other_path_not_exposed`: a POST with `Content-Length: 0` correctly hit the body-rejection path, but `BaseHTTPRequestHandler.send_error()` emitted HTML while the client test required JSON. The HTTP server now responds with a fixed JSON `400 {"error":"bad_request"}`, adds a `nosniff` header, and rejects binding to arbitrary interfaces. Regression tests cover the rejected POST and listener binding. The HA transport test doubles were also updated to the new bounded `response.content.read(4097)` API and `allow_redirects=False` behavior. The **v5 preflight is prepared but not yet confirmed passing on HAOS**. It runs both backend and HA tests (unlike v2), and checks source syntax and manifest JSON. No real SDK session or credentials are accessed.

## HAOS App candidate staged after 119/119 source checks (2026-11-20)

**Verified by the user on HAOS:** 104 backend tests and 15 HA fake-transport/snapshot tests passed, followed by Python compilation and HA JSON manifest checks. This is a **119/119 source-only PASS**, not a live HA Core or installed-App acceptance test.

**New separate Supervisor-discoverable App source:** [`genvex-nabto-remote/`](../genvex-nabto-remote/). It has a Dockerfile based on the proven QEMU/x86_64 test-runtime approach, a manual-boot App manifest, a native Python bootstrap, a bundled copy of the 11 validated runtime modules, and fake-credential bootstrap tests. The App has `host_network: false`, no published host ports, `share:ro`, and does not touch the working Genvex LAN integration or the earlier test App.

The bootstrap expects `client.crt` and `client-encrypted.key` under `/share/genvex-remote-profile/` (separate from the existing private host profile), copies them to private App `/data/profile/` with 0600 permissions, validates a 12-digit device ID, and reads the encrypted-key passphrase and a 43+ character IPC token from App `password` options. The private token is written with mode 0600. It starts only the read-only polling runtime. The HA integration uses `http://app_local_genvex_nabto_remote:18275/v1/snapshot` and the same token. **No automatic certificate enrollment or profile migration exists.** Supervisor options are not a dedicated secret vault; manual secret entry is development-only.

**Next source acceptance test:** [`run_haos_remote_install_preflight_v7.sh`](../scripts/run_haos_remote_install_preflight_v7.sh), pinned to the candidate source and covering the 104 backend tests, 15 HA tests, 7 App bootstrap tests, source-copy parity, and compilation. **Not yet executed on HAOS.**

**Do not install this candidate yet:** the image has not been built or validated on HAOS; the profile import and IPC token UX are not finished; vendor SDK redistribution/licensing and private network isolation require review. The existing App must not be replaced.

## Separate development installation artifacts

The App candidate is now at repository root [`genvex-nabto-remote/`](../genvex-nabto-remote/) so Supervisor can discover it as a distinct App when this development repository is configured. It is manual-boot and not built/tested as an installed App yet. The Home Assistant integration stays in [`experimental/home_assistant/custom_components/genvex_remote/`](../experimental/home_assistant/custom_components/genvex_remote/) to avoid modifying the working LAN integration. The [offline App CI workflow](../.github/workflows/remote-app-offline.yml) now checks source parity, fake-credential bootstrap tests and App config, and prepares a downloadable **development-only HA integration ZIP** as a GitHub Actions artifact. The artifact is not a signed or validated production release.

The Home Assistant config flow now masks the IPC bearer token with a password selector. A matching token must be provisioned to the App separately; never publish the token or Nabto unlock secret in logs or GitHub issues.

**v7** is the latest pinned offline HAOS preflight (backend + HA + App bootstrap, source parity and compilation). Its result has not yet been reported. The previously reported v5 result of **119/119 PASS** remains the last verified source-only baseline.

## 126/126 verified and first isolated App image build prepared

**Verified by the user on HAOS (v7):** 104 backend tests + 15 HA tests + 7 App bootstrap tests, all passed; runtime source parity, Python compilation and HA JSON checks also passed. This is the current **126/126 source-only baseline**.

The next step is the pinned [`run_haos_remote_app_image_build_v1.sh`](../scripts/run_haos_remote_app_image_build_v1.sh). It downloads a fixed source commit, builds **only** a separate `genvex-nabto-remote:dev-...` Docker image for ARM64, performs the existing Nabto CLI/QEMU and x86 Python build smoke tests, and runs an offline import test without networking or secrets. It requires at least 3 GiB free on the HAOS data partition, may download/build several gigabytes, and does **not** install or start any App. The image build has **not yet been executed on the user's HAOS host**. A Docker build failure must be investigated before installing anything.

**Important security note:** the proposed `/share/genvex-remote-profile` import path is shared across HAOS Apps that have share access, even if the files are mode 0600. It is not an acceptable final private-key enrollment design. Before live installation, replace this import path with a secure, App-private enrollment/migration workflow that leaves the existing encrypted host profile untouched. Do not ask the user to copy the encrypted private key into globally shared storage as a routine installation step.

**Repository distribution note:** the App candidate currently exists on the `remote-nabto-connection` development branch; adding the default-branch GitHub repository to Supervisor will not automatically install the development-branch candidate. A suitable release branch/repository or package publication path must be prepared and verified before presenting GUI installation instructions.

## Native ARM64 CI image-build gate added

[`.github/workflows/remote-app-image-build.yml`](../.github/workflows/remote-app-image-build.yml) builds the isolated App image on a native `ubuntu-24.04-arm` GitHub runner when the candidate Dockerfile, runtime or workflow changes. It performs a no-network/no-secrets container import smoke test and verifies ARM64 architecture, App label and absence of published ports. It does **not** push/publish an image, install a HAOS App, access the user's certificate profile or connect to the gateway. **Workflow outcome is pending/unverified** until GitHub Actions reports a completed run. The local pinned [build script](../scripts/run_haos_remote_app_image_build_v1.sh) remains available for an actual HAOS-specific build check.
