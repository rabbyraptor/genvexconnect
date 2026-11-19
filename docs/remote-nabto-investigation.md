# Remote Nabto investigation

## Goal

Investigate whether Home Assistant can reach a Genvex ECO 360 R H / Optima controller remotely through the same supported remote path used by Genvex Connect, without a VPN or additional hardware at the installation.

This work is experimental. The existing integration remains a local UDP implementation; this document does not claim that cloud access is available.

## What the current integration does

- Discovers gateways with UDP broadcast on port 5570.
- Uses the device's local IP/port and a Genvex Connect account email as the protocol's authorized identity.
- Sends the Genvex/Nabto connection request directly to the discovered gateway.
- Uses the existing GenvexNabto library and model adapters to read/write controller data.

The current integration has no cloud login, remote tunnel establishment, or remote-device discovery implementation. Adding an account password field alone cannot create that transport.

## Nabto research findings

The related Nabto 4 Python wrapper exposes profile creation, sessions, RPC and TCP tunnels. However:

- Its documented `createProfile(email, password)` path is for a dedicated Nabto user-management service configured for that deployment.
- The Nabto C API documentation says this is not a generic login mechanism for arbitrary Nabto Cloud/AppMyProduct applications.
- The public wrapper repository ships Linux x86_64 binaries, not an ARM64/Raspberry Pi build.
- The old Micro Nabto stack used by legacy LS Control products is not interchangeable with Nabto Edge.
- Public LS Control/Nabto sample projects demonstrate parts of the older client-side RPC flow, but do not establish the current Genvex Connect app's cloud configuration or grant a third-party cloud API.

Therefore, the first technical blocker is identifying the exact remote transport and identity configuration used by the current Genvex Connect service/app—not guessing a portal hostname or sending credentials to a generic Nabto endpoint.

## Safe diagnostic principles

1. Never log the Genvex account identifier, password, private key, certificate, tokens, or complete credential payloads.
2. Never send credentials to an unverified host or guessed Nabto portal.
3. Log only the stage, SDK/library version, sanitized error name/code, and elapsed time.
4. Keep remote transport isolated from the existing local transport so local functionality remains testable.
5. Do not store a second copy of credentials in diagnostics or debug output.
6. Treat all experiments as read-only until a remote session is proven stable; write/control calls require separate validation.

## Investigation sequence

### Phase 1 — Identify the official app's remote configuration

Establish, from public project evidence and user-authorized observation of the installed app, which client stack, portal/CA configuration, device identifier format, and session/tunnel mechanism are in use.

Do not infer that the legacy `nabtoCreateProfile` flow is the current Genvex Connect login flow.

### Phase 2 — Validate SDK feasibility

Determine whether a compatible Micro Nabto client SDK exists for the architecture running Home Assistant. If not, evaluate a supported isolated service/runtime only if it can be maintained and packaged reliably. Do not bundle x86_64 binaries into an ARM64 integration.

### Phase 3 — Build a standalone diagnostic

Before integrating with Home Assistant, create a small diagnostic that reports:

- SDK initialization success/failure
- configured client stack and SDK version
- profile/session stage reached
- sanitized error code/name
- whether a remote P2P or relay path was established
- elapsed time for each stage

The diagnostic must not print credentials or key material.

### Phase 4 — Home Assistant transport integration

Only after Phase 3 proves a supported remote session, add a transport abstraction and retain the current local UDP transport as a separate option. Reuse the existing model adapter and entity layer where possible.

## References

- Genvex Connect Home Assistant integration: https://github.com/superrob/genvexconnect
- GenvexNabto Python library: https://github.com/superrob/genvexnabto
- Nabto 4 Python wrapper: https://github.com/nabto/nabto4-python-wrapper
- Nabto Cordova plugin: https://github.com/nabto/cordova-plugin-nabto
- LS Control Nabto test app: https://github.com/nabto/cordova-lsc-test
- Official Genvex Connect product information: https://www.genvex.com/produkter/genvex-tilbehor/genvex-connect


## Raspberry Pi 4 / HAOS architecture finding

The target Home Assistant host is a Raspberry Pi 4 running 64-bit ARM (aarch64).

This rules out directly loading the Linux x86_64 shared library bundled by the existing `nabto4-python-wrapper`. Do not attempt to install that wheel on the Pi or copy its x86_64 shared object into HAOS.

A potentially relevant lead is the public Nabto 4 Android Client API repository. It contains an Android `arm64-v8a` JNI library, but this is an Android/Bionic JNI artifact, not a documented Linux ARM64 client SDK. It cannot be treated as a drop-in `libnabto_client_api.so` for Home Assistant. Extracting or reusing it would require understanding its JNI boundary, runtime dependencies, licensing and compatibility; it is not the preferred production path.

The public Nabto Edge SDK has Linux aarch64 build support, but Edge and Micro are explicitly incompatible. It cannot connect to the existing Micro Nabto Genvex gateway unless LS Control migrates the device/service to Edge.

The public Nabto 4 CLI project explicitly says the legacy client SDK is obtained by contacting Nabto support. This is currently the most credible route to determine whether an ARM64 Linux client build exists or can be supplied.

### Updated decision

1. Ask Nabto whether the legacy Nabto 4/Micro Client SDK is available for Linux aarch64 and whether its use is permitted for a third-party Home Assistant integration.
2. In parallel, ask LS Control/Genvex for the supported remote integration interface or written authorization and technical details for their current Genvex Connect service.
3. Do not build against Android JNI or Nabto Edge as a substitute for the Micro client.
4. Keep local UDP support as the working fallback. Remote support remains blocked pending a compatible client SDK and the correct Genvex identity-management configuration.

