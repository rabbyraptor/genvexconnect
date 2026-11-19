# Observed Genvex Connect cloud traffic: first LS Control API calls

Date observed: 2026-11-18/19
Source: two user-supplied Proxyman log captures from Genvex Connect on iPhone.

## Confirmed request destination

Both captures contain an HTTPS request with:

- Host: `api.lscontrol.dk`
- Destination IP observed: `77.247.79.106`
- TCP port: `4160`
- Method: `POST`
- Path: `/`
- Content type: `multipart/form-data`
- HTTP version: `1.1`
- Origin: `capacitor://localhost`
- User-Agent identifies an iPhone WebKit/Cordova-style webview.

This is the first directly observed LS Control cloud HTTP endpoint in this investigation. It is distinct from the Nabto RPC URI scheme and from the local UDP/5570 protocol.

## Request body structure

Both requests contain the same seven multipart field names:

| Field | First capture | Second capture | Notes |
|---|---|---|---|
| `man#1` | `KVM-Genvex` | `KVM-Genvex` | Manufacturer/product marker, exact semantics not confirmed |
| `pwm#2` | Redacted | Redacted | Contains a repeated static-looking application/service value; do not publish or replay |
| `com#3` | `7` | `8` | Changes between requests; command/operation code is plausible but unconfirmed |
| `devid#4` | Redacted device ID | Same ID | Device identifier; keep private |
| `usno#5` | Empty | `1` | Changes between requests |
| `us#6` | Empty | Empty | Empty in both captures |
| `pwu#7` | Empty | Empty | Empty in both captures |

The static-looking value in `pwm#2` and the device ID have intentionally been redacted. Do not include them in public issues, logs, code, or test requests. Do not replay these requests or attempt to use the static value as an authentication credential.

## Responses

Both requests receive:

- HTTP status: `200 OK`
- Response content type: `text/html; charset=utf-8`
- Body: `{"Status":"1"}`

The meaning of `Status: 1` is not yet known. HTTP 200 confirms a normal HTTP response, not necessarily successful authentication or a successful device operation.

## Timing and differences

The two requests occur close together (approximately 2.4 seconds between their request start times in the capture metadata). The `com#3` field changes from `7` to `8`, and `usno#5` changes from empty to `1`. All other visible structural fields remain the same.

This suggests the app is making at least two distinct operations against the same service endpoint during the login/initialization flow. It is not yet possible to assign names or semantics to operation codes 7 and 8.

## What this establishes

1. Genvex Connect communicates with an LS Control HTTPS service at `api.lscontrol.dk:4160`.
2. The observed interface is a multipart POST to the root path, not a conventional REST path such as `/api/login`.
3. The request includes a manufacturer marker, an application/service value, a device ID, a numeric operation field, and user-related fields.
4. The server returns a small JSON object even though its response content type is labelled `text/html`.

## What it does not establish

- That these calls authenticate the user's account.
- That `com#3` is a command ID, though that is a reasonable hypothesis.
- That `pwm#2` is a password or can be used as one.
- That `Status: 1` means success.
- Any endpoint or operation for reading telemetry, setting parameters, listing devices, or retrieving history.
- Whether subsequent device communication uses this same HTTPS service, Nabto RPC, or another channel.

## Next safe observation

Capture a fresh Proxyman session with the following passive sequence, without changing any ventilation settings:

1. Start capture before opening Genvex Connect.
2. Open the app and wait for its initial screen.
3. Open the already-registered ventilation unit and wait for all values to finish loading.
4. Open each read-only status/measurement screen and wait briefly.
5. Open alarms or error history if available, without resetting anything.
6. Stop capture and export the additional requests.

For every request, preserve method, host, port, path, content type, field names, non-sensitive numeric operation values, response status and response shape. Redact device identifiers, account details, tokens, passwords, and static application/service values before sharing.

