> **Archived evidence (21 November 2026).** This is a dated investigation or completed milestone, not the current operating instructions. See [current status](../STATUS.md).

# Reconstructing a read-only remote RPC query from the LAN implementation

Date: 2026-11-19  
**Status: authenticated read-only RPC 45 verified via Steam Deck x86_64 on 2026-11-19; source-derived schema works for one sensor. Numeric sensor-to-temperature interpretation still awaits independent comparison.**

## New observation: known remote query 17 matches the LAN opcode and encoding

The [public Genvex Nabto LAN implementation](https://github.com/superrob/genvexnabto) represents application query identifiers as four big-endian bytes:

- `GenvexCommandPing.buildCommand()` sends `00 00 00 11 70 69 6e 67`. `0x11` = **17** and the four request bytes are `0x70696e67` = `ping` = **1885957735**.
- Independently, Nabto's official [LS Control Cordova test app](https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js) defines `ping.json` with **query ID 17**, `uint32 ping`, same value. That RPC was authenticated and successfully run remotely on the project gateway using the Nabto 4 SDK, including under HAOS/QEMU.
- Nabto [TEN025](https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf), section 6.1, specifies that the XML `query id` is the numeric opcode transmitted to the device; query **name** is used by the client to identify the matching entry.

**Interpretation:** the known ping query is byte-for-byte consistent with the LAN command. This is unusually strong evidence that the two transports use the same application-level query numbering and uNabto serialization.

## Candidate additional command identifiers: grounded in source, not guesses

The public LAN code specifies:

| LAN application command | Hex | Decimal | Purpose | Project remote status |
| --- | ---: | ---: | --- | --- |
| `PING` | 0x11 | 17 | Identify device | **VERIFIED REMOTE** |
| `DATAPOINT_READLIST` | 0x2d | **45** | Read datapoints | **VERIFIED REMOTE for a single object/address** |
| `SETPOINT_READLIST` | 0x2a | **42** | Read setpoints | **UNVERIFIED REMOTE** |
| `SETPOINT_WRITELIST` | 0x2b | 43 | Write setpoints | **DO NOT TEST** |

Upstream: [`protocol/payload.py`](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/protocol/payload.py) and respective `cmd_*.py` source. **These are application command opcodes**, not local controller register addresses: an earlier warning about reusing register addresses still stands.

## Offline-reconstructed query 45 request

The LAN source builds a request with:

1. Four-byte opcode `00 00 00 2d`
2. Two-byte big-endian list count
3. For each entry: one-byte object ID and four-byte big-endian datapoint address
4. One trailing byte `01`, whose significance the source does not explain

For the Optima 270's *supply temperature* datapoint, `obj=0` and `address=20` according to [`models/optima270.py`](https://github.com/superrob/genvexnabto/blob/main/src/genvexnabto/models/optima270.py), with default object value confirmed in `models/basemodel.py`.

Expected serialized application request: **`00 00 00 2d 00 01 00 00 00 00 14 01`**.

Nabto's original [uNabto query C code](https://github.com/nabto/unabto/blob/master/src/unabto/unabto_query_rw.c) confirms list length is encoded as a big-endian uint16 preceding element bytes. The published TEN025 manual describes how to represent a list in XML and how clients invoke list RPCs through a URL's `json=` parameter.

## Prototype artifact

- [`tests/fixtures/candidate_readonly_query45.xml`](../../tests/fixtures/candidate_readonly_query45.xml) — *hypothetical* read-only schema, mapping query ID **45** to list fields `obj:uint8`, `address:uint32`, and an explicit `trailer:uint8=1`, with a candidate response list of signed 16-bit values.
- [`tests/test_reconstructed_readonly_rpc.py`](../../tests/test_reconstructed_readonly_rpc.py) — offline-only comparison against public LAN serialization.

The author ran **four equivalent offline structural tests**, passing for one, three, and zero datapoints and a schema assertion. The test reimplements the documented encoding and checks exact bytes; **the SDK now independently accepted the candidate XML and decoded a single remote response successfully**.

The candidate response schema `list(values: int16)` reflects the publicly documented local decoder's `uint16 count` followed by signed 16-bit values. The trailing `01` in the LAN request is not yet explained; modeling it as an extra `uint8` parameter is a **testable hypothesis**.

## Safe validation steps

1. First use the already provisioned Steam Deck client and **only the local Nabto SDK parser** (`nabtoRpcSetDefaultInterface`) to verify that the candidate schema is valid; no controller invocation required for this step.
2. If accepted, authorize/perform **one read-only query 45** for **one verified Optima 270 datapoint** (`obj=0, address=20`) through the existing authenticated remote connection. No batch, no guessed ID range, and no writes.
3. Classify SDK status and error event while suppressing credential, endpoint and raw JSON logging; if successful, decode a single raw int16 reading and apply the existing model's `(raw - 300)/10` temperature conversion.
4. Independently compare with the existing local integration when both are available, without changing the local integration.
5. Only after verification, extend schema to known, read-only datapoint addresses and later setpoint reads. Do **not** infer write safety or enable ID 43.

## Risk/constraints

Remote reachability of query 45 for one address, SDK XML acceptance, and one-element int16 response decoding are now **VERIFIED**. The exact semantic meaning of the response without a contemporaneous local comparison, general multi-value behavior, HAOS/QEMU operation of RPC 45, and SDK licensing/distribution remain **OPEN**. A valid local schema and working ping do not prove a new query is present remotely. Keep the existing HAOS integration untouched.

## Prepared single-sensor authenticated read-only test

A dedicated, standalone probe is now available at [`scripts/probe_remote_datapoint45_readonly.py`](../../scripts/probe_remote_datapoint45_readonly.py). It uses the already provisioned, encrypted RSA-1024 test profile, registers **only** the candidate RPC opcode 45, and sends **at most one** read for `obj=0, address=20` after the XML is accepted. It does not enable write opcode 43, make arbitrary-ID requests, print raw responses, alter Home Assistant files, or store credentials in Git. It uses the existing test profile and suppresses personal identifiers in printed output.

**The user has now executed the script against the authorized Genvex gateway.** The SDK accepted the XML and returned RPC status 0, with one signed 16-bit datapoint value (367). If the SDK returns a diagnostic, record only sanitized status/event codes. A plausible numerical temperature still requires independent comparison against the known local integration.

## Verified Steam Deck remote test (2026-11-19)

**Status 0 for XML registration and RPC invocation.** SDK 4.9.11, authorized CA-signed RSA-1024 test identity; query ID 45, obj 0, address 20, list count 1. Response was decoded as raw signed int16 value **367**; model-derived supply temperature is **6.7 °C**. Session closure and cleanup succeeded. This is a real remote response using our *own reconstructed RPC XML*, not the vendor's original XML. **Independent temperature comparison is still needed**; no claim that 6.7 °C is already validated as the actual air temperature. No writes were attempted; the working Home Assistant integration is unchanged.
