# Genvex Connect remote login capture — 2026-11-19

Date: 2026-11-19  
Branch: `remote-nabto-connection`  
Sources supplied by the user:
- `genvex-login-full.pcap`
- `api.lscontrol.dk_11-19-2026-12-36-06.har`
- `api.lscontrol.dk_11-19-2026-12-36-34.har`

This note records passive observations from one Genvex Connect login attempt. It supplements, rather than replaces, the earlier local/remote Nabto and cloud API findings in this directory.

Sensitive values are intentionally omitted: the device ID, account email, certificate contents/fingerprints/serials, and the static-looking application/service field in the multipart body. Do not add them to public logs, source code, test fixtures, or issue reports.

## Executive summary

The combined HAR and packet capture show several distinct network paths during the login attempt:

1. Two HTTPS/TLS connections to `api.lscontrol.dk:4160`, with two multipart POST operations documented by the HAR files.
2. Two TLS connections to `lscontrol.nabto.com:443`.
3. Nabto-related UDP activity: local discovery on UDP 5570, STUN exchanges on UDP 3478/3479, controller-service exchanges on UDP 5566, and a subsequent Micro DATA session with `80.208.69.3:30795`.
4. Two successful WebSocket upgrade handshakes: `/handshake` on `34.249.112.159:80` and `/gateway` on `3.255.115.248:80`.

The capture supports a multi-service login/connection architecture. It does **not** establish the application role of every service, prove that the WebSockets carry telemetry or control, or show that the LS Control API returns live device values.

## 1. Capture integrity and scope

The PCAP is a classic Ethernet pcap with microsecond timestamps.

- Frames/packets parsed: 395
- Capture duration: approximately 28.370 seconds
- Capture start: 2026-11-19 11:35:13.278800 UTC
- Capture end: 2026-11-19 11:35:41.648778 UTC
- iPhone address on the temporary hotspot: `10.42.0.35`

The capture contains Genvex-related traffic as well as other phone background traffic. Connections to Google DNS and a Microsoft/Hotmail host are visible but have not been tied to Genvex Connect and are excluded from the Genvex interpretation.

The two HAR files each contain one request to the LS Control API. Their timestamps are recorded below. Exact one-to-one correlation of each HAR entry to a particular encrypted TLS application-data record in the PCAP is not asserted: the PCAP and HAR timestamps do not align cleanly for both requests. The HAR request/response content itself is clear.

## 2. LS Control cloud API: two observed POST operations

Both HAR entries document:

- Method: `POST`
- URL: `https://api.lscontrol.dk:4160/`
- Destination IP in the PCAP: `77.247.79.106`
- Transport: TLS 1.3
- Request content type: multipart/form-data
- Origin: `capacitor://localhost`
- HTTP status: `200`
- Response body: `{"Status":"1"}`

The two PCAP TCP flows to `77.247.79.106:4160` both have TLS ClientHello SNI `api.lscontrol.dk`.

### Sanitized request comparison

| Field | HAR 1 | HAR 2 | Interpretation |
|---|---|---|---|
| `man#1` | `KVM-Genvex` | `KVM-Genvex` | Product/manufacturer marker; exact semantics unknown |
| `pwm#2` | Redacted | Redacted | Static-looking app/service value; do not publish or replay |
| `com#3` | `7` | `8` | Operation selector is plausible, but unconfirmed |
| `devid#4` | Redacted | Redacted | Device identifier |
| `usno#5` | Empty | `1` | User-related field; exact semantics unknown |
| `us#6` | Empty | Empty | Empty in both requests |
| `pwu#7` | Empty | Empty | Empty in both requests |

HAR timing:

| Request | HAR start (UTC) | Duration | HTTP result |
|---|---|---:|---|
| 1 | 11:35:14.271 | 7.255 s | 200, `{"Status":"1"}` |
| 2 | 11:35:21.560 | 0.993 s | 200, `{"Status":"1"}` |

The HAR encodes the response body as base64; decoding it yields the JSON shown above. The response content type is labelled `text/html; charset=utf-8` despite the JSON body.

### What this establishes