### Additional references

- Nabto 4 Android client API (Android arm64 JNI, not Linux ABI): https://github.com/nabto/android-client-api
- Nabto 4 Client SDK CLI build requirements: https://github.com/nabto/nabto-cli
- Nabto Micro vs Edge compatibility: https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html


## Genvex Connect account flow: important new evidence

The current official Genvex Connect product page explicitly lists Optima 270 as directly compatible with the app. The ECO 360 R product page states that it ships with Optima 270 and has built-in internet connectivity for app control and remote monitoring. The Optima 270 setup documentation says the controller exposes a secure-communication Device-ID and an internet-connection status.

The official Genvex Connect quick guide for the legacy Internet Gateway describes:
- account registration using an email address;
- an automatically generated password sent to that email address;
- the first account as the owner;
- additional app users signing in with the owner's email and password.

The guide is for the older external gateway setup, so its precise onboarding details must not automatically be assumed to match the current Optima 270 app flow. It does establish that Genvex Connect credentials are distinct from the email-only identity field used by the local Home Assistant integration.

The Nabto Cordova plugin's public API documents a legacy `createSignedKeyPair(email, password)` operation. Its description says the email/password authenticate against central Nabto CA user-management services and the same password encrypts the local private key. The plugin also explicitly marks this flow deprecated and says Nabto CA services are no longer part of the standard platform and require customer-specific setup. Its normal session startup opens a previously installed keypair; it is not itself a generic cloud login.

Nabto's LS Control partner architecture page describes Ionic/Cordova mobile apps using Nabto RPC and a .NET server using the Nabto Client SDK, with Nabto CA authentication integrated into custom identity management. This is strong historical/architectural evidence, but it does not prove that Genvex Connect app v4.0.3 still uses the same Cordova plugin or CA flow.

### Revised hypothesis

A plausible legacy flow is:
1. The app obtains/creates a signed Nabto client profile using the Genvex account credentials against LS Control's configured CA/user-management service.
2. The app opens a Nabto session using that stored profile.
3. The client prepares the Genvex device hostname/ID and uses Nabto RPC over a P2P or relay connection.
4. The device's embedded uNabto endpoint handles the RPC calls.

This is a hypothesis to verify, not an implementation specification. In particular, the CA portal hostname, identity service, device hostname format, RPC interface definitions, and current app SDK generation remain unknown.

### ARM64 clarification

The Android Client API repository includes an ARM64 Android JNI binary packaged in an Android AAR. This confirms that Nabto has shipped a Micro client implementation for Android ARM64, but it is built for Android's runtime/ABI and JNI bridge. It is not a Linux ARM64 `libnabto_client_api.so` and cannot be loaded directly by a Raspberry Pi Home Assistant OS process.

The public Cordova plugin source confirms that Android and iOS use platform-specific native wrappers around the Nabto 4 client. Reusing the Android binary on Linux would require an Android runtime/JNI host and would still not solve the missing Genvex app configuration or provide a maintainable HAOS deployment. This is not recommended for the product.

### Questions for Nabto / LS Control

- Is Genvex Connect v4.0.3 still based on Nabto 4/Micro, or has it migrated to another transport?
- Does LS Control still operate a Nabto CA/user-management service for Genvex Connect accounts?
- Is third-party client access permitted for a customer-owned Optima 270 device?
- Can Nabto provide a Linux aarch64 build of the legacy Nabto 4 Client SDK, or a supported alternative?
- What is the official device hostname/ID mapping and RPC interface definition for Optima 270?
- Is there a supported server-side API or customer integration route that avoids reverse-engineering the mobile app?

No credentials have been sent to any endpoint as part of this investigation.


## Existing Optima 270 command coverage — confirmed

The command definitions are already present in the separate `superrob/genvexnabto` dependency, not duplicated in this Home Assistant repository. The Optima 270 model adapter identifies controller model 2010 / device number 79265 and loads the Optima 270 register map.

### Existing read datapoints

The Optima 270 adapter currently requests:
- Supply, outside, exhaust, extract and frost-protection temperatures
- Relative humidity
- Supply and extract fan duty cycles and RPM
- Preheat and reheat PWM
- Bypass active state and analog bypass position
- Two Optima 270 alarm datapoints
- Rotor speed

### Existing writable/readable setpoints

The Optima 270 model currently defines:
- Fan speed (levels 0–4)
- Temperature setpoint
- Bypass opening offset
- Bypass turn-off threshold
- Forced bypass speed and temperature
- Reheating enable
- Humidity control enable
- Boost enable and duration
- Filter days and filter reset

The model file also contains commented-out supply/extract airflow level setpoints, explicitly described as write-locked in the gateway. These are not currently supported as writable Optima 270 setpoints.

### Important transport distinction

The current Python library does not use the Nabto Client SDK to establish a cloud session. It sends the reverse-engineered Genvex protocol as UDP datagrams directly to the device's IP address and port 5570. It handles discovery, U_CONNECT, ping, encrypted datapoint/setpoint reads and setpoint writes itself.

The Nabto Cordova plugin, by contrast, exposes Nabto RPC and TCP tunnelling APIs. A TCP tunnel is not a transparent transport for the existing UDP datagrams. Therefore, we cannot simply point the current UDP socket at a Nabto TCP tunnel and expect it to work.

