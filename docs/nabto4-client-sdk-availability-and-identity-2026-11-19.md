# Nabto 4 Client SDK availability and identity model

Date: 2026-11-19
Branch: `remote-nabto-connection`

## Executive summary

The supported implementation route remains the official Nabto 4/Micro Client SDK, not a hand-built DATA-packet client. Current public Nabto documentation clarifies three important points:

1. The legacy Nabto 4 Client SDK binaries are not publicly distributed through the current public SDK release repository. Nabto's own `nabto-cli` build instructions say to contact Nabto support for the legacy SDK libraries.
2. The public `nabto-client-sdk-releases` repository explicitly replaces the old Nabto 5 releases repository only from version 5.12.0 onward. Those are Nabto Edge releases, not Nabto 4/Micro.
3. A Nabto profile is a local private-key/certificate identity. The Cordova `startupAndOpenProfile(username, password)` operation locates an installed keypair and decrypts its private key; it is not itself a generic cloud login. The legacy `createSignedKeyPair(email, password)` flow is deprecated and requires a customer-specific CA/user-management setup.

This means an email/password pair alone is not a sufficient technical specification for a third-party remote client. We need LS Control/Genvex to confirm how the current Genvex Connect app obtains and provisions its Nabto profile, and Nabto to confirm a supported Linux aarch64 SDK build and distribution terms.

## 1. Legacy SDK availability

### Official Nabto CLI build instructions

The public `nabto/nabto-cli` repository states that building its CLI demo requires the legacy Nabto 4 Client SDK libraries and explicitly instructs developers to contact Nabto support for download information. The repository expects a platform library named `libnabto_client_api.so` on Linux, but the README does not specify Linux ARM64 availability.

Source: https://github.com/nabto/nabto-cli (README, SDK installation)

### Current public SDK release repository

The public `nabto/nabto-client-sdk-releases` repository says it replaces `nabto5-releases` for releases from v5.12.0. Its artifacts are therefore the newer Nabto Edge client SDK, not the legacy Nabto 4/Micro SDK.

Source: https://github.com/nabto/nabto-client-sdk-releases (README)

### Android ARM64 is not Linux ARM64

The public `nabto/android-client-api` repository documents an Android `arm64-v8a` JNI library inside an Android AAR. It is an Android-native/JNI build, not a Linux aarch64 `libnabto_client_api.so`. It must not be treated as a drop-in library for HAOS on Raspberry Pi.

Source: https://github.com/nabto/android-client-api (README)

### Nabto 4 support status

Nabto's Security and Support Policy dated 2026-09-08 lists Nabto 4 as being in maintenance, with security updates only and no new features; no end date is currently set. This is more precise than describing Nabto 4 as simply abandoned, but it does not guarantee that a suitable Linux ARM64 client binary is available.

Source: https://www.nabto.com/docs/developer/systems/security-support.html

## 2. Client profile and identity model

### Profile storage and unlocking

Nabto's TEN025 client-application guide explains that `nabtoOpenSession()` uses a user profile's private key. Profiles are stored in the Nabto home directory supplied to `nabtoStartup()`, and `nabtoGetCertificates()` can enumerate available profiles. The private key and associated public certificate must already be available to the client library, either pre-installed or generated.

Source: https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf (section 5.5)

### CA-signed profile provisioning

TEN025 says `nabtoCreateProfile()` creates a private/public keypair and contacts the configured Nabto webservice to obtain a CA signature. This requires an existing verified account on that webservice. The document says Nabto's former central services still run for legacy clients, but new CA-signed deployments require the solution owner to provide and maintain the user-management services, with Nabto support contacted for details.

The Cordova plugin's `createSignedKeyPair(email, password)` method describes the email/password as credentials for the central user-management service; the password is also used to encrypt the local private key. The plugin explicitly marks this method deprecated and says Nabto CA services are no longer part of the standard platform and require customer-specific setup.

Sources:
- https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf (section 5.5.1)
- https://github.com/nabto/cordova-plugin-nabto (API documentation for createSignedKeyPair)

### Opening an existing profile is not account provisioning

The Cordova plugin describes `startupAndOpenProfile(username, password)` as locating an installed keypair associated with the username and decrypting its private key with the password. The method does not create a profile or prove that the password is sent to the device.

Source: https://github.com/nabto/cordova-plugin-nabto (API documentation for startupAndOpenProfile)