- The app makes at least two distinct multipart POST operations to the LS Control API during this login attempt.
- The `com#3` and `usno#5` fields differ between the requests.
- Both responses are small and identical.
- Neither HAR request contains a visible account email, account password, bearer token, or session cookie. The `us#6` and `pwu#7` fields are empty.

### What remains unknown

- The meanings of operation values 7 and 8.
- The meaning of `usno#5=1`.
- Whether `Status: 1` represents application-level success, acknowledgement, or another status.
- Whether these calls register the device, retrieve configuration, authorize another service, or perform some other initialization.
- Whether the API is necessary for every subsequent Nabto session.

Do not replay the requests, vary operation numbers, or treat the redacted static-looking field as an authentication credential.

## 3. TLS connections to Nabto infrastructure

The PCAP contains two separate TLS connections from the iPhone to:

- Host/SNI: `lscontrol.nabto.com`
- Destination IP: `52.29.115.156`
- TCP port: `443`

This is direct packet-level evidence that the app contacts a Nabto-branded LS Control host during the same login attempt.

The PCAP also shows a TCP connection attempt to `52.29.115.156:5571` that is reset by the server before any application payload is exchanged. Its purpose is unknown.

The existence of TLS traffic to `lscontrol.nabto.com` does not by itself reveal the API, authentication method, or data exchanged because the payload is encrypted.

## 4. Local discovery, STUN and UDP 5566

### Local discovery

The phone sends UDP broadcasts to `255.255.255.255:5570`. Early packets are 14-byte discovery messages; later 45-byte messages contain the device hostname/identifier. The identifier is redacted here.

This is local discovery traffic and should not be confused with the remote data path.

### STUN

The phone exchanges STUN-shaped UDP packets on ports 3478 and 3479 with several public endpoints, including:

- `99.80.12.126`
- `52.88.74.226`
- `18.136.59.44`
- `52.17.80.64`

The observed request/response sizes and STUN message headers are consistent with NAT-discovery activity. The exact role of each server in this particular LS Control deployment is not established by this capture alone.

### UDP 5566

The capture contains a larger UDP exchange involving:

- `34.249.112.159:5566`
- `52.48.135.33:5566`

Observed payload sizes include 794-byte client messages, 805-byte server responses, and later messages of 308, 302 and 164 bytes.

This is consistent with the Nabto Controller-service activity seen in earlier captures and with the legacy Nabto connection architecture. The packet exchange should be described as controller-related/Nabto-associated traffic; its full message semantics have not been decoded here.

Earlier analysis of a separate login capture extracted a Nabto-issued client certificate whose Subject contained the user's account email. The exact email and all certificate material remain intentionally redacted. Two different client certificates with the same email Subject were observed across the earlier captures; this does not prove that a new certificate was issued during the login event.

## 5. Remote UDP session: Nabto Micro DATA

The PCAP shows a bidirectional UDP session between:

- Phone: `10.42.0.35:55665`
- Public endpoint: `80.208.69.3:30795`

The session begins with short packets of 26, 36 and 44 bytes, followed by recurring exchanges with payload sizes including 70, 24, 102, 310, 166, 134 and 118 bytes.

The 70-byte packet has the Nabto Micro DATA packet structure documented in `observed-lscontrol-cloud-api.md` and `remote-nabto-investigation.md`:

- DATA packet type
- Protocol version 2
- CRYPTO payload type
- Crypto suite `0x230A`

The suite is identified in the public uNabto definitions as AES-CBC with HMAC-SHA256. The application payload is encrypted and is not decoded by this capture.

The 24-byte server packets include a NOTIFY payload with notification code 3, `NOTIFY_MICRO_ACK`. The uNabto source describes this as meaning that the Micro side has received the request but the answer is not ready yet.

The endpoint `80.208.69.3` must remain role-unassigned. This capture does not prove whether it is the gateway, a direct peer, a relay, or another Nabto infrastructure endpoint.

The UDP port is `30795` in this session. Earlier captures used other ports, so the remote port is dynamic/session-specific and must not be hard-coded.

## 6. Two WebSocket handshakes

The PCAP contains two readable HTTP Upgrade handshakes over TCP port 80. Both servers return `101 Switching Protocols`.

### A. Device-specific `/handshake`

Client request:

```http
GET /handshake HTTP/1.1
Host: <device-id>.remote.lscontrol.dk
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
```