For remote support, one of the following must be established:
1. Genvex exposes an RPC interface that provides the same datapoints/setpoints; implement a separate RPC transport and map its values to the existing model/entity layer.
2. Nabto/LS Control provides a supported UDP-capable remote tunnel/transport to the device's UDP service; adapt the transport carefully and validate packet/session semantics.
3. An official server-side API exists and is supported for third-party use.

This makes the remaining work much more specific: identify the actual remote RPC/tunnel endpoint and authentication configuration. The Optima 270 datapoint/setpoint map itself is not the primary unknown.

### Existing source references

- Optima 270 model map: https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/models/optima270.py
- Local UDP transport and command send/receive flow: https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/genvexnabto.py
- Model adapter and Optima 270 device identification: https://github.com/superrob/genvexnabto/blob/master/src/genvexnabto/genvexnabto_modeladapter.py


## Additional community implementations checked

Two independent community projects provide useful cross-checks:

- Homey's Genvex Connect app advertises Optima 270 support over the local network/LAN. Its public listing exposes fan-level and temperature control, filter reset, sensor readings, bypass and alarms, but does not advertise remote cloud access from a separate network.
- HairingX's newer `nilan_connect` Python client explicitly describes itself as a local client for gateways over `micro_nabto`. It documents Optima 270 as read-tested on a unit and uses the account-paired email plus a gateway host/device ID. Its companion Home Assistant integration explicitly says local network / no cloud. This is a second independent implementation of the local path, not a cloud API.
- The ESPHome `genvex-optima-270` project uses the Optima controller's RS-485/Modbus connection and a separate ESPHome-compatible board. It is a useful protocol/point-map reference, but it adds hardware and wiring at the installation and therefore does not meet this project's current no-extra-hardware requirement.

These projects strengthen the conclusion that the known public community integrations are local-network solutions. They do not establish a supported third-party cloud endpoint for Genvex Connect.

### Current technical boundary

The public code gives us the Optima 270 point map and local Micro Nabto transport. Public Nabto material gives us historical RPC client concepts and LS Control's broad architecture. What is still missing is the bridge between them: the current Genvex app's concrete remote host/identity configuration and its RPC interface definitions or a supported remote UDP tunnel.

Without that bridge, implementing a remote client now would require guessing protocol endpoints or app-specific credentials. That would be brittle and could send credentials to the wrong service. The next productive step is technical confirmation from LS Control/Nabto or an authorized inspection of the app's own connection metadata while it is operating—not blind endpoint probing.


## Follow-up research: independent Python Micro Nabto implementation and remote packet distinction (2026-11-19)

### 1. A third independent local implementation is now available

The newer HairingX projects provide two related repositories:

- https://github.com/HairingX/nilan_connect
- https://github.com/HairingX/modbus_event_connect
- Home Assistant integration: https://github.com/HairingX/ha_nilan_connect

The Nilan Connect README explicitly says that Genvex Optima 270 values have been read from a real unit. It also explicitly describes the client as communicating with the gateway over the local `micro_nabto` protocol, with no cloud connection. The companion HA integration likewise describes itself as LAN-only.

The important new detail is that `modbus_event_connect` contains a pure-Python, asyncio-based Micro Nabto transport:

- `MicroNabtoConnection` owns a UDP datagram endpoint.
- It sends discovery broadcasts to `255.255.255.255:5570`.
- It can rediscover a known device ID on the local network.
- It performs the U_CONNECT handshake, ping, DATA exchanges and request/response correlation.
- It handles Micro ACK notifications, retransmissions, idle sessions, reconnect backoff and device-busy responses.
- The library deliberately records connection diagnostics without exposing the paired email or device ID.

Primary source files:
- https://github.com/HairingX/modbus_event_connect/blob/main/src/modbus_event_connect/micro_nabto/_connection.py
- https://github.com/HairingX/modbus_event_connect/blob/main/src/modbus_event_connect/micro_nabto/_wire.py
- https://github.com/HairingX/nilan_connect/blob/main/src/nilan_connect/_optima_270.py
- https://github.com/HairingX/ha_nilan_connect

This is a useful independent reference for the local transport and for a more robust HA data model. It is not a remote client implementation: the connection sends UDP datagrams to a configured host/port and its rediscovery mechanism uses local broadcast. No CA/profile provisioning, basestation rendezvous, NAT traversal or relay client is implemented in these files.

### 2. The local-versus-remote crypto difference is now independently corroborated

The HairingX Python wire implementation constructs local DATA requests with crypto code `0x000A`. The official uNabto source defines this as `CRYPT_W_NULL_DATA`: a CRYPT payload using the null-data security mode, not AES encryption.

The remote Genvex Connect capture already documented in `observed-lscontrol-cloud-api.md` contains DATA/CRYPTO packets with code `0x230A`. The official uNabto definitions compose this as:

- CRYPT operation: `0x0002`
- SECR mode: `0x0008`
- AES-CBC: `0x2000`
- HMAC-SHA256: `0x0300`
- Combined: `0x230A`

This gives us a much stronger explanation for why the local Python/Java clients cannot simply be pointed at the remote endpoint. Their local request builder uses the null-data suite and local gateway handshake assumptions; the observed remote traffic uses AES-CBC/HMAC-SHA256. The encrypted application payload is not available from the capture.

Sources:
- https://github.com/HairingX/modbus_event_connect/blob/main/src/modbus_event_connect/micro_nabto/_wire.py
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet_util.h
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_protocol_defines.h
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_crypto.c

