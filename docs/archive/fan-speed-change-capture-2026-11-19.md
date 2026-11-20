# Genvex fan-speed-change capture — 2026-11-19

Date: 2026-11-19  
Branch: `remote-nabto-connection`  
User-supplied files:
- `genvex-fan-change.pcap`
- `genvex-fan-change.txt`

The text file contains one user action marker:

```
2026-11-19 15:00:22.145117760 FAN_SPEED_CHANGE
```

The PCAP timestamps are Unix epoch timestamps. Interpreting the marker in the user's local Europe/Copenhagen time zone (UTC+01:00 on this date) places it at **14:00:22.145117760 UTC**.

This is a passive capture analysis. Device identifiers, peer IDs, account details, and cryptographic payloads are not reproduced here.

## Executive summary

A remote UDP session between the phone (`10.42.0.35:53925`) and `80.208.69.3:30721` was active across the marked fan-speed change.

The exchange is confirmed to use the same Nabto Micro DATA/CRYPTO framing and crypto suite `0x230A` documented in earlier captures. The 24-byte server notifications are `NOTIFY_MICRO_ACK` packets (notification code 3).

A discrete 70-byte client DATA request occurred **1.619 seconds after** the marked user action. It received:
- a 24-byte `NOTIFY_MICRO_ACK` 12.562 ms after the request; and
- a 70-byte DATA response 37.109 ms after the request.

This is a useful temporal correlation, but it does **not** prove that this particular 70-byte request is the fan-speed write. The same 70-byte request/response pattern occurs again 13.574 seconds later, with an identical server response payload. That repetition is compatible with a recurring query/keepalive or another repeated operation. The encrypted application payload cannot be identified from this capture.

The capture therefore confirms that the fan-speed action happened during an active remote Nabto Micro session and was followed shortly by a complete short DATA request/response exchange. It does not yet identify the command packet or decode the requested fan stage.

## 1. Capture overview

The PCAP contains 36,438 parsed IPv4 TCP/UDP packets and spans approximately 8 minutes 3.95 seconds. Most of the traffic is unrelated phone/background traffic.

The relevant Nabto UDP flow contains **353 datagrams** and is active from:
- First packet: 14:00:15.136938 UTC
- Last packet: 14:01:16.812005 UTC

The remote session therefore begins about 7.008 seconds before the marker and continues for about 54.666 seconds after it.

The phone-side address is `10.42.0.35`. The remote endpoint is `80.208.69.3:30721`. The endpoint's ownership/role remains unverified; do not label it as the gateway, a relay, or another specific Nabto service based on this capture alone.

## 2. Protocol confirmation

The 70-byte client packets have the same Nabto Micro structure seen in earlier captures:

- DATA packet type
- Protocol version 2
- CRYPTO payload
- Crypto suite `0x230A` (AES-CBC with HMAC-SHA256)

The server's 24-byte packets contain a NOTIFY payload with notification code 3, `NOTIFY_MICRO_ACK`. This means the Micro side has received the request but the answer is not ready yet.

This is consistent with the protocol analysis already recorded in:
- `observed-lscontrol-cloud-api.md`
- `remote-nabto-investigation.md`

## 3. Packets around the user action

Marker: **14:00:22.145118 UTC**

| UTC timestamp | Offset from marker | Direction | UDP payload | Sequence | Observation |
|---|---:|---|---:|---:|---|
| 14:00:20.784270 | -1.361 s | Phone → endpoint | 310 bytes | `0x0010` | Regular DATA exchange |
| 14:00:20.808622 | -1.336 s | Phone → endpoint | 134 bytes | `0x0011` | Regular DATA exchange |
| 14:00:22.145118 | 0 | — | — | — | User marker: FAN_SPEED_CHANGE |
| 14:00:22.854264 | +0.709 s | Phone → endpoint | 310 bytes | `0x0012` | DATA request |
| 14:00:22.870700 | +0.726 s | Endpoint → phone | 24 bytes | `0x0012` | `NOTIFY_MICRO_ACK` |
| 14:00:22.874068 | +0.729 s | Endpoint → phone | 166 bytes | `0x0012` | DATA response |
| 14:00:22.879201 | +0.734 s | Phone → endpoint | 134 bytes | `0x0013` | DATA request |
| 14:00:22.892364 | +0.747 s | Endpoint → phone | 24 bytes | `0x0013` | `NOTIFY_MICRO_ACK` |
| 14:00:22.894587 | +0.750 s | Endpoint → phone | 118 bytes | `0x0013` | DATA response |
| 14:00:23.764270 | +1.619 s | Phone → endpoint | 70 bytes | `0x0014` | Short DATA request |
| 14:00:23.776832 | +1.632 s | Endpoint → phone | 24 bytes | `0x0014` | `NOTIFY_MICRO_ACK` |
| 14:00:23.801379 | +1.656 s | Endpoint → phone | 70 bytes | `0x0014` | DATA response |

