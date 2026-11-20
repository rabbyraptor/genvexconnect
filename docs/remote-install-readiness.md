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
and compiles the HA integration without installing or restarting anything:

```sh
(
  set -eu
  umask 077
  runner=$(mktemp /tmp/genvex-preflight.XXXXXX)
  trap 'rm -f "$runner"' EXIT
  curl -fsSL \
    'https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts/run_haos_remote_install_preflight_v2.sh' \
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