- Destination: `34.249.112.159:80`
- Server response: `HTTP/1.1 101 Switching Protocols`
- Server software header: `Boost.Beast/360`
- The client closes this TCP connection shortly after the successful upgrade.
- No WebSocket application frame is observed before closure.

### B. `/gateway`

Client request:

```http
GET /gateway HTTP/1.1
Host: ec2-3-255-115-248.eu-west-1.compute.amazonaws.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Version: 13
```

- Destination: `3.255.115.248:80`
- Server response: `HTTP/1.1 101 Switching Protocols`
- Server software header: `Boost.Beast/360`
- The TCP connection remains open through the end of the capture.
- No WebSocket application payload is visible during the captured interval.

These are confirmed WebSocket handshakes. Their application roles are **not** confirmed. In particular, there is no evidence in this capture that either WebSocket carries telemetry or fan-control commands. The `/gateway` path is a useful follow-up investigation target, not a proven control channel.

A separate TCP attempt to `3.255.115.248:5568` receives a SYN/ACK and is then reset by the client without application payload. Its purpose is unknown.

## 7. Updated connection model

The evidence supports the following inventory, not a fully proven causal sequence:

| Component | Observed path | Evidence | Role status |
|---|---|---|---|
| LS Control API | TLS to `api.lscontrol.dk:4160` | Two HAR POSTs and two TLS flows | API operations observed; semantics unknown |
| LS Control/Nabto host | TLS to `lscontrol.nabto.com:443` | Two TLS flows with matching SNI | Contact confirmed; payload encrypted |
| Local discovery | UDP 5570 broadcast | Readable packets | Discovery traffic |
| STUN | UDP 3478/3479 | STUN-shaped request/responses | NAT discovery strongly indicated |
| Controller exchange | UDP 5566 | Large bidirectional messages | Nabto-associated; details incomplete |
| Device-specific WebSocket | TCP 80 `/handshake` | HTTP 101 | Handshake confirmed; purpose unknown |
| Gateway WebSocket | TCP 80 `/gateway` | HTTP 101, connection remains open | Handshake confirmed; purpose unknown |
| Remote UDP session | UDP to `80.208.69.3:30795` | Nabto DATA/CRYPTO and Micro ACK structure | Nabto Micro data path confirmed; peer role unknown |

An earlier conversational summary described a strictly sequential chain in which the API completes before all Nabto activity starts. That is too strong. The PCAP shows overlapping connection activity, and the HAR timestamps do not establish a clean causal ordering for every request. It is safer to say that these services are all involved in the same login/connection attempt, while their exact dependencies remain unknown.

## 8. Implications for the Home Assistant implementation

The findings do not support replacing the remote transport with a simple REST client to `api.lscontrol.dk`:

- The two visible API responses contain only `{"Status":"1"}`.
- No telemetry values or control results are present in the HAR responses.
- The PCAP independently shows an encrypted Nabto Micro UDP session.
- The app also contacts Nabto infrastructure and establishes WebSocket handshakes.

The likely implementation boundary remains a separate remote transport/client layer that can establish an authorized Nabto Micro session and invoke the appropriate device interface, while reusing the existing Optima 270 model mapping and Home Assistant entity layer. This remains conditional on a supported client identity/profile flow and the required RPC definitions.

Do not alter the existing local UDP implementation. Do not assume the local Micro packet builder can be pointed at the public endpoint: the remote capture uses crypto suite `0x230A`, unlike the local null-data path documented in the existing research.

## 9. Recommended next investigation

No additional login capture is needed solely to reconfirm these handshakes. The most useful next work is:

1. Keep the raw captures private and preserve the sanitized observations in this document.
2. Continue source-level examination of the official Nabto 4 client and LS Control app architecture.
3. Determine whether the `/gateway` WebSocket exchanges any application frames during an already-authorized read-only session or control action; do not assume it is the command channel.
4. Obtain the supported LS Control/Nabto client identity/profile and RPC interface requirements rather than guessing credentials or endpoints.
5. Keep any eventual remote transport isolated from the working local UDP transport and reuse the existing model/entity layer only after the remote RPC data semantics are verified.

No credentials were replayed, no undocumented endpoint was probed, and no control request was generated as part of this passive capture analysis.
