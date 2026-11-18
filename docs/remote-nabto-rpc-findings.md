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