### 3. Reinterpretation of the captured remote endpoint

The user-authorized passive capture documented in `observed-lscontrol-cloud-api.md` contains recurring UDP traffic to `80.208.69.3:30815`, including 70-byte DATA/CRYPTO packets using `0x230A` and 24-byte `NOTIFY_MICRO_ACK` responses.

The endpoint's ownership and role have not been independently verified. It must not yet be labelled as the Genvex device, a Nabto relay, or a cloud API.

Nabto's published legacy architecture explains why this distinction matters: the basestation helps devices register and clients locate them; after connection establishment, client and device communicate directly when possible, with relay as a fallback. Therefore an observed public UDP peer could be part of a direct peer path or a relay path. Packet structure alone does not distinguish those cases.

Source:
- https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf
- https://www.nabto.com/partners/ls-control/

### 4. What the public sources say about the current client boundary

Nabto's LS Control partner page describes the LS Control architecture as uNabto on embedded PIC32 hardware, Ionic/Cordova apps using Nabto RPC, and a .NET server application using the Nabto Client SDK. It also describes CA-based authentication integrated with LS Control's custom identity management.

The public Cordova plugin README marks the old `createSignedKeyPair(email, password)` CA flow as deprecated and says the CA services require customer-specific setup. The same README says new solutions should use a different security design, such as PPKA or authentication tokens. This means we must not treat the Genvex app password as a generic Nabto profile password or invent a CA endpoint.

The public Nabto CLI README says the legacy Nabto 4 Client SDK libraries are required to build the client and are distributed separately. Nabto Edge has Linux ARM64 support, but Nabto's own documentation explicitly says Edge and Micro are incompatible. Edge cannot be substituted for the existing Genvex Micro device.

Sources:
- https://github.com/nabto/cordova-plugin-nabto
- https://github.com/nabto/nabto-cli
- https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html
- https://github.com/nabto/nabto-embedded-sdk

### 5. Updated technical assessment

What is now well supported by evidence:

- The local Optima 270 point map is available from several independent implementations.
- At least three independent community implementations support the local Micro Nabto path.
- The newer HairingX transport provides a pure-Python reference for local Micro Nabto framing and robust session handling.
- The user's remote Genvex Connect capture contains Nabto Micro DATA packets using the AES-CBC/HMAC-SHA256 suite and Micro ACK notifications.
- LS Control's published architecture has historically used a Nabto Client SDK on its server side and custom CA-based identity management.

What remains unknown:

- Whether Genvex Connect v4.0.3 uses exactly the same legacy Cordova/CA flow described in the public LS Control material.
- The actual role of `80.208.69.3:30815` in the observed session.
- The supported remote client identity/profile configuration for this particular Genvex account and device.
- The production Optima 270 RPC interface definitions beyond the public test app's `ping.json`.
- Whether a supported legacy Nabto 4 Linux ARM64 client library is available for a distributable HAOS add-on.

### 6. Revised next steps — no blind endpoint probing

The next work should use the evidence already collected and source-level analysis:

1. Keep the local Micro Nabto implementation unchanged as a working baseline.
2. Treat the observed remote UDP exchange as the confirmed remote Nabto-format path, while leaving the endpoint role explicitly unassigned.
3. Continue source analysis of the official Nabto client API and LS Control test app to separate profile creation, profile opening, host preparation, RPC invocation and tunnel setup.
4. Use only passive observation of normal app operation if another capture becomes necessary; do not replay requests, guess RPC names, probe undocumented endpoints or test credential payloads.
5. Keep remote transport isolated behind an adapter. Do not change the Optima 270 model/entity layer until a supported remote session and a documented/read-only RPC are available.
6. Evaluate the old Client SDK as a product dependency only after its supported platforms, licensing and redistribution terms are known. Do not substitute Edge or Android JNI binaries for a Linux Micro client.

No credentials, private keys, certificates, tokens or redacted application values have been added to this document.


### 7. Reuse and packaging notes for the HairingX reference

The two HairingX Python libraries inspected here publish MIT licenses. Their current project metadata also states:

- `modbus_event_connect` is in Alpha development status and requires Python `>=3.14`.
- `nilan_connect` is in Alpha development status and requires Python `>=3.14`.
- The companion HA integration pins `nilan_connect==0.7.0` and declares `iot_class: local_polling`.

This makes the code legally easier to evaluate for reuse than an unlicensed repository, but it is not automatically a drop-in dependency for every Home Assistant Core release or deployment. Before adopting it, verify the Python runtime used by the target HA release, test the package in the actual HA environment, and pin a reviewed version.

Sources:
- https://github.com/HairingX/modbus_event_connect/blob/main/LICENSE
- https://github.com/HairingX/modbus_event_connect/blob/main/pyproject.toml
- https://github.com/HairingX/nilan_connect/blob/main/LICENSE
- https://github.com/HairingX/nilan_connect/blob/main/pyproject.toml
- https://github.com/HairingX/ha_nilan_connect/blob/main/custom_components/nilan_connect/manifest.json


## HAOS-first reassessment (2026-11-19)

The investigation priority is now exclusively: **make remote Genvex monitoring work in the existing Home Assistant OS installation**. Commercial packaging, product strategy, redistribution scenarios and future customer support are out of scope unless they directly block a working HAOS implementation.

### What the source code tells us about the current HA integration

The current `superrob/genvexconnect` integration:

- Is a normal Home Assistant custom integration with platforms for sensor, binary sensor, climate, switch, number, button and select.
- Depends on `genvexnabto==1.5.4`.
- Creates `GenvexNabto(authenticatedEmail)`, then either discovers a device on the local network or accepts a manually configured local IP and port.
- Waits for local discovery, calls `connectToDevice()`, waits for the connection and then waits for fresh data.
- Does not initialize a Nabto Client SDK, create/open a Nabto profile, resolve a remote hostname through a basestation, or establish a remote P2P/relay session.

The email entered in this integration is the device's paired/authorized email identity for its local Micro Nabto connection. It is not, by itself, a Genvex Connect cloud login implementation.

Source files:
- https://github.com/superrob/genvexconnect/blob/main/custom_components/genvex_connect/manifest.json
- https://github.com/superrob/genvexconnect/blob/main/custom_components/genvex_connect/__init__.py
- https://github.com/superrob/genvexconnect/blob/main/custom_components/genvex_connect/config_flow.py

### The ARM64 finding is now more conclusive

The Python wrapper's `setup.py` hard-codes the Linux platform directory to `linux64`; the repository's packaged native libraries are for x86_64 Linux. It does not contain a Linux aarch64 build.

The Nabto Android repository does contain an `arm64-v8a` JNI library, but that is built for Android and is not a Linux shared library suitable for direct loading by HAOS.

An independent Nabto 4 project, `danibram/caleon`, confirms the distinction from a real implementation:
- Its ordinary transport is a pure-Rust local UDP implementation and builds for Linux ARM64.
- Its optional official Nabto 4.3 SDK transport is explicitly x86_64 Linux only.
- It obtains the closed SDK libraries from the same Nabto Python wrapper distribution.
- It explicitly documents that the SDK mode is unavailable on ARM NAS/Raspberry Pi.

This is strong corroboration that the missing Linux ARM64 Micro Client SDK is a real platform limitation, not just an omission in our Python wrapper setup script.

Sources:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/setup.py
- https://github.com/nabto/android-client-api
- https://github.com/danibram/caleon
- https://github.com/danibram/caleon/blob/main/README.md
- https://github.com/danibram/caleon/blob/main/Dockerfile

### What this means for the current HAOS target

Assuming the HAOS host is the Raspberry Pi 4 / 64-bit ARM installation already identified in this project:

- The existing local Genvex integration can run on ARM because it is Python and uses the local UDP transport.
- The existing x86_64 Nabto Client SDK wrapper cannot be imported as-is on that host.
- The Android ARM64 JNI library is not a valid replacement.
- Nabto Edge's ARM64 SDK is not a valid replacement because Edge cannot speak the legacy Micro protocol.
- A custom HAOS add-on does not magically solve a missing native ARM64 library: it still runs on the host's Linux architecture unless it emulates another architecture, which would add complexity and would not be a sensible first test.

### Updated practical options, ranked for HAOS

1. **Find an actual Linux aarch64 Nabto 4/Micro Client SDK binary or supported source build.** This is the cleanest path if Nabto has one that is not publicly listed. If obtained, it could be wrapped in a small Python package or a dedicated HAOS add-on and tested independently of the HA integration.
2. **Determine whether the remote app exposes a documented read-only RPC or service API that does not require the closed Client SDK.** The existing Genvex entity/model layer could then be reused behind a separate remote transport. We must first establish the real RPC interface and authentication requirements from authorized evidence.
3. **Investigate a pure-Python implementation of the remote Micro client only if the required protocol, identity material and crypto/session setup are documented or otherwise legitimately available.** The local HairingX implementation is not enough: it uses the local null-data suite and local discovery assumptions, while the observed app traffic uses suite `0x230A` (AES-CBC/HMAC-SHA256). Do not simply change the suite constant and assume remote operation will work.
4. **Use the existing local integration when HAOS is on the same LAN as the ventilation unit.** This is already the proven baseline, but does not solve the remote summer-house requirement.

### Immediate next experiment

Before changing the integration, establish the exact HAOS host architecture and runtime from Home Assistant's own System Information page, then check whether any available Nabto 4 client artifact matches that architecture and ABI. If the host is aarch64 and no Linux Micro client exists, stop trying to install the x86_64 wrapper on HAOS and concentrate on the documented remote RPC/API path or obtaining a compatible client library.

No new credentials or remote requests are needed for this architecture check.


## Public Nabto release matrix checked (2026-11-19)

A further check of Nabto's own current repositories resolves an apparent contradiction: Linux ARM64 Nabto client binaries do exist publicly, but the available ARM64 release is **Nabto 5 / Edge**, not the legacy Nabto 4 / Micro client required by the Genvex traffic.

Evidence:

- The `nabto-client-sdk-releases` repository explicitly says it contains Nabto Client SDK releases from v5.12.0 onward. This is the Edge generation.
- Nabto's own `nabto-cli` README explicitly marks that CLI as Nabto 4/Micro and says the legacy Client SDK libraries must be obtained separately from Nabto.
- The current `nabto-cli` GitHub Actions workflow fetches Nabto Client SDK 4.9.11 and lists only `linux64` for Linux, plus `mac-arm64` for macOS. It does not list Linux aarch64.
- The current `nabto4-python-wrapper` was updated on 2026-10-27 to SDK 4.9.11 and still hard-codes Linux to `linux64` in `setup.py`.

So the previous conclusion should be stated precisely: **there is no publicly documented Linux aarch64 Nabto 4/Micro client artifact in the official sources checked**. We cannot conclude that Nabto has never built one privately or can never provide one.