Do not replay requests, modify operation codes, probe undocumented paths, or attempt writes. The immediate goal is to map normal app behaviour and identify which read operations fetch live device data.

## Public-source cross-check

The Google Play listing identifies Genvex Connect as an LS Control A/S app and describes remote control, sensor/status reading, error messages and set-point controls. This corroborates the app/vendor relationship, but it does not document the observed host, port, or protocol.

Source: https://play.google.com/store/apps/details?id=dk.lscontrol.genvexapp


## Additional observation: UDP traffic correlated with fan-speed changes

Date observed: 2026-11-19
Source: user-supplied tcpdump capture from an iPhone connected through a SteamOS-hosted Wi-Fi hotspot. The capture was stopped cleanly with Ctrl+C.

Capture summary:
- 231 packets captured.
- 235 packets received by filter.
- 0 packets dropped by kernel.
- Phone-side address in the temporary capture network: `10.42.0.35`.
- Repeated UDP exchange with `80.208.69.3:30815`.
- The remote endpoint's ownership and service identity have not been independently verified.

The user performed three fan-speed changes and pressed Enter immediately after each change. The marker timestamps were:
- `00:47:02.673358870`
- `00:47:04.340171727`
- `00:47:07.070587157`

At each marker, a 70-byte UDP packet from the phone to `80.208.69.3:30815` appeared immediately beforehand, followed by a 24-byte response and a 70-byte packet from the server:

| User marker | Phone → endpoint | Endpoint → phone | Endpoint → phone |
|---|---|---|---|
| 00:47:02.673 | 00:47:02.607, 70 bytes | 00:47:02.618, 24 bytes | 00:47:02.644, 70 bytes |
| 00:47:04.340 | 00:47:04.220, 70 bytes | 00:47:04.231, 24 bytes | 00:47:04.255, 70 bytes |
| 00:47:07.071 | 00:47:07.110, 70 bytes | 00:47:07.121, 24 bytes | 00:47:07.146, 70 bytes |

The marker timestamps are close to the packet exchanges, and the same request/response size pattern occurred three times during the three user actions. This is a useful correlation, but packet lengths and timing alone do not establish payload semantics or prove that the 70-byte request is the actual fan-speed command.

A similar 70-byte exchange was observed in earlier captures outside a clearly isolated action window. Therefore, it must not be described as uniquely generated by a fan-speed change. The current evidence supports the narrower statement that this exchange was observed in close temporal association with all three marked changes.

### Current interpretation

- The app maintains a recurring UDP exchange with `80.208.69.3:30815`.
- The same packet-size sequence was observed around all three marked fan-speed changes.
- The endpoint may be part of the remote device communication path, but its identity and role remain unverified.
- This capture does not decode the protocol, identify the command value, or establish whether the exchange is a command, acknowledgement, polling operation, or status update.
- The earlier UDP traffic to port 5566 and STUN-like traffic on port 3478 remain suggestive of a Nabto-related transport, not proof of it.

No further packet-capture repetition is planned at this stage. The investigation should move to source-level/vendor documentation and supported SDK/API access rather than continuing timing experiments.


## Protocol identification from the 2026-11-19 PCAP hex dump

A byte-level comparison of the three 70-byte UDP datagrams to `80.208.69.3:30815` against the public Nabto uNabto protocol definitions and the existing `superrob/genvexnabto` implementation identifies them as Nabto Micro DATA packets.

This is substantially stronger than the earlier timing/packet-size correlation.

### Parsed client-to-server packet

The UDP payload is 70 bytes and parses as:

| Offset | Bytes | Interpretation |
|---:|---|---|
| 0–3 | `31 c7 0d d4` | Client peer ID (NSI.cp) |
| 4–7 | `c3 e1 e7 96` | Server peer ID (NSI.sp) |
| 8 | `16` | Packet type DATA (decimal 22) |
| 9 | `02` | Nabto protocol version 2 |
| 10 | `00` | Retransmission/reserved field |
| 11 | `00` | Packet flags |
| 12–13 | `00 a8`, `00 ad`, `00 b4` | Sequence numbers in the three observed packets |
| 14–15 | `00 46` | Total packet length: 70 bytes |
| 16–19 | `36 00 00 36` | CRYPTO payload header; type 0x36, flags 0, payload length 0x0036 (54 bytes) |
| 20–21 | `23 0a` | Crypto suite code 0x230A |
| 22–69 | 48 bytes | Encrypted/authenticated crypto data |

The apparent two-byte prefix before DATA in the original terminal rendering was a parsing-offset mistake: the UDP checksum was included in the Ethernet hex line. The UDP payload itself starts at byte `31 c7`, and its packet header aligns exactly with the uNabto 16-byte fixed header.

### Crypto suite identification

The public uNabto definitions compose the crypto code from:
- `CRYPT` operation: `0x0002`
- `SECR` encryption mode: `0x0008`
- AES-CBC: `0x2000`
- HMAC-SHA256: `0x0300`

Combined: `0x230A`.

This is the uNabto `CRYPT_W_AES_CBC_HMAC_SHA256` suite. The 48-byte crypto-data region is consistent with the documented layout of a 16-byte IV, one 16-byte AES-CBC ciphertext block (including padding of the short plaintext), and a 16-byte truncated HMAC. The encrypted application command itself is not visible in the capture.

### Server response packets

The 70-byte server datagrams have the same DATA/CRYPTO structure and sequence number as the corresponding client packet, with the response flag set (`flags=0x01`). Their crypto suite code is also `0x230A`.

The intervening 24-byte server datagrams have not yet been decoded. In uNabto, an asynchronous request can produce a notification ACK using the `NOTIFY_MICRO_ACK` notification code. The 24-byte packet length is consistent with such a packet, but the exact notification type/code must be checked against its bytes before labelling it an ACK.

### Conclusion and confidence

- **Confirmed:** The 70-byte datagrams are structured as Nabto uNabto DATA packets, version 2, carrying a CRYPTO payload.
- **Confirmed:** The crypto suite code is `0x230A`, which the public uNabto source defines as AES-CBC with HMAC-SHA256.
- **Confirmed:** The three client packets carry sequence numbers `0x00A8`, `0x00AD`, and `0x00B4`; the server responses mirror those sequence numbers and set the response flag.
- **Strongly established:** The app's remote UDP exchange uses the Nabto Micro/uNabto packet format. This is no longer merely inferred from port numbers.
- **Not established:** The identity/role of `80.208.69.3` (device, relay, or other Nabto infrastructure), the plaintext command, or whether each correlated packet is itself the fan-speed write rather than part of its request/response flow.
- **Next useful analysis:** Decode the already-captured 24-byte server datagrams to test whether they are the uNabto asynchronous Micro ACK. No new capture is required.

Relevant public source:
- Nabto uNabto packet layout and crypto definitions: https://github.com/nabto/unabto/blob/master/src/unabto/unabto_protocol_defines.h
- Nabto uNabto packet header parsing: https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet_util.c
- Nabto Micro ACK generation: https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet.c
- Existing Genvex packet builder: https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/packet.py
- Existing Genvex UDP message parser: https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/genvexnabto.py


## Decode of the 24-byte server notifications (2026-11-19)

The user supplied a tcpdump hex dump filtered to UDP payload length 32 bytes at the IP layer (24-byte UDP payload). These packets are now decoded conclusively as Nabto Micro ACK notifications.

Example UDP payload, beginning at the first byte after the UDP header:

```
31 c7 0d d4  c3 e1 e7 96  16 02 00 01  00 a8 00 18
34 00 00 08  00 00 00 03
```

