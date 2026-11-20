# Genvex Remote — installation readiness (development branch)

## Current state

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
    'https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts/run_haos_remote_install_preflight_v6.sh' \
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

**Next source acceptance test:** [`run_haos_remote_install_preflight_v6.sh`](../scripts/run_haos_remote_install_preflight_v6.sh), pinned to the candidate source and covering the 104 backend tests, 15 HA tests, 7 App bootstrap tests, source-copy parity, and compilation. **Not yet executed on HAOS.**

**Do not install this candidate yet:** the image has not been built or validated on HAOS; the profile import and IPC token UX are not finished; vendor SDK redistribution/licensing and private network isolation require review. The existing App must not be replaced.
