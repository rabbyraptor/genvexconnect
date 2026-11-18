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