| Offset | Bytes | Interpretation |
|---:|---|---|
| 0–3 | `31 c7 0d d4` | Client peer ID |
| 4–7 | `c3 e1 e7 96` | Server peer ID |
| 8 | `16` | DATA packet |
| 9 | `02` | Protocol version 2 |
| 10 | `00` | Reserved/retransmission field |
| 11 | `01` | Response flag |
| 12–13 | `00 a8` | Sequence number |
| 14–15 | `00 18` | Packet length: 24 bytes |
| 16–19 | `34 00 00 08` | NOTIFY payload, flags 0, length 8 |
| 20–23 | `00 00 00 03` | Notification code 3 |

The public Nabto uNabto source defines payload type `0x34` as `NP_PAYLOAD_TYPE_NOTIFY`. Its notification enum begins at `NOTIFY_ATTACH_OK = 1`, followed by `NOTIFY_ATTACH_CLOSE = 2`, then `NOTIFY_MICRO_ACK = 3`. The source comment for `NOTIFY_MICRO_ACK` explicitly says: “The Micro has received the request, but the answer isn't ready yet.”

The packet is therefore definitively a `NOTIFY_MICRO_ACK`, not merely a packet that happens to be 24 bytes long.

### Correlation with the three observed 70-byte DATA requests

The supplied capture includes notifications whose sequence numbers match the three 70-byte client DATA packets identified in the previous analysis:

- `0x00A8` — notification at 00:47:02.618405
- `0x00AD` — notification at 00:47:04.230543
- `0x00B4` — notification at 00:47:07.120947

This matching sequence number is consistent with Nabto acknowledging those requests while their answers are not yet ready. The capture excerpt shows repeated notifications at roughly one-second intervals for many sequence numbers; this is part of the observed asynchronous exchange and should not be mistaken for a new fan-speed command each time.

### Updated conclusion

- **Confirmed:** The 24-byte server packets are Nabto DATA response packets containing a NOTIFY payload with notification code 3, i.e. `NOTIFY_MICRO_ACK`.
- **Confirmed:** The notification means the Micro side has received the request but the answer is not ready yet.
- **Confirmed:** At least three notification sequence numbers (`0x00A8`, `0x00AD`, `0x00B4`) match the sequence numbers of the three 70-byte client DATA packets from the earlier analysis.
- **Not established:** Whether the corresponding request is specifically the fan-speed write, another app operation, or a periodic/background request. Sequence matching proves protocol-level correlation, not application-level meaning.

Source:
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_protocol_defines.h
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet_util.h
- https://github.com/nabto/unabto/blob/master/src/unabto/unabto_packet.c


## Official Nabto/LS Control architecture and supported-client investigation (2026-11-19)

A review of Nabto's official LS Control partner page provides an important architectural confirmation and changes the recommended next step.

### What Nabto publicly confirms about LS Control

Nabto describes the LS Control implementation as:

- Embedded hardware based on PIC32 using the uNabto SDK for RPC and streaming.
- iOS and Android apps built with Ionic/Cordova using Nabto RPC for remote control.
- A .NET server application using the Nabto Client SDK .NET wrapper to access devices through Nabto RPC and Nabto Streaming.
- Nabto CA-based authentication integrated with a custom identity-management system.

Source: https://www.nabto.com/partners/ls-control/

This is direct vendor-published evidence that LS Control has used a **server-side Nabto client**, not only mobile clients. It also confirms the CA/custom-identity architecture at the LS Control product level. It does not establish that the public Genvex Connect login credentials can be used directly with the Nabto SDK, nor does it document a third-party API.

### Why this matters for a Home Assistant integration

The most promising supported route is now to investigate the same server-side client model LS Control publicly describes:

1. Obtain confirmation from Nabto/LS Control whether the legacy Nabto 4/Micro Client SDK and .NET wrapper can be licensed or supplied for third-party integration.
2. Confirm whether a supported Linux build exists and whether it runs on the target architecture(s) intended for the HAOS add-on (initially ARM64/Raspberry Pi if that remains the target).
3. Obtain the documented CA authentication and identity-management flow for an authorized Genvex Connect user/device.
4. Confirm whether the SDK may be redistributed inside a commercial, preconfigured Home Assistant appliance, and what licensing or per-device fees apply.
5. If the SDK is available, build a small isolated service/add-on that uses the supported SDK and exposes a narrow local API to Home Assistant. Keep Nabto session management and credentials out of YAML dashboards and ordinary entity attributes.

The official Nabto Edge Linux SDK documentation is **not** a drop-in replacement: Edge is the newer Nabto platform, while LS Control's published architecture and the captured traffic identify the deployed system as legacy uNabto/Nabto Micro. A client written for Edge cannot be assumed to connect to a Micro device.

Nabto explicitly labels its legacy Nabto 4/Micro material as a legacy platform superseded by Nabto 5/Edge and recommends Edge for new designs. That is a lifecycle and support risk for a commercial product, so written confirmation of availability, support and redistribution rights is essential before investing in a production implementation.

Relevant Nabto sources:
- LS Control architecture: https://www.nabto.com/partners/ls-control/
- Nabto Edge SDK platform list (documents current Edge SDKs, including Linux): https://www.nabto.com/docs/developer/platforms.html
- Nabto article explicitly identifying Nabto 4/Micro as legacy: https://www.nabto.com/cc3200-two-way-audio-with-android/
- Nabto legacy PPKA access-control overview: https://www.nabto.com/pairing-and-access-control-part-1-intro-and-device/
- Nabto legacy client-side authentication/pairing overview: https://www.nabto.com/pairing-and-access-control-client-implementation/

### Genvex Connect account onboarding: what the public guide says

Genvex's current Quick Guide says that:

- A 12-digit ID on the gateway label is used to add a gateway when the phone is not on the same local network.
- A user is created by entering an email address; a password is automatically generated and sent to that email address.
- The first user registered on a gateway becomes its owner; additional users use the owner's email address and password.

Source: https://www.genvex.com/download/18.2632f14918aa7daec381d84/1775546758460/Quickguide-Genvex-Connect.pdf

This describes the consumer account workflow, but it does **not** explain how that account maps to Nabto CA identities or how a third-party server client is authorized. Do not assume that the emailed Genvex password is a Nabto certificate password or a reusable SDK credential.

### Smart Connect Center as a separate supported route

Genvex's Smart Connect Center product page says that systems with Optima 270 can be connected when they have LAN connectivity. It advertises current and historical operating data, alarm/event logs, service history, notifications, and remote parameter adjustment. The service is presented as a professional/administrator product.

Source: https://www.genvex.com/en/products/genvex-accessories/smart-connect-center

This is especially relevant to the Optima 270 controller in the investigation. It may be a more supportable data-access route for a commercial integration, but no public third-party API or end-user API documentation has been identified. The next vendor question should be whether an authorized API, scheduled export, or data-sharing interface exists, and whether access requires a Smart Connect Center subscription or installer/partner agreement.

### Questions to send to Nabto and LS Control/Genvex

**To Nabto:**
1. Is the legacy Nabto 4/Micro Client SDK (Plain C and/or .NET wrapper) still available to existing deployments such as LS Control?
2. Is there a supported Linux client build, and which architectures/libc environments are supported (particularly ARM64)?
3. Can a third-party commercial appliance redistribute or bundle the client SDK? What licensing, support and runtime fees apply?
4. What is the supported integration process for a third-party server client connecting to an LS Control device using the LS Control CA/custom identity-management setup?

**To LS Control/Genvex:**
1. Is there a documented or partner-accessible API/SDK for Genvex Connect or the LS Control Nabto service?
2. Can an end user explicitly authorize a third-party Home Assistant client to access their own gateway, without sharing the owner's account password?
3. Is there a supported server-side integration path corresponding to the .NET Nabto Client SDK application described by Nabto?
4. For Optima 270, can Smart Connect Center data be accessed through an API, export, or data-sharing agreement?
5. What are the commercial, licensing, security-review and support conditions for embedding such access in a preconfigured Home Assistant appliance?