The regular 310-/134-byte exchange normally advances at approximately one-second intervals. There is a 2.046-second interval between the 134-byte client packet at 14:00:20.808622 and the next 310-byte client packet at 14:00:22.854264. The user marker falls inside this interval. This timing difference is worth retaining, but one occurrence is not enough to assign meaning to the pause.

## 4. Repeated 70-byte exchange

The capture contains three 70-byte client DATA packets in this session:

| Client request (UTC) | Sequence | Server ACK | Server DATA response |
|---|---|---|---|
| 14:00:15.165507 | `0x0003` | 14:00:15.177113 | 102 bytes at 14:00:15.178798 |
| 14:00:23.764270 | `0x0014` | 14:00:23.776832 | 70 bytes at 14:00:23.801379 |
| 14:00:37.338274 | `0x002F` | 14:00:37.348760 | 70 bytes at 14:00:37.373662 |

The second and third server responses have the same 70-byte payload after the sequence/header fields; the client request ciphertext differs. The two requests are 13.574 seconds apart.

The second request is 1.619 seconds after the fan-change marker. The third request occurs 15.193 seconds after the marker.

This repetition means the 70-byte transaction cannot be confidently called the fan-speed command based only on its proximity to the marker. It may be a periodic operation, a repeated read, a keepalive, or another application-level request. Its exact meaning is unknown.

## 5. Background exchange pattern

Across the 61.675-second remote session, the phone sends:
- 57 packets of 310 bytes;
- 57 packets of 134 bytes;
- 3 packets of 70 bytes;
- one 44-byte packet; and
- one 26-byte packet.

The endpoint sends:
- 117 packets of 24 bytes (`NOTIFY_MICRO_ACK`);
- 57 packets of 166 bytes;
- 56 packets of 118 bytes;
- two packets of 70 bytes; and
- one 36-byte packet and one 102-byte packet.

The 310-/134-byte request pattern and 166-/118-byte responses continue before and after the user marker. These repeated transactions appear to be the session's ongoing background/application traffic. Their encrypted payloads are not decoded.

## 6. What this capture establishes

**Confirmed:**
- A Nabto Micro remote UDP session was active during the fan-speed change.
- The remote session used the same `0x230A` DATA/CRYPTO framing as earlier captures.
- The 24-byte responses are `NOTIFY_MICRO_ACK` notifications.
- A 70-byte client request occurred 1.619 seconds after the marked fan-speed change and received a 70-byte DATA response.
- The same 70-byte request/response size pattern recurred 13.574 seconds later, with an identical server response payload.
- The remote UDP port in this session was `30721`, different from previous sessions. It is session-specific and must not be hard-coded.

**Not established:**
- Which encrypted request carries the fan-speed write.
- Whether the 70-byte request is a control command, read request, periodic query, or keepalive.
- The requested fan stage or any plaintext RPC/query value.
- Whether `80.208.69.3` is the gateway, a peer, a relay, or another Nabto endpoint.

## 7. Updated interpretation and next step

This capture strengthens the evidence that fan-speed changes occur over the remote Nabto Micro data path. It does not yet isolate the actual application-level write.

The 70-byte transaction is a candidate for further comparison because it occurs shortly after the user marker and has a complete ACK/response sequence. However, its recurrence at a roughly 13.6-second interval makes it unsafe to label it as the fan-speed command without another discriminating observation.

The next useful comparison would be a capture with two or more clearly separated user markers for different fan-stage changes, ideally with a short quiet period between them. We should compare the encrypted packet sequence/timing around each marker against the same background traffic. Do not replay or modify captured encrypted packets.

No credentials were sent, no packet was replayed, and no undocumented endpoint was probed during this analysis.
