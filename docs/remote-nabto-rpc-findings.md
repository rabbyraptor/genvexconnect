# Remote Genvex: Nabto 4 / LS Control RPC findings

Date: 2026-11-18

## Executive finding

There is now a much more concrete candidate for the remote path: the LS Control ecosystem is documented as using the legacy Nabto 4 / Micro (uNabto) stack, and Nabto publishes a small LS Control-specific Cordova test application which discovers an LS Control device hostname and invokes its `ping.json` RPC.

This is stronger evidence than the previously known generic LS Control partner description. It identifies:
- the legacy client generation: Nabto SDK 4.8;
- the device hostname pattern: `<12-digit-id>.remote.lscontrol.dk`;
- a working RPC operation name: `ping.json`;
- the kind of device metadata returned by the ping (device number, model, slave device/model, protocol version);
- the intended client API shape: discover/prepare a host, configure an RPC interface, then invoke a `nabto://` RPC URL.

It does **not** yet prove that Genvex Connect 4.0.3 uses this exact plugin version or that the public LSC test's local AP-mode flow is the same as the app's remote authenticated flow. Treat this as a strong implementation lead, not a completed remote connection.

## Evidence

### 1. LS Control's Nabto architecture

Nabto's LS Control partner page describes:
- PIC32 device architecture using uNabto for RPC and streaming;
- iOS/Android Ionic/Cordova apps using Nabto RPC;
- a .NET server using the Nabto Client SDK .NET wrapper;
- Nabto CA authentication integrated with LS Control's own identity management.

Source: https://www.nabto.com/partners/ls-control/

### 2. LS Control-specific Nabto test application

Nabto's public `nabto/cordova-lsc-test` repository is explicitly a test app for invoking `ping.json` on an LS Control device.

Its README includes a captured run:
- Cordova app reports Nabto SDK 4.8;
- local discovery returns a hostname such as `776878486829.remote.lscontrol.dk`;
- it invokes `ping.json`;
- the JSON response contains `Devicenumber`, `Model`, `Pong`, `SlaveDevicenumber`, `SlaveModel`, and `Version`.

Important limitation: the README says the Android device should be connected directly to the gateway in AP mode. Therefore this is proof of the LSC hostname/RPC interface and local Nabto client use, not proof that this test app has been configured for remote access.

Source: https://github.com/nabto/cordova-lsc-test

### 3. Legacy Nabto 4 client API supports remote P2P and relay

The public Cordova plugin is explicitly for Nabto 4/Micro. It documents:
- `startupAndOpenProfile(username, password)` to open an installed client profile;
- `rpcSetDefaultInterface(...)` / `rpcSetInterface(...)` to provide the RPC interface definition;
- `prepareInvoke(hosts)` before invoking;
- `rpcInvoke('nabto://<host>/<query>?', ...)`;
- remote connection states including P2P, relay and Micro relay;
- legacy CA-signed profiles via email/password, but that CA/user-management flow is deprecated and only available with customer-specific CA setup.

The plugin's stated transport is encrypted direct peer-to-peer connectivity with NAT traversal and fallback through a central relay.

Source: https://github.com/nabto/cordova-plugin-nabto

### 4. Genvex device hostnames already appear in the local library

The existing `genvexnabto` local UDP implementation receives a device identifier from discovery and only accepts IDs containing `remote.lscontrol.dk`. It then records the sender's local IP address and communicates with the gateway directly over UDP port 5570.

Source: https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/genvexnabto.py

This suggests the local discovery identifier is already a Nabto-style hostname, rather than a separate arbitrary Genvex serial number. The current library still does not use that hostname to establish a remote Nabto session: it uses LAN discovery and direct UDP.

### 5. Genvex app and product support

Genvex confirms Optima 270 is directly supported by Genvex Connect, including remote access from anywhere. The current App Store listing reports Genvex Connect 4.0.3, but the public release notes do not identify the internal Nabto client generation.

Sources:
- https://www.genvex.com/produkter/genvex-tilbehor/genvex-connect
- https://apps.apple.com/dk/app/genvex-connect/id1342181479

## Updated architecture hypothesis

The most plausible legacy architecture to investigate is:

1. Resolve/identify the Optima 270 device using its Nabto hostname, likely the same `<device-id>.remote.lscontrol.dk` name seen in discovery.
2. Initialize a Nabto 4/Micro client and load the correct LS Control client identity/profile.
3. Prepare the device hostname for invocation, allowing Nabto's client to establish local, remote P2P, or relay transport.
4. Invoke the LS Control device's Nabto RPC interface.
5. Map the RPC responses into the existing Optima 270 model adapter and Home Assistant entities.

This is materially different from trying to tunnel the existing UDP protocol. It would be a Nabto RPC transport, and the existing UDP transport would remain as a separate LAN implementation/fallback.

## What remains unknown

1. Whether Genvex Connect 4.0.3 still uses Nabto 4/Micro or has a modified/new client.
2. The exact profile/identity creation and storage flow used by Genvex Connect accounts.
3. The production CA / identity-management configuration for Genvex users.
4. The complete Optima 270 RPC query definitions (the Nabto test app only demonstrates `ping.json`).
5. Whether LS Control permits a third-party client to use the same account/device identity, and under what terms.
6. Availability and licensing of a legacy Nabto 4 Linux ARM64 client library.

## Platform implications

- Nabto's public `nabto-cli` repository says the legacy Nabto 4 Client SDK libraries are obtained by contacting Nabto support. It provides a Linux shared-library build layout but does not itself provide the SDK library.
- The existing Python wrapper's published Linux binary is x86_64, not a Raspberry Pi Linux ARM64 build.
- The Android ARM64 library is an Android/JNI artifact, not a Linux ARM64 shared library.
- Nabto Edge's Linux ARM64 support is not a drop-in replacement: Edge and Micro/uNabto are different protocol generations.

Source: https://github.com/nabto/nabto-cli

## Next technical steps

1. Obtain a supported Nabto 4/Micro client SDK build for Linux ARM64 (or confirm the actual HA host is x86_64 and use the matching supported build).
2. Confirm the current Genvex Connect 4.0.3 client stack and identity/profile flow with LS Control/Nabto.
3. Obtain the Genvex Optima 270 RPC interface definition/query bundle. The LSC test app's `ping.json` can be used as a safe initial read-only handshake only once the correct supported client profile and host configuration are available.
4. Build a standalone diagnostic outside Home Assistant that reports only SDK version, sanitized error/status, connection mode (local/P2P/relay), and ping metadata. Never log account passwords, private keys, certificates, tokens, or credential payloads.
5. After a successful read-only remote RPC, implement a separate remote transport adapter and reuse the existing entity/model mapping where the RPC data semantics match.

## Safety and product notes

- No credentials have been sent to guessed endpoints.
- Do not assume a Genvex account password is itself a Nabto client profile password; the old CA flow and current Genvex app behavior must be confirmed.
- Do not ship a dependency on a discontinued or unlicensed binary without a redistribution/maintenance plan.
- For a plug-and-play product, prefer a supported ARM64 SDK or an official LS Control integration interface over bundling an undocumented x86_64 client.


## Deeper inspection: public Python wrapper and native Client API (2026-11-19)

The public `nabto/nabto4-python-wrapper` repository was inspected at source level. This yields a more concrete client-side API map than the previous high-level README review.

### 1. The wrapper exposes the actual legacy client operations

The wrapper's C extension (`extension/src/nabto.c`) binds these native Client API operations:

- `nabtoStartup(home_directory)` and `nabtoShutdown()`.
- `nabtoCreateProfile(user_id, password)`: creates a CA-signed profile for a user that already exists in a central user-management service.
- `nabtoCreateSelfSignedProfile(user_id, password)`: creates a self-signed profile; the wrapper documentation explicitly says its identity is not trusted unless the device trusts that certificate fingerprint.
- `nabtoGetFingerprint(user_id)`.
- `NabtoSession.open(user_id, key_password)`: calls `nabtoOpenSession` using an already-created profile.
- `NabtoSession.rpcSetDefaultInterface(interface_xml)`.
- `NabtoSession.rpcInvoke(nabto_url)`: synchronous RPC invocation.
- TCP tunnel open/close/status operations.

The wrapper's Python README demonstrates the profile/session/tunnel lifecycle. The C extension additionally shows the RPC bindings, even though the README's quick example focuses on tunnelling.

Sources:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/README.md
- https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/src/nabto.c
- https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h