### Evidence boundary

Confirmed by public vendor sources:
- LS Control's historical architecture includes a server-side .NET Nabto Client SDK wrapper.
- LS Control uses Nabto CA authentication integrated with custom identity management.
- Genvex Connect's documented user onboarding is based on an owner email/password workflow.
- Genvex advertises Smart Connect Center support for Optima 270 systems.

Not yet confirmed:
- Availability of the legacy SDK/wrapper to third parties.
- Linux ARM64 compatibility of the legacy client.
- Redistribution rights or commercial licensing.
- The exact mapping between Genvex Connect accounts and Nabto CA identities.
- Any supported third-party API or Smart Connect Center API.
- Whether the Genvex gateway in this investigation is registered for Smart Connect Center.

### Recommended decision

Do not start implementing a custom Nabto Micro client or reverse-engineered cloud login yet. First request written answers from Nabto and LS Control/Genvex on SDK availability, CA identity authorization, ARM64 support, redistribution and commercial terms. In parallel, ask about Smart Connect Center data access for Optima 270. Those answers determine whether the production architecture should be a supported Nabto client sidecar, an official cloud/data integration, or a local-only fallback.


## Full login capture cross-reference (2026-11-19)

A later user-supplied login session was captured simultaneously as two Proxyman HAR entries and a full packet capture. The two HAR entries again show POST operations to `https://api.lscontrol.dk:4160/`:

- `com#3=7`, `usno#5` empty; HTTP 200, body `{"Status":"1"}`.
- `com#3=8`, `usno#5=1`; HTTP 200, body `{"Status":"1"}`.

Both requests also contain the same manufacturer marker, a redacted static-looking application/service field, a redacted device ID, and empty `us#6` and `pwu#7` fields. No account email, account password, bearer token or session cookie is visible in these HAR requests. The exact semantics of the operation and user-number fields remain unknown. The response status string must not be treated as proof of authentication or device-operation success.

The corresponding full PCAP contains two TLS 1.3 connections to `api.lscontrol.dk:4160`, two TLS connections to `lscontrol.nabto.com:443`, UDP 5570 discovery, STUN activity on UDP 3478/3479, controller-associated UDP 5566 traffic, a Nabto Micro DATA/CRYPTO session to `80.208.69.3:30795`, and successful WebSocket upgrades to `/handshake` and `/gateway`. The WebSocket application roles remain unknown; no WebSocket application frames are visible in this capture.

See [remote-login-flow-capture-2026-11-19.md](remote-login-flow-capture-2026-11-19.md) for the detailed sanitized packet and HAR analysis, including timing caveats and the distinction between confirmed protocol structure and unverified service roles.


## Marked fan-speed-change PCAP (2026-11-19)

A separate user-supplied PCAP and marker file were analyzed. The marker records `2026-11-19 15:00:22.145117760 FAN_SPEED_CHANGE` in the user's local time (UTC+01:00), equivalent to 14:00:22.145118 UTC.

A remote Nabto Micro UDP session to `80.208.69.3:30721` was active across the marker. A 70-byte client DATA request occurred 1.619 seconds after the marker and received a 24-byte `NOTIFY_MICRO_ACK`, followed by a 70-byte DATA response. However, the same 70-byte request/response pattern occurred again 13.574 seconds later, with an identical server response payload. It is therefore not proven to be the fan-speed write; it may be a periodic query or another repeated operation.

The ongoing 310-/134-byte DATA exchanges continued before and after the marker. There was a 2.046-second interval between two client packets around the marker, but this single timing difference is not enough to identify a command.

Detailed packet timestamps, sequence numbers, counts and limitations are documented in [fan-speed-change-capture-2026-11-19.md](fan-speed-change-capture-2026-11-19.md).