### What this means for Genvex Connect

Earlier capture analysis recorded a Nabto client certificate whose X.509 Subject contained the account email. That is consistent with the traditional CA-signed identity model described in TEN036, where the certificate subject carries a user identifier and the device authorizes that identity.

However, the available evidence does not establish that Genvex Connect 4.0.3 still uses the public Cordova plugin's deprecated `createSignedKeyPair` flow, nor does it reveal the current LS Control CA portal or profile-generation procedure. Do not assume the app account password can simply be used as a new client's Nabto profile password.

Sources:
- https://downloads.nabto.com/assets/docs/TEN036%20Security%20in%20Nabto%20Solutions.pdf (section 8.1)
- https://github.com/nabto/cordova-plugin-nabto

## 3. RPC interface requirement

Nabto TEN025 explains that a client must load the device's RPC interface definition (the legacy `unabto_queries.xml` model) before invoking RPC methods. The model defines query names, numeric IDs, request parameters and response parameters. The client then invokes a URL such as `nabto://<host>/<query>?` through the Client API.

The LS Control test application demonstrates `ping.json`, but that is not a complete Optima 270 interface definition. The existing Home Assistant local integration's point map is not automatically equivalent to the device's Nabto RPC query model.

Source: https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf (sections 5.2 and 6)

## 4. Relevance of the observed constant responder IV

The three user-supplied fan-change PCAPs are cumulative snapshots of one recording, not independent captures. The largest v3 file contains **1,325 distinct server-to-phone Nabto DATA/CRYPTO packets** from the observed remote UDP endpoint (the earlier 2,834 total mistakenly added overlapping packets). Every packet's 16-byte IV field is `00 01 02 ... 0f`. The client-to-endpoint packets use varying IV values.

The public uNabto source's encryption routine calls `nabto_random(dst, 16)` to generate the IV. Its separate dummy random module emits the byte sequence `00, 01, 02, ...` and explicitly warns that it is an incomplete, cryptographically useless implementation. Nabto's TEN036 security guide states that AES-CBC IVs should be unique under a key and unguessable at encryption time.

This is a reproducible packet observation and a legitimate vendor question. It is not proof that the remote endpoint is the physical gateway, that the endpoint uses this exact public dummy module, or that the capture enables decryption or packet forgery. No attempt should be made to exploit, replay or modify the traffic. The correct action is to report the sanitized observation to Nabto/LS Control and ask them to identify the endpoint and confirm the firmware/client implementation.

Sources:
- https://github.com/nabto/unabto/blob/b8d4bdc417ef97c8d11ecb7fab2efde950dad2b9/src/unabto/unabto_crypto.c
- https://github.com/nabto/unabto/blob/b8d4bdc417ef97c8d11ecb7fab2efde950dad2b9/src/modules/random/dummy/unabto_random_dummy.c
- https://downloads.nabto.com/assets/docs/TEN036%20Security%20in%20Nabto%20Solutions.pdf (section 11.4)

## 5. Recommended vendor questions

Ask Nabto and LS Control/Genvex to answer these concrete questions:

1. Is Genvex Connect 4.0.3 based on the legacy Nabto 4/Micro Client SDK, and which client SDK version/build is embedded?
2. Is the Genvex Connect account still provisioned through a CA-signed Nabto client profile? If so, what is the supported third-party profile enrollment and renewal procedure?
3. Is a third-party Home Assistant client permitted to use the customer's existing device/account authorization?
4. Can Nabto supply a supported Linux aarch64 Nabto 4 Client SDK, headers, static resources and redistribution/licensing terms?
5. Can LS Control provide the Optima 270 `unabto_queries.xml` RPC interface definition and the supported device hostname mapping?
6. Can Nabto/LS Control identify the observed remote endpoint's role and confirm the repeated responder-side IV value against the actual deployed implementation?

## 6. Engineering decision

Do not implement the legacy wire protocol by hand and do not substitute Nabto Edge. The next implementation gate is:

- obtain written confirmation of the supported profile/identity workflow;
- obtain a supported Linux aarch64 Nabto 4 Client SDK or an approved alternative;
- obtain the Optima 270 RPC interface definition;
- then run a standalone, read-only diagnostic using the official client API.

Only after that succeeds should a remote transport adapter be added to Home Assistant. Existing local UDP support remains unchanged.

No integration code was changed during this research.
