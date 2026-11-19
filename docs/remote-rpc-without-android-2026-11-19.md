# Alternative paths to Genvex remote RPC model without Android

Date: 2026-11-19

## Question

Find the real LS Control / Genvex Connect Optima 270 Nabto 4 RPC interface model without requiring an Android device or untrusted APK.

## Current reliable baseline

- Authenticated remote `ping.json`, query ID 17, verified via Nabto 4 SDK 4.9.11 both on Linux x86_64 Steam Deck and Raspberry Pi HAOS ARM64 under x86_64 QEMU emulation.
- `get_interface_info.json` probe failed with SDK status 26 and event **2000027 = QUERY_MODEL_NO_SUCH_REQUEST**, consistent with the client-side XML containing only `ping.json`. This tells us nothing about whether the remote gateway implements that command.
- Product-specific remote telemetry query IDs and formats remain unknown. Local LAN UDP register addresses are *not* Nabto 4 RPC IDs.

## Alternatives ranked by evidence and effort

### 1. Legitimate legacy HTML Device Driver archive

Nabto's historic client architecture centrally served `html_dd.zip` containing `nabto/unabto_queries.xml` and static content. This file might be located in historical vendor/Nabto build archives or copies of a deployed HTML-DD, but no official LS Control production bundle has yet been located or verified. Avoid fabricating a device-specific URL, treating a sample demo ZIP as the Genvex bundle, or accessing unauthorized portal resources.

Upstream sources:
- https://github.com/nabto/unabto/blob/master/apps/html_device_driver/README.txt
- https://github.com/nabto/cordova-plugin-nabto/blob/master/README.md

### 2. Authorized existing iPhone captures

Previous user-authorized Proxyman/UDP captures identified HTTPS `api.lscontrol.dk:4160` and encrypted legacy Nabto UDP. Revisit existing *redacted* HTTPS transaction URL paths, response content types, and client resource/download names, not cookies, tokens, passwords or raw HAR. If the app loads its interface at runtime and the resource is observable, the file may be discoverable without an APK. Nabto UDP ciphertext should not be mistaken for accessible RPC strings. If no resource transfers are observed, this route may yield nothing.

### 3. Vendor/source inquiry

Ask **Genvex/LS Control** for the supported third-party integration path, the read-only Nabto 4 Optima 270 `unabto_queries.xml` definition, and historical HTML-DD archive or supported telemetry API. Ask **Nabto** specifically for historical HTML-DD retrieval rules, availability of customer-supplied legacy bundles, and licensing/aarch64 support for the Nabto 4 SDK. Vendor permission may be required to redistribute SDK binaries; don't presume it.

Genvex official app listing support email was shown publicly as `appservice@genvex.dk` in Google Play search results on 2026-11-19, subject to verification before sending.

### 4. Published firmware/source of corresponding LS Control controller

Inspect publicly released, authorized firmware/app resources, official updates or the supplier's own sample sources for application-level RPC handler mappings and XML. Generic Nabto `unabto_queries.xml` samples and Homey LAN register maps are not evidence of the product's remote query IDs.

### 5. Protocol/tunnel alternative – research only

The SDK documents `nabtoStreamOpen` and `nabtoTunnelOpenTcp`, but these require corresponding device-side features/ACLs. They do **not** transparently tunnel the existing LAN UDP port 5570. No supported read-only Genvex stream/tunnel endpoint has been identified. Treat as a lower-priority hypothesis, not a working workaround.

## Boundary

Do not enumerate guessed RPC IDs against the production unit; do not try write commands. Never expose a device ID, personal account, signing cert/private key or network capture to public GitHub. Do not modify the working Home Assistant local transport while investigating. Existing HAOS QEMU remote read-only ping remains the reference.

## Decision

Next **without an Android phone**: inspect redacted already-captured iPhone HTTPS metadata if available, in parallel search original HTML-DD and vendor materials. If neither yields a real RPC XML, obtain a vendor interface specification before attempting remote telemetry. This is an evidence gap, not a Nabto transport blocker.