The existence of the Edge ARM64 library does not unblock Genvex: Nabto documents Edge and Micro as incompatible protocol generations. Do not install the Edge library as a substitute.

Primary sources:
- https://github.com/nabto/nabto-client-sdk-releases/blob/main/README.md
- https://github.com/nabto/nabto-cli/blob/master/README.md
- https://github.com/nabto/nabto-cli/blob/master/.github/workflows/build.yml
- https://github.com/nabto/nabto4-python-wrapper/blob/master/setup.py
- https://github.com/nabto/nabto4-python-wrapper/commit/8ab0cb550d3d8eb9f16148283daa042cf9d1fbc5
- https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html

### HAOS deployment conclusion

A dedicated HAOS app/add-on remains a valid way to isolate a native transport service and its dependencies. Home Assistant's current app build documentation supports multi-architecture images for `amd64` and `aarch64`, and exposes `BUILD_ARCH` / `TARGETARCH` to select architecture-specific build behavior.

However, containerization only solves dependency isolation and packaging. It does not convert the Edge client into a Micro client or supply a missing Micro ARM64 binary. The add-on route becomes actionable as soon as one of these exists:

- a Linux aarch64 Nabto 4/Micro SDK;
- a supported, documented Genvex remote API/RPC client that can run on aarch64;
- or a separately verified remote transport implementation that does not depend on the closed SDK.

Home Assistant app build references:
- https://contributors.home-assistant.io/apps/guides/dockerfile/
- https://github.com/home-assistant/docker-base

### Next HAOS-side check

The next user-side check should be read-only and only needs to establish the actual architecture reported by the running HAOS host. From the Terminal & SSH app, run:

```sh
echo "=== HAOS host architecture ==="
uname -m
echo
echo "=== Home Assistant installation info ==="
ha info 2>/dev/null | grep -Ei 'arch|machine|version|operating_system' || true
```

Expected architecture names include `aarch64` (64-bit ARM) or `x86_64` (64-bit Intel/AMD). This check does not change configuration or contact the Genvex device.


## QEMU user-mode feasibility on Raspberry Pi 4 (2026-11-19)

The confirmed HAOS host is:

- Home Assistant OS 18.5
- Machine: `raspberrypi4-64`
- Host architecture: `aarch64`

A new candidate route is to run the official Nabto 4 Linux x86_64 CLI under **QEMU Linux user-mode emulation** inside a dedicated ARM64 Home Assistant app.

### Why this is technically plausible

QEMU user-mode can launch Linux programs compiled for a different CPU architecture on the same operating system kernel. It translates guest system calls to the host kernel. QEMU's documentation explicitly notes that Linux user-mode processes can run inside containers.

This differs from full system emulation:
- It does not boot a second x86_64 operating system or emulate a whole PC.
- The ARM64 HAOS Linux kernel remains the host kernel.
- QEMU translates the x86_64 process instructions and system calls.
- The emulated process can use host-provided resources, subject to QEMU's syscall and ABI support.

QEMU documentation:
- https://www.qemu.org/docs/master/user/
- https://www.qemu.org/docs/master/user/main.html
- https://www.qemu.org/docs/master/about/emulation.html

### Nabto CLI artifact now identified

The official Nabto CLI v1.3.0 release (2026-10-27) publishes `nabto-cli-linux.zip`. Its release notes identify that artifact as Linux x86_64 and say it uses Nabto Client SDK 4.9.11.

The current official build workflow:
- builds the Linux artifact on `ubuntu-24.04`;
- downloads the Nabto 4.9.11 `linux64` client library;
- packages the CLI and `libnabto_client_api.so` together.

The CLI README explicitly identifies this as the legacy Nabto 4/Micro client, not Edge.

References:
- https://github.com/nabto/nabto-cli/releases/tag/v1.3.0
- https://github.com/nabto/nabto-cli/blob/master/.github/workflows/build.yml
- https://github.com/nabto/nabto-cli/blob/master/CMakeLists.txt
- https://github.com/nabto/nabto-cli/blob/master/README.md

### Runtime dependencies that must be handled

The release ZIP bundles the Nabto SDK shared library, but that does not mean it bundles the complete Linux runtime. The executable is built on Ubuntu 24.04 and may depend on the x86_64 ELF loader, glibc, libstdc++ and other system libraries.

Therefore the ARM64 app must provide an x86_64 userspace runtime compatible with the binary. A likely test layout is:
- ARM64 app base and ARM64 QEMU user emulator;
- QEMU's x86_64 user-mode executable;
- the official Nabto CLI and its bundled Nabto shared library;
- a small Ubuntu 24.04 x86_64 runtime/sysroot for the ELF loader and required libraries.

QEMU's `-L` option provides the ELF interpreter prefix/sysroot. We must inspect the actual release binary's ELF interpreter and dynamic dependencies before deciding the minimum runtime contents. Do not assume Debian Bookworm's glibc is new enough for a binary built on Ubuntu 24.04.

### QEMU availability on ARM64

Debian publishes `qemu-user-static` for arm64. The package includes statically linked user-mode emulators, including x86-64 emulation. The full Debian package is large, so the app build should extract and copy only the required `qemu-x86_64-static` executable into the final image rather than installing every emulator and its package metadata.

References:
- https://packages.debian.org/bookworm/arm64/qemu-user-static
- https://packages.debian.org/bookworm/qemu-user-static

### HAOS packaging implications

