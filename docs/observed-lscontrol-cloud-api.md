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
