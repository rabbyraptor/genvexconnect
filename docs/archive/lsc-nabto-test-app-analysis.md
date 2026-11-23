# Nabto LS Control test app: source-level clarification

> **2026-11-19 update:** The assertions below about what *this upstream sample* demonstrates remain accurate: its LS Control ping is local. **Separately, our own authenticated Linux x86_64 Nabto SDK 4.9.11 test has now successfully executed remote `ping.json` (query 17) with status 0 and a gateway JSON response.** See the [verified facts manifest](../remote-nabto-verified-facts.md). The complete production controller RPC model remains unknown.

Date: 2026-11-18

The source of `nabto/cordova-lsc-test` was inspected, not only its README.

File: https://github.com/nabto/cordova-lsc-test/blob/main/www/js/index.js

## What the code actually does

The app defines a Nabto RPC interface containing one query:

- Query name: `ping.json`
- Query ID: `17`
- Request: `ping` as uint32
- Response: `Pong`, `Devicenumber`, `Model`, `Version`, `SlaveDevicenumber`, `SlaveModel`, `UserNames:`

The app then:
1. Calls `nabto.startupAndOpenProfile()` with no explicit username/password.
2. Reads the Nabto SDK version.
3. Calls `bindToWifi()`.
4. Calls `getLocalDevices()`.
5. Filters for a host containing `lscontrol`.
6. Calls `prepareInvoke([device])`.
7. Registers the RPC interface.
8. Invokes `nabto://<device>/ping.json?ping=1885957735`.
9. Calls `clearWifiBinding()`.

After that, it separately tests remote access to `demo.nabto.net`, not to the LS Control device.

## Important correction

This source does **not** demonstrate a remote connection to an LS Control/Genvex device. Its LSC ping is explicitly local: the README requires the Android device to be connected directly to the gateway in AP mode. The remote test targets Nabto's public demo device.

What it does establish:
- LS Control's Nabto device RPC includes `ping.json` with the above request/response schema.
- The LSC device hostname returned by discovery has the form `<12-digit-id>.remote.lscontrol.dk`.
- The LSC test uses Nabto SDK 4.8.
- The Cordova API sequence for a local LSC RPC is concrete and reproducible.

What it does not establish:
- That Genvex Connect 4.0.3 uses this exact code or SDK version.
- That the LSC hostname is remotely reachable using a generic Nabto profile.
- Which account/CA/profile mechanism is used for remote Genvex Connect access.
- The RPC query definitions for Optima 270 datapoints and setpoints.

## Implementation consequence

Do not treat `ping.json` as a complete Optima 270 API. It is a device-identification/handshake query. The next necessary artifact is the production Genvex RPC interface definition and supported client identity configuration, together with a compatible Nabto 4 Linux client SDK.

The existing local UDP implementation remains a separate transport and should not be replaced by this test-app code.