A dedicated ARM64 Home Assistant app is still the appropriate isolation boundary:
- HA Core remains native ARM64 and does not load an x86_64 Python extension.
- The Nabto CLI runs as a separate QEMU-emulated process.
- A small native ARM64 bridge/service can communicate with it over a local Unix socket or loopback TCP.
- The existing Genvex integration can later communicate with that bridge without importing the x86_64 shared library.

Home Assistant app build guidance supports ARM64 app images and documents multi-architecture builds:
- https://contributors.home-assistant.io/apps/guides/dockerfile/
- https://contributors.home-assistant.io/apps/guides/publishing/
- https://contributors.home-assistant.io/apps/guides/testing/

### Important limitations and unverified points

This is a feasibility hypothesis, not a proven working configuration.

Still to test:
1. The exact official Nabto CLI v1.3.0 binary starts under ARM64-hosted `qemu-x86_64`.
2. Its dynamic loader and all shared-library dependencies resolve from the selected x86_64 sysroot.
3. The CLI can initialize the Nabto 4.9.11 SDK under emulation.
4. QEMU's translated socket operations support the UDP/TCP behavior used by the Nabto client.
5. Threading, timers, signals and crypto operations used by the SDK behave correctly.
6. Runtime overhead on the Raspberry Pi 4 is acceptable for a low-frequency ventilation integration.

The QEMU documentation confirms syscall translation and Linux threading support in general, but it does not certify this particular Nabto binary or its networking behavior. A small isolated test must prove those points before we build a Genvex connection flow.

### Revised next steps

1. Build a minimal ARM64 test app containing QEMU user-mode and the official Nabto CLI release.
2. Inspect the release binary's ELF architecture, interpreter and dynamic dependencies during the image build.
3. Run only the CLI version/help command under emulation first; do not provide credentials or contact the Genvex device in this first test.
4. If that succeeds, run a harmless local socket test under QEMU to verify translated networking.
5. Only then test Nabto SDK initialization and continue with the separately unresolved Genvex identity/profile and RPC configuration.

This QEMU route supersedes the earlier statement that an add-on would not be a sensible first experiment: a dedicated add-on can isolate the emulator and x86_64 runtime without modifying HAOS or Home Assistant Core. It does not remove the need for valid Genvex remote identity configuration or RPC definitions.

No Genvex credentials, private keys, certificates, tokens or new remote requests are involved in this feasibility test.


## HAOS test app scaffold created (2026-11-19)

A minimal, isolated Home Assistant app scaffold has been added under:

`haos-apps/genvex-nabto-runtime-test/`

Files:
- `config.yaml` — ARM64-only, manual startup, no exposed ports.
- `Dockerfile` — native ARM64 build stage obtains QEMU user-mode static emulator and official Nabto CLI v1.3.0; a foreign-platform Ubuntu 24.04 x86-64 image supplies the x86-64 runtime filesystem; final image is native ARM64 Home Assistant base.
- `run.sh` — logs host architecture, QEMU version, and runs Nabto CLI `-v` under emulation; it does not connect to Genvex.
- `DOCS.md` — test scope and expected result.

The repository now also has a root `repository.yaml` so the app can be discovered as part of a Home Assistant app repository after the branch is available to the Supervisor.

### Important status

This is a **scaffold only**. It has not yet been built or run on the Raspberry Pi. Do not treat the Dockerfile's assumptions about the x86-64 sysroot, dynamic library resolution, or QEMU behavior as verified until the Home Assistant build and app log confirm them.

The test is deliberately limited to the official CLI's version command. It does not configure credentials, perform discovery, open sessions, invoke RPCs, create tunnels, or contact Genvex.

### Current installation path for testing this branch

Because this work currently lives on the `remote-nabto-connection` development branch, the most direct test route is to copy the app folder into HAOS's `/local_apps` directory using the official local-app workflow. The current Home Assistant documentation identifies `/local_apps` as the directory scanned for locally developed apps and supports installing them from Settings > Apps > Local apps.

References:
- https://contributors.home-assistant.io/apps/first-app/
- https://contributors.home-assistant.io/apps/guides/dockerfile/
- https://contributors.home-assistant.io/apps/guides/repository/

### Source/build references checked

- QEMU user-mode translates guest system calls to the host kernel and supports running Linux user-mode processes in containers: https://www.qemu.org/docs/master/user/main.html
- Debian Bookworm ARM64's `qemu-user-static` package includes `/usr/bin/qemu-x86_64-static`: https://packages.debian.org/bookworm/arm64/qemu-user-static/filelist
- Ubuntu 24.04 publishes ARM64 `qemu-user-static` builds as well, confirming the host architecture is supported: https://packages.ubuntu.com/noble-updates/arm64/qemu-user-static
- Home Assistant base images support `aarch64`, and the official Dockerfile guide recommends Debian/Ubuntu base images when software requires glibc: https://contributors.home-assistant.io/apps/guides/dockerfile/

The next action is to install this local app on the actual HAOS host and inspect the image build result. If the build fails, use the exact Docker build error to refine the sysroot and package contents before attempting any Genvex network activity.


## Nabto CLI initialization verified and HAOS test app v0.3.0 (2026-11-19)

### Source-level correction to the 0.2.0 interpretation

Inspection of the official Nabto CLI source `src/nabto_cli.cpp` shows that `main()` calls `init(result)` immediately after parsing arguments and **before** dispatching `--version`, `--help`, `--certs` or `--discover`.