### 2. The Python wrapper's platform packaging is not ARM64-ready as published

The wrapper's `setup.py` maps every `sys.platform == "linux"` build to the directory named `extension/linux64`. The repository contains Linux64 headers/library layout, not a Linux ARM64-specific target in that packaging logic. Therefore the published Python wrapper cannot be treated as a ready-to-install Raspberry Pi/HAOS ARM64 dependency.

This is a packaging observation, not proof that the underlying Nabto C Client SDK could never be built for ARM64. It means we would need an ARM64-compatible native client library and a deliberate build/package path rather than installing this wrapper unchanged.

The wrapper is also not itself a pure-Python implementation: its extension links against `libnabto_client_api`. Merely installing the Python package does not remove the native-library architecture dependency.

Source:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/setup.py
- https://github.com/nabto/nabto4-python-wrapper/tree/master/extension

### 3. Profile creation and opening are separate operations

The API distinction matters:

- `nabtoCreateProfile(id, password)` creates a CA-signed certificate/profile through the configured central user-management service.
- `nabtoOpenSession(id, password)` opens a session using a profile already stored on the client.
- `nabtoCreateSelfSignedProfile` is a different trust model and cannot be assumed to work with a production Genvex gateway unless that gateway already trusts the fingerprint.

The native header documents errors including `NABTO_PORTAL_LOGIN_FAILURE`, `NABTO_CERT_SIGNING_ERROR`, and `NABTO_OPEN_CERT_OR_PK_FAILED`. This confirms the legacy client has explicit profile/CA setup and certificate lifecycle, rather than simply taking a device ID and password and connecting.

No attempt should be made to feed the Genvex Connect account password into these functions without knowing that the Genvex app actually provisions the same Nabto profile. The current public sources do not establish that mapping.

Source:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h

### 4. RPC invocation needs an interface definition

The Python wrapper's RPC flow is:
1. Open a Nabto session with a locally available profile.
2. Call `rpcSetDefaultInterface(interface_xml)` with an RPC interface definition.
3. Call `rpcInvoke("nabto://<device-host>/<query>")`.
4. Receive the RPC result as a string (the wrapper converts the C API response to a Python string).

The Cordova plugin exposes the same conceptual flow, but with per-host or default interface registration and a separate `prepareInvoke(devices)` call. The Python wrapper inspected here does not expose `prepareInvoke` as a Python method; do not assume the two wrappers have identical method surfaces.

Sources:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/src/nabto.c
- https://github.com/nabto/cordova-plugin-nabto/blob/master/www/nabto.js

### 5. What this means for our next implementation step

We can now define the client-side software boundary without inventing the protocol:

- A process/service owns the Nabto client runtime and its private profile directory.
- It exposes a small local interface to Home Assistant.
- It uses a known RPC interface definition and explicit RPC URLs.
- It returns structured results to the existing Genvex model/entity layer.
- Credentials and private-key material remain in the service's protected storage and are never written to HA YAML, logs, or entity attributes.

However, we still lack two concrete inputs needed for a successful Genvex RPC:
- an authorized client profile accepted by the Genvex/LS Control CA, and
- the Optima 270 RPC interface definition/query names beyond the demonstrated `ping.json` example.

The public Python wrapper is useful as an API reference and potential x86_64 diagnostic harness, but its current Linux packaging is not a ready ARM64 solution. The open-source uNabto repository is the embedded/device-side SDK; it should not be confused with the separate legacy Nabto Client SDK used by the Python wrapper.


## Source-level clarification: what the LS Control Cordova test actually proves (2026-11-19)

The full `nabto/cordova-lsc-test/www/js/index.js` and README were inspected. This narrows an earlier interpretation: the test app does **not** demonstrate a remote RPC call to an LS Control/Genvex device.

### Exact test-app flow

The app embeds one LS Control RPC interface definition containing only:

- Query name: `ping.json`
- Query ID: `17`
- Request parameter: `ping` (`uint32`)
- Response fields: `Pong`, `Devicenumber`, `Model`, `Version`, `SlaveDevicenumber`, `SlaveModel`, and a raw `UserNames:` field.

Its LS Control invocation sequence is:

1. `startupAndOpenProfile()` with the plugin's default guest profile.
2. `bindToWifi()`.
3. `getLocalDevices()`.
4. Filter for a discovered hostname containing `lscontrol`.
5. `prepareInvoke([device])`.
6. `rpcSetDefaultInterface(lscRpcInterface)`.
7. Invoke `nabto://<local-lscontrol-host>/ping.json?ping=1885957735`.
8. Clear the Wi-Fi binding.

The README explicitly instructs that the Android device must be connected directly to the gateway in AP mode. Its example output confirms a successful local ping and shows sample metadata, but that sample is not evidence about the user's specific gateway.

After clearing the Wi-Fi binding, the app separately invokes `demo.nabto.net/wind_speed.json` as a generic remote-connectivity demonstration. It does **not** invoke the LS Control hostname remotely.

Sources:
- https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js
- https://github.com/nabto/cordova-lsc-test/blob/master/README.md

### What `prepareInvoke()` actually does in the public Cordova plugin

The Android implementation of `prepareInvoke` iterates over supplied hostnames, caches them, and applies free-tier/ad gating logic. It does not itself establish a Nabto session or prove that a device is reachable. The actual RPC invocation is performed separately by `rpcInvoke()`.

This means our earlier shorthand that the test app's `prepareInvoke` step demonstrates remote discovery/connection was too strong. The test app proves the RPC API usage pattern and local LS Control ping, not the remote LS Control authentication path.

Source:
- https://github.com/nabto/cordova-plugin-nabto/blob/master/src/android/Nabto.java

### Important consequence for the Genvex investigation

We now have a known, read-only LS Control query definition (`ping.json`) and its expected response schema. We do **not** have:
- a public LS Control remote-client example using a Genvex hostname,
- the user's gateway's actual ping response from the remote path,
- the Optima 270 datapoint/setpoint RPC definitions,
- evidence that the public guest profile can access the user's registered remote gateway.

The sample test-app ping response reports `Model=1141`, but this is only the README's example device. It must not be treated as the model ID of the user's Optima 270. The existing `genvexnabto` library independently parses device model and slave model from its local ping response and selects an adapter from those values; that is the model-identification step we should preserve if we later obtain an RPC response for the user's own gateway.

### Updated evidence boundary

- **Confirmed:** The public LS Control test app can issue `ping.json` to a locally discovered LS Control device using Nabto 4.8.
- **Confirmed:** The query interface is an XML definition embedded in the test app source.
- **Confirmed:** The test app's remote demonstration targets `demo.nabto.net`, not the LS Control gateway.
- **Not confirmed:** Remote access to a Genvex gateway using the test app, guest profile, or a third-party profile.
- **Not confirmed:** Any Optima 270 RPC methods beyond `ping.json`.

This correction supersedes any implication elsewhere in this document that `cordova-lsc-test` itself proves remote LS Control RPC.


## Related community implementation discovered: glutter/genvexassistant (2026-11-19)

A separate community project, `glutter/genvexassistant`, implements a Java 17 service and Home Assistant add-on for Genvex Optima 270 / Model 2010 over the local Micro Nabto UDP interface.

Relevant source:
- https://github.com/glutter/genvexassistant
- https://github.com/glutter/genvexassistant/blob/main/src/main/java/GenvexClient.java
- https://github.com/glutter/genvexassistant/blob/main/src/main/java/GenvexProbe.java
- https://github.com/glutter/genvexassistant/blob/main/ADDRESS_MAP.md

### What is useful for our investigation

1. The project independently implements the local Genvex UDP handshake on port 5570, including the CP_ID email payload and a ping handshake.
2. It confirms a read-only register-scan approach using only DATAPOINT_READ (`0x2d`) and SETPOINT_READ (`0x2a`).
3. Its `GenvexProbe` scans addresses 0–127 and records raw response bytes, then watches selected addresses over time.
4. It identifies fan telemetry as:
   - datapoint 18: supply fan duty, raw/100;
   - datapoint 19: extract fan duty, raw/100;
   - datapoint 35: supply fan RPM;
   - datapoint 36: extract fan RPM;
   - setpoint read address 7: fan stage, noted as unreliable on some firmware;
   - datapoint 24: a temperature register, not the fan-stage register.
