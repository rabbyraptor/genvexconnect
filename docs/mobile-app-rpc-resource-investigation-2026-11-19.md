# Genvex Connect mobile app asset investigation plan

Date: 2026-11-19  
Current baseline: [verified facts manifest](remote-nabto-verified-facts.md)

## Identified app artifacts

- Android first-party app listing: https://play.google.com/store/apps/details?id=dk.lscontrol.genvexapp ; package identifier **`dk.lscontrol.genvexapp`** (publisher LS Control A/S). Google Play listing updated 2026-09-17.
- iOS App Store listing: https://apps.apple.com/dk/app/genvex-connect/id1342181479 ; app ID **1342181479**. Bundle identifier reported by third-party listing `dk.lscontrol.genvexconnect`; this specific identifier should be confirmed against the actual IPA, not treated as independently verified.
- Nabto's LS Control partner page states its mobile apps historically used **Ionic/Cordova + Nabto RPC**: https://www.nabto.com/partners/ls-control/ . This is architectural context, not proof that the 2026 Genvex Connect build still bundles the same assets.

## Discovery result

Public LS Control/Nabto source provides **only** verified `ping.json` query 17. Neither GitHub source searches nor indexed web pages yielded a complete Optima 270 production RPC schema. A third-party Homey Genvex Connect repository uses **LAN UDP port 5570 and local register commands**, not the Nabto 4 remote Client SDK interface; see [Homey local vs RPC](homey-source-vs-remote-rpc-2026-11-19.md).

## Recommended next evidence acquisition

**Obtain a legitimate copy of the app package from an installation under the user's control**, preferably an Android APK or APK set for `dk.lscontrol.genvexapp`, or a decryptable iOS IPA the user is authorized to inspect. Avoid untrusted modified APKs and never execute an unknown downloaded package on HAOS.

Static extraction can proceed offline:

1. Identify package version and original application signing certificate/fingerprint when supported; document source and whether APK is a base/split bundle.
2. Examine archive entries without installing or executing the app; inventory `assets/www/`, `www/js/`, `assets/`, `res/raw/`, `classes*.dex`, and bundled `lib/*` entries.
3. Search **app-owned** HTML/XML/JS/text resources for `unabto_queries`, `rpcSetDefaultInterface`, `rpcSetInterface`, `rpcInvoke`, `ping.json`, `get_interface_info`, and `<query`. Use binary string scans of DEX/native modules only if necessary.
4. Extract the RPC query model from any verified application resource and manually verify names, numeric IDs, argument types, and whether they are **read-only**. Do not assume a name alone proves write safety.
5. Keep package binaries, account identifiers, tokens, device IDs, and private key/certificates out of Git. Commit only sanitized metadata and findings. Do not blindly enumerate or call undocumented queries.

**Status:** artifact not yet supplied or inspected; no additional remote telemetry query has been proven.

## Next gate

Request an authorized APK/IPA (or an extracted, non-sensitive app-owned JS/XML asset). Once obtained, perform the static source/asset inspection and identify the first *documented read-only* Optima 270 RPC for the already-working remote Nabto 4 test client.