The shared `init()` function calls:

1. `nabtoStartup(homeDir)` (or `nabtoStartup(NULL)` when no custom home is supplied);
2. `nabtoInstallDefaultStaticResources(NULL)`.

Consequently, the successful 0.2.0 `--version` and `--help` runs already proved that Nabto SDK startup and default static-resource installation completed under QEMU. The earlier conversational interpretation that these commands ran before SDK initialization was incorrect; the upstream source resolves this.

Source: https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp

### Version 0.3.0 diagnostic scope

The test app has been advanced to 0.3.0 on the `remote-nabto-connection` branch.

It adds two read-only operations, each using a fresh temporary Nabto home directory:

- `--certs`: exercises certificate-store enumeration without accessing any pre-existing user profile. Output is captured and suppressed so certificate names and fingerprints do not enter logs.
- `--discover`: exercises the CLI's local Nabto discovery API through QEMU. Output is captured and suppressed so discovered device IDs do not enter logs. The process is limited to 25 seconds.

The temporary directory and captured output are removed when the app stops. No profile is opened, no certificate is created, and no pairing, RPC, stream, tunnel, remote hostname or Genvex control request is attempted.

### Discovery result interpretation

The upstream CLI's `--discover` branch calls `showLocalDevices()` and then exits with status 0 without checking the helper's return value. Therefore, a zero process exit status does **not** prove that the discovery API succeeded. The test records only the number of output lines and suppresses all raw output. A nonzero line count is evidence that the CLI emitted discovery results; zero lines is inconclusive between no local devices and an internal discovery failure.

This test exercises local-network discovery only. It does not establish remote Nabto connectivity or reveal the remote Genvex identity/profile configuration.

### Next decision point

After the user installs and runs 0.3.0:

1. Confirm that the isolated `--certs` operation completes without error.
2. Inspect the discovery output-line count (without exposing device identifiers).
3. If discovery behaves correctly, design a separate, explicitly bounded test for remote SDK/profile behavior only after the actual Genvex Connect identity mechanism and authorized remote endpoint are established. Do not guess credentials, profile names, basestation settings or RPC URLs.


## Full remote login capture update (2026-11-19)

A full user-authorized login PCAP and two matching LS Control API HAR exports have now been analyzed. The detailed sanitized record is in [remote-login-flow-capture-2026-11-19.md](remote-login-flow-capture-2026-11-19.md).

Newly confirmed observations:

- Two multipart POST operations to `api.lscontrol.dk:4160`: `com#3=7` with `usno#5` empty, then `com#3=8` with `usno#5=1`. Both return HTTP 200 and `{"Status":"1"}`. Field meanings remain unknown; the requests expose no email/password/token/cookie.
- Two TLS connections with SNI `lscontrol.nabto.com` to `52.29.115.156:443`.
- Two WebSocket upgrades returning HTTP 101: device-specific `/handshake` at `34.249.112.159:80`, and `/gateway` at `3.255.115.248:80`. The `/gateway` TCP connection remains open through the capture, but no WebSocket application frames are visible. Neither endpoint's application role is established.
- UDP 5566 controller-associated exchanges, STUN activity on UDP 3478/3479, and local discovery broadcasts on UDP 5570.
- A remote UDP session to `80.208.69.3:30795` with the same Nabto Micro DATA/CRYPTO structure and crypto suite `0x230A` already identified in earlier captures. The 24-byte notification packets include `NOTIFY_MICRO_ACK` (code 3).

The new PCAP contains 395 packets over approximately 28.37 seconds. Its remote UDP endpoint role remains unassigned (device/peer, relay, or other Nabto infrastructure). The remote UDP port differs from earlier captures and must be treated as session-specific.

### Interpretation correction

Do not describe the overall flow as a proven strictly sequential chain in which the LS Control API finishes before all Nabto activity begins. The full PCAP shows overlapping connections, and the HAR timestamps do not establish a reliable one-to-one mapping for every encrypted TLS record. The supported conclusion is that the API, Nabto infrastructure, controller/STUN traffic, WebSocket handshakes and remote Micro UDP session all occur during the same login/connection attempt; their causal dependencies remain unknown.

### Current API-first conclusion

The HAR responses still contain no telemetry or control values. A pure REST translation layer based only on the two observed API operations is therefore unsupported by current evidence. A higher-level translation layer may still be useful, but it would need a verified remote transport/API beneath it. The remote Nabto Micro session is now independently visible in the full capture.


## Marked fan-speed-change capture update (2026-11-19)

A new PCAP with a precise `FAN_SPEED_CHANGE` marker confirms that a remote Nabto Micro UDP session was active during the user action. The phone exchanged DATA/CRYPTO packets using suite `0x230A` with `80.208.69.3:30721`; the 24-byte notifications decode as `NOTIFY_MICRO_ACK`.

A 70-byte client DATA request occurred 1.619 seconds after the marker and received a 70-byte DATA response. The same request/response pattern recurred 13.574 seconds later, with an identical server response payload. This means the 70-byte exchange is a candidate for comparison, but it cannot yet be labelled as the fan-speed write. The regular 310-/134-byte exchanges continued around the marker, with one 2.046-second interval that may be worth comparing in future captures but is not conclusive on its own.

The remote UDP port was `30721` in this session, reinforcing that the port varies and must not be hard-coded.

See [fan-speed-change-capture-2026-11-19.md](fan-speed-change-capture-2026-11-19.md) for the full packet-level analysis and evidence boundaries.