5. Its published Optima 270 map substantially matches the existing `superrob/genvexnabto` model mapping already used in this investigation.
6. Its dashboard/service includes fan-stage estimation from duty and RPM and keeps observed fan state separate from the requested/commanded stage.

### Important scope limitation

This is a local-network implementation. Its configuration requires a Genvex IP and registered email, and its Java client sends UDP to the device at port 5570. It does not provide a Nabto cloud relay client or prove remote connectivity from outside the summer-house LAN. It therefore cannot be used as the remote transport solution without additional supported remote transport.

### Why we should keep it as a reference

This is a useful independent implementation for validating the Optima 270 register map and the semantics of the values we eventually expose through Home Assistant. Its read-only probe is especially useful as a model for safe telemetry validation. We should not transplant its fan-control policy wholesale; our immediate focus remains remote data access and preserving the existing integration's entity/model layer.

The project's address map reports some firmware-dependent behavior: setpoint read address 7 can be inactive/always zero, and read address 24 may not reliably reflect a commanded fan stage. This reinforces the need to treat fan duty/RPM as observed state and a setpoint as requested state, rather than conflating them.


## 2026-11-19: DATA packet structure and repeated fan-change correlation

A new passive analysis of three user-supplied fan-change captures identified the 70-byte packet's exact Nabto framing: 16-byte DATA header, 4-byte CRYPTO payload header, 2-byte suite code `0x230A`, and 48 bytes of AES-CBC/HMAC-SHA256 crypto data. The crypto data is 16-byte IV + one 16-byte ciphertext block + 16-byte truncated HMAC; under the published uNabto padding scheme, the plaintext is at most 15 bytes.

All nine manually marked fan changes across the 15:08, 15:12 and 15:17 captures have a 70-byte client DATA request 74–385 ms before the entered timestamp. Each request is followed by a 24-byte `NOTIFY_MICRO_ACK` and a DATA response. This is strong correlation, not proof of the RPC meaning.

A notable anomaly: the three PCAPs are cumulative byte-prefix snapshots, not independent captures. All **1,325 distinct server-to-phone DATA/CRYPTO packets in the largest v3 file** have the same first 16 crypto-data bytes (`00..0f`), matching the public uNabto repository's explicitly dummy `nabto_random()` implementation. This requires confirmation against the actual LS Control firmware/build; it is not being treated as a proven vulnerability or as a way to decrypt/forge packets.

Detailed offsets, capture timings, public-source mapping, and caveats are documented in [nabto-data-packet-structure-2026-11-19.md](nabto-data-packet-structure-2026-11-19.md).

No packet replay, credential extraction, or integration-code changes were performed.


## 2026-11-19: Official Nabto 4 SDK and identity-model research

Official Nabto documentation confirms that the legacy Nabto 4 Client SDK binaries are not publicly distributed with the current CLI source: the Nabto CLI README instructs developers to contact Nabto support for the legacy SDK libraries. The current `nabto-client-sdk-releases` repository starts at v5.12.0 and is for Nabto Edge, not Micro. The Android `arm64-v8a` library is a JNI/AAR artifact and is not a Linux aarch64 shared library.

The profile flow is also more specific than a generic email/password login. TEN025 says a Nabto client profile consists of a private key and associated public certificate; profiles live in the Nabto home directory and the private key is unlocked when opening a session. CA-signed profile creation contacts the configured Nabto webservice and requires an existing verified account. The Cordova plugin marks `createSignedKeyPair(email,password)` as deprecated and notes that CA/user-management services require customer-specific setup. Its `startupAndOpenProfile(username,password)` method opens an already-installed keypair and decrypts its private key; it is not itself the account-provisioning step.

Earlier capture evidence of a client certificate with the account email in its X.509 Subject is consistent with the traditional CA-signed identity model, but does not prove the current Genvex Connect 4.0.3 enrollment implementation. Do not assume the account password can be used as a new Nabto profile password without LS Control confirmation.

Nabto's 2026-09-08 support policy lists Nabto 4 as maintenance-only (security updates, no new features) with no published end date. This is more precise than calling it abandoned, but does not guarantee a Linux aarch64 client build.

See [nabto4-client-sdk-availability-and-identity-2026-11-19.md](nabto4-client-sdk-availability-and-identity-2026-11-19.md) for source links, profile semantics, the IV observation, and vendor questions. No integration code was changed.
