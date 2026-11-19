# Reconstructing a read-only remote RPC query from the LAN implementation

Date: 2026-11-19  
**Status: experimentally promising hypothesis; NOT verified via remote device.**

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
| `DATAPOINT_READLIST` | 0x2d | **45** | Read datapoints | **UNVERIFIED REMOTE** |
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

- [`tests/fixtures/candidate_readonly_query45.xml`](../tests/fixtures/candidate_readonly_query45.xml) — *hypothetical* read-only schema, mapping query ID **45** to list fields `obj:uint8`, `address:uint32`, and an explicit `trailer:uint8=1`, with a candidate response list of signed 16-bit values.
- [`tests/test_reconstructed_readonly_rpc.py`](../tests/test_reconstructed_readonly_rpc.py) — offline-only comparison against public LAN serialization.

The author ran **four equivalent offline structural tests**, passing for one, three, and zero datapoints and a schema assertion. The test reimplements the documented encoding and checks exact bytes; **this does NOT prove the closed-source Nabto 4 Client SDK will accept the XML or serialize it identically**.

The candidate response schema `list(values: int16)` reflects the publicly documented local decoder's `uint16 count` followed by signed 16-bit values. The trailing `01` in the LAN request is not yet explained; modeling it as an extra `uint8` parameter is a **testable hypothesis**.

## Safe validation steps

1. First use the already provisioned Steam Deck client and **only the local Nabto SDK parser** (`nabtoRpcSetDefaultInterface`) to verify that the candidate schema is valid; no controller invocation required for this step.
2. If accepted, authorize/perform **one read-only query 45** for **one verified Optima 270 datapoint** (`obj=0, address=20`) through the existing authenticated remote connection. No batch, no guessed ID range, and no writes.
3. Classify SDK status and error event while suppressing credential, endpoint and raw JSON logging; if successful, decode a single raw int16 reading and apply the existing model's `(raw - 300)/10` temperature conversion.
4. Independently compare with the existing local integration when both are available, without changing the local integration.
5. Only after verification, extend schema to known, read-only datapoint addresses and later setpoint reads. Do **not** infer write safety or enable ID 43.

## Risk/constraints

Remote reachability of query 45, device handler behavior, XML request's trailing byte, exact response layout, and licensing/distribution of the legacy binary **remain OPEN**. A valid local schema and working ping do not prove a new query is present remotely. Keep the existing HAOS integration untouched.
