# Remote Nabto 4 — verified facts manifest

**Status:** authenticated remote Nabto RPC 17 (ping) and RPC 45 (five independent sensor reads and one five-item batch) proven on 2026-11-19; supply-air interpretation independently corroborated by the user's official Genvex Connect app screenshot.  
**Target:** Genvex Connect / Optima 270; eventual Home Assistant OS on Raspberry Pi (Linux aarch64).  
**Evidence level:** authenticated remote ping on Linux x86_64 Steam Deck and on Raspberry Pi HAOS ARM64/QEMU; additionally, read-only datapoint RPC ID 45 returned five successful one-sensor reads **and one successful five-sensor batch in a single RPC** on Steam Deck x86_64. RPC 45 has not yet been tested on HAOS/QEMU. This is emulation for HAOS, not native ARM64 or a production integration.  
**Scope:** experimental remote transport only. The working local UDP integration is unchanged.

This file is the **single source of truth for the current project state**. The other documents preserve investigation history, hypotheses and capture evidence. When they conflict with this document's verified later experiments, prefer this manifest and the underlying captured output.

## Evidence labels

- **VERIFIED:** observed successfully in our controlled tests, with SDK return values or independent certificate checks.
- **SOURCE:** demonstrated in linked upstream source code, but not necessarily reproduced on this controller.
- **OBSERVED:** recorded in packet/application captures without proven interpretation.
- **OPEN:** hypothesis, unresolved requirement or untested implementation.

## Proven facts — 2026-11-19

| Area | Status | Evidence / limitation |
| --- | --- | --- |
| Legacy CA registration endpoint | **VERIFIED** | HTTPS form POST to `https://lscontrol.nabto.com/service/register` with `email`, `password`, and PEM `csr`; successful response starts with status `0` and `Success` followed by a PEM X.509 certificate. Authentication uses the user's own Genvex Connect account credentials. |
| RSA key requirement in tested SDK | **VERIFIED** | The 2048-bit certificate/key was CA-verifiable and matched, but `nabtoOpenSession` returned `18`. SDK log: `EVP_PKEY_get_size(key) is 256, it must be 128`; it expects a 128-byte RSA key in this path (RSA-1024). Do **not** generalize to every Nabto SDK version or application. |
| 1024-bit CA-signed client identity | **VERIFIED** | RSA-1024 CSR using SHA-256 accepted; portal returned `0 / Success`. Certificate checked with original legacy Nabto CA, `openssl verify -auth_level 0`; certificate public key matches private key. A preceding 1024-bit attempt had portal status `1`, with its message not captured: reason **unknown**, not assumed to be key-size rejection. |
| Local key protection | **VERIFIED** | Encrypted PKCS#8 key with PBES2 / PBKDF2-HMAC-SHA256 / 2048 iterations / 3DES works in tested SDK. Unlock password is a separately chosen *local key passphrase*, **not** necessarily the Genvex account password. Keep certificate/key/passphrase out of the repository and diagnostic logs. |
| Profile naming | **VERIFIED** | SDK profile files in `<nabto-home>/users/`: `<email-with-@-replaced-by-_at_>.crt` and `.key`. SDK profile discovery alone does not establish that a session opens. |
| SDK load on Linux x86_64 | **VERIFIED** | `libnabto_client_api.so` obtained from the isolated Nabto CLI test runtime loads with Python `ctypes.CDLL` on Steam Deck x86_64. `nabtoStartup`, `nabtoInstallDefaultStaticResources`, `nabtoOpenSession`, `nabtoStatusStr`, `nabtoRpcSetDefaultInterface`, `nabtoRpcInvoke`, `nabtoCloseSession`, `nabtoShutdown` are accessible. |
| Open authenticated SDK session | **VERIFIED** | With the newly issued 1024-bit cert and encrypted key: `nabtoStartup = 0`, static resources `= 0`, `nabtoOpenSession = 0`, and `nabtoCloseSession = 0`. This is a local SDK session result, not on its own proof of device reachability. |
| LS Control RPC ping definition | **SOURCE + VERIFIED** | Nabto's `cordova-lsc-test/www/js/index.js` defines query ID `17`, name `ping.json`, one uint32 input `ping`, and response fields below; the exact interface successfully installed through `nabtoRpcSetDefaultInterface = 0` in our test. |
| **Remote authenticated RPC** | **VERIFIED** | With the same 1024-bit profile and the device's private, account-associated `<12-digit-id>.remote.lscontrol.dk` hostname: `nabtoRpcInvoke('nabto://<device>/ping.json?ping=1885957735') = 0`, yielding the gateway response below. This is the key end-to-end milestone. |
| **HAOS ARM64 + QEMU remote RPC** | **VERIFIED** | On Raspberry Pi HAOS, isolated test app `app_local_genvex_nabto_runtime_test` ran Nabto CLI v1.3.0 / SDK 4.9.11 through `qemu-x86_64-static -L /opt/x86_64-sysroot`; encrypted RSA-1024 profile transferred securely via SSH, `ping.json` RPC returned exit status `0` and the same six numeric gateway values as the Steam Deck baseline; temporary profile removal reported `True`. The native SDK process remains x86_64 emulated. |
| **RPC 45 / datapoint read** | **VERIFIED ON X86_64** | SDK accepted source-derived XML (0), invoked RPC 45 for one known read-only datapoint (obj=0, address=20) (0), and decoded one signed 16-bit raw value 367 -> *candidate* supply-air temperature 6.7 °C. Official app screenshot at 22:33 showed **Supply air 6.70 °C**, matching the independently obtained remote value exactly; HAOS/QEMU RPC 45 support remains OPEN. No writes. |
| **Five-source-defined sensor remote reads** | **VERIFIED ON X86_64** | One authenticated Nabto SDK session registered a reconstructed read-only RPC ID 45 XML and completed **5/5 individually addressed** sensor reads with status 0 and correctly decoded signed-int16 values. Addresses 20/21/22/23/26; see the result table below. Batch requests and HAOS/QEMU for RPC 45 not yet tested. |
| Native Linux aarch64 Nabto 4 client | **OPEN** | No native Linux aarch64 SDK/client found or validated; no completed Home Assistant remote adapter. |
| Additional Genvex RPC operations | **PARTIALLY OPEN** | Read-only datapoint RPC **45** verified for a single sensor. Other addresses, batched reads, setpoint read ID 42 and all write/control operations remain untested. No complete production XML recovered. Local register addresses are distinct from application query IDs. |
| Route details | **OPEN** | A successful remote response does **not** distinguish direct P2P from Nabto relay; do not claim which was used without separate evidence. |

### End-to-end response actually received

The first remote call using the independently provisioned CA-signed profile returned `nabtoRpcInvoke = 0 (operation successful)`. The diagnostic deliberately omitted `UserNames:` and other potentially sensitive data:

```json
{
  "Pong": 1886350951,
  "Devicenumber": 79265,
  "Model": 2010,
  "Version": 11,
  "SlaveDevicenumber": 0,
  "SlaveModel": 11
}
```

The value `1886350951` corresponds to ASCII `pong` (`0x706f6e67`); input `1885957735` corresponds to `ping` (`0x70696e67`). The numeric device/model values are test observations, **not** a publicly reusable target or definitive mapping of all controller capabilities. Keep real account email, full device hostname, private key and credentials out of the public docs.

### Working test architecture

```text
Steam Deck (Linux x86_64)
  Python ctypes
    -> legacy libnabto_client_api.so (SDK 4.9.11)
      -> Nabto CA-signed RSA-1024 identity + encrypted private key
        -> legacy Nabto remote transport (path/relay not yet established)
          -> Genvex Connect / Optima 270
            -> RPC 17 (ping) and RPC 45 (single Steam Deck datapoint read) -> JSON response
```

**No iPhone translation layer is required for this proven path.** The HAOS ARM64 test now proves remote RPC **under x86_64 user-mode emulation**. This is SDK-backed, **not** a pure-Python Micro Nabto implementation, native ARM64 library, licensed production bundle or completed Home Assistant integration.

### Second independently executed environment: HAOS ARM64 using QEMU (2026-11-19)

- Source: the user's successful output of `HAOS ARM64 NABTO QEMU TEST`.
- All four stages returned zero: `Create temporary directory: 0`, `Create profile directory: 0`, `Transfer encrypted profile: 0`, and `Remote RPC through QEMU: 0`.
- Returned `Pong: 1886350951`, `Devicenumber: 79265`, `Model: 2010`, `Version: 11`, `SlaveDevicenumber: 0`, `SlaveModel: 11`.
- `Temporary files removed: True`; existing HA integration unchanged.
- Execution path: Steam Deck orchestration / encrypted SSH profile transfer -> HAOS Docker test container -> QEMU Linux x86_64 SDK + CLI -> remote Nabto 4 `ping.json`.
- **Important limits:** this test does not quantify latency, CPU, RAM, reboot persistence, reconnection, transport route, deployment security, SDK redistribution rights, or production viability; test credentials live transiently in the CLI process command line while it runs.

## Reproducible technical details (sanitized)

- Legacy client SDK: Nabto **4.9.11** from Nabto CLI **v1.3.0**, Linux x86_64 ELF shared library.
- CLI test environment on HAOS: isolated `haos-apps/genvex-nabto-runtime-test`, Linux x86_64 CLI through `qemu-x86_64-static` and an x86_64 sysroot. The separate SDK-loaded Python test succeeded on the Steam Deck without QEMU.
- Provision: OpenSSL RSA-1024 private key and SHA-256 CSR with subject `/emailAddress=<account-email>`; form POST `email`, `password`, `csr` to the confirmed LS Control registration endpoint.
- Certificate chain: legacy Nabto issuer `C=DK, O=Nabto` (not the separate `Nabto NG` CA); the old chain uses deprecated cryptography. `openssl verify -auth_level 0` was used as a compatibility check, **not** a modern security endorsement.
- PKCS#8 key: `openssl pkcs8 -topk8 -v2 des3 -v2prf hmacWithSHA256 -iter 2048`; store the passphrase separately and enter it interactively.
- SDK call sequence: `nabtoStartup(home)` -> `nabtoInstallDefaultStaticResources(NULL)` -> `nabtoOpenSession(&session, email, key_passphrase)` -> `nabtoRpcSetDefaultInterface(session, xml, &error)` -> `nabtoRpcInvoke(session, url, &response)` -> free returned SDK allocations -> `nabtoCloseSession(session)` -> `nabtoShutdown()`.
- SDK status: `0` = success; status `18` was a **generic** error for the 2048-bit mismatch. The specific reason came from `nabtoRegisterLogCallback`, not the status code alone.
- Endpoint: `nabto://<device-id>.remote.lscontrol.dk/ping.json?ping=1885957735` (replace device ID only in private test environment).
- RPC interface from Nabto's own LS Control source: query `17`, input `ping: uint32`; response `Pong`, `Devicenumber`, `Model`, `Version`, `SlaveDevicenumber`, `SlaveModel` as uint32, plus `UserNames:` as raw. Do not print or publish the username field.

### First non-ping authenticated remote datapoint result (2026-11-19)

**VERIFIED USER OUTPUT, Steam Deck x86_64, Nabto SDK 4.9.11:**

```text
===== READ-ONLY RPC 45 CANDIDATE =====
SDK startup: 0
Resources: 0
Profile session: 0
Candidate XML registered: 0
Invoking: read-only ID 45; object 0; address 20; count 1
RPC status: 0
Raw supply temperature register: 367
Decoded temperature (candidate): 6.7 C
Result: RESPONSE_DECODED_UNVERIFIED
Session close: 0
SDK shutdown: 0
Temporary profile: removed on normal exit
Test exit status: 0
```

The candidate query ID 45 was reconstructed from the source-defined LAN opcode DATAPOINT_READLIST=0x2d. The XML request was a list containing a single entry (obj=0, address=20) and a trailing uint8=1; response schema: list(values:int16). The client-side *name* candidate_read_datapoints.json was chosen by us and is not claimed as the vendor's original RPC name. The authenticated remote gateway supplied a successful decoded response.

**Boundary:** SDK RPC status 0 and decoded response confirm a working read-only RPC 45 operation, not just a ping. Raw 367 is a device response. The temperature interpretation 6.7 °C derives from the public Optima 270 LAN adapter (raw-300)/10 and has NOT been independently validated against the contemporaneous local sensor or app. RPC 45 has NOT yet been tested on HAOS/QEMU. Do not infer remote support for query 42, arbitrary addresses, batching, control or writes. No existing HA integration changes.

Related: [RPC 45 derivation](reconstructed-readonly-query45-2026-11-19.md) · [read-only probe](../scripts/probe_remote_datapoint45_readonly.py).

### Independent manufacturer-app comparison — 2026-11-19

**VERIFIED by contemporaneous user-provided screenshot:** the official Genvex Connect iOS application displayed **`Supply air: 6.70 °C`** at phone clock **22:33**, matching our previously obtained standalone SDK 4.9.11 read-only RPC ID **45**, object **0**, address **20**, raw **367**, interpreted using the published adapter as **6.7 °C**.

The screenshot also showed potential follow-up benchmarks: outdoor air **0.20 °C**, exhaust air **1.80 °C**, extract air **7.60 °C**, humidity **66 %**, supply fan **60.00 %**, extract fan **58.00 %**, bypass off, and controller version **11**. These are **snapshot reference readings, not guaranteed to persist** and have not yet been retrieved with the independent RPC client. The screenshot was supplied privately in the conversation and is **not** committed to this repository.

**Result:** A single **source-derived, authenticated remote sensor datapoint** can be read using our own Nabto 4 SDK client and its reported real-world interpretation **matches the official Genvex application** at the displayed value. It is still one sample: accuracy over time, multi-datapoint list handling, query 42, and HAOS/QEMU RPC 45 remain to validate. No existing HA integration changes, writes, or sensitive identifiers exposed.

### Phase 1: five individual remote sensor reads — 2026-11-19

**VERIFIED by user-supplied terminal output** from Linux x86_64 Steam Deck using the existing authorized RSA-1024 profile and Nabto SDK 4.9.11. SDK startup, resources, session, XML setup, session closure and shutdown all returned status `0`. All five read-only RPC 45 calls decoded successfully and test exited 0:

| Optima 270 datapoint | Address | Raw | Decoded | SDK invocation duration |
| --- | ---: | ---: | ---: | ---: |
| Supply air | 20 | 365 | 6.50 °C | 335 ms |
| Outdoor air | 21 | 299 | -0.10 °C | 17 ms |
| Exhaust air | 22 | 313 | 1.30 °C | 16 ms |
| Extract air | 23 | 376 | 7.60 °C | 16 ms |
| Humidity | 26 | 66 | 66 % | 16 ms |

Each address was read separately, using the reconstructed RPC 45 model's list of **one** `obj=0, address=<listed>` item, and `trailer=1`. These are source-documented Optima 270 datapoint addresses, **not enumerated or guessed IDs**. The supplied app screenshot predates this capture and is only an approximate reference, not a simultaneous ground truth. The first invocation likely incurred setup overhead, but this causal explanation is not yet independently measured. One run cannot establish typical latency or stability. Reference: [phase 1 validation](remote-phase1-sensor-validation-2026-11-19.md).

**Next unverified milestone:** validate the newly successful five-element batch inside the isolated HAOS/QEMU runtime. Never assume writes are supported. No changes to the current local HA integration.

### Phase 1B — verified read-only RPC 45 five-element batch (2026-11-19)

**VERIFIED from user's Steam Deck terminal output:** same existing authenticated x86_64 Nabto SDK 4.9.11 test profile, with explicit passphrase via stdin. `nabtoStartup`, `nabtoInstallDefaultStaticResources`, `nabtoOpenSession` and `nabtoRpcSetDefaultInterface` all returned **0**. Exactly one `nabtoRpcInvoke` for query **45** with the ordered five-item request `obj=0`, addresses **20, 21, 22, 23, 26**, trailer=1, returned **RPC status 0** in **318 ms**. Its response decoded to **five signed int16 values**:

| Address | Sensor | Raw | Converted |
| ---: | --- | ---: | ---: |
| 20 | Supply air | 365 | 6.50 °C |
| 21 | Outdoor air | 299 | -0.10 °C |
| 22 | Exhaust air | 313 | 1.30 °C |
| 23 | Extract air | 377 | 7.70 °C |
| 26 | Humidity | 65 | 65 % |

Log ended `Read-only batch decoded: 5/5`, `Result: BATCH_DECODED`, session close 0, SDK shutdown 0, cleaned temporary profile and wrapper success. This demonstrates **one working five-address remote batch**, including response count and values consistent with individual reads and expected position ordering. Since no response-side address IDs were present, response **ordering is strongly corroborated rather than independently proven for every possible list**. An additional repeated/reordered batch could check this if needed. The 318 ms is one observed elapsed time and not a latency benchmark.

**Now next gate:** run the same read-only batch inside the **existing isolated** HAOS Raspberry Pi 4 ARM64/QEMU test runtime. Do not change the working Home Assistant integration, commit private credentials or SDK binaries, or enable writes. Confirm SDK/CLI invocation and response decoding in the emulated environment; only then plan HA entity mapping and runtime deployment.

## Safety, privacy and engineering guardrails

1. **Do not commit** actual client certificates, private keys, account passwords, local passphrases, device identifiers, or unredacted PCAP/HAR captures.
2. RSA-1024, SHA-1-era certificates and 3DES are **legacy compatibility mechanisms**, not appropriate cryptographic defaults for new systems. Evaluate ongoing security and vendor-supported alternatives before deployment.
3. Keep remote tests read-only until the individual RPC calls, authorization, error paths and timeout behavior are verified.
4. Do not confuse Nabto **Micro/4** with **Nabto Edge/5**; Edge binaries and APIs are not compatible drop-in replacements.
5. No changes to `custom_components/genvex_connect` without a separate implementation decision. Preserve the existing working local UDP integration.
6. Publicly redistributing the proprietary Nabto SDK requires reviewing permission/licensing. Test access to the shared library does not establish redistribution rights.
7. Isolated diagnostics should set timeouts, minimize sensitive output, and securely manage keys. Successful `ping` does not validate controller write capabilities, transport resilience or ARM64 portability.

## Next experiments (ordered)

1. **Validate the verified *read-only* RPC 45 batch on HAOS/QEMU:** x86_64 single-point reads and a five-sensor batch are now successful; reproduce the batch in the isolated ARM64/QEMU test environment, then benchmark stability and safely map to HA entities. Never attempt writes or assume other query models. The original production XML remains useful but is no longer a prerequisite for cautious read-only progress.
2. **Reference client:** preserve the proven Python/ctypes experiment as a **local/private** test fixture; extract a sanitized, non-secret template only after the interface is known. Do not commit SDK binaries or working credentials.
3. **ARM64 path:** investigate a licensed native Nabto 4 Client SDK for Linux aarch64; separately evaluate whether an isolated emulated x86_64 service can be supported on HAOS as a **fallback**. **Remote RPC on HAOS ARM64 through QEMU has now succeeded.** Next evaluate its maintainability and security, including CPU/memory, reconnection, restart behavior and supported SDK licensing before considering it a deployable fallback.
4. **Integration architecture:** abstract remote transport behind the existing Home Assistant entities only after the read RPC schema and runtime packaging are verified. Keep local and remote modes isolated, with explicit credential handling and a tested fallback.
5. **Remote behavior:** establish timeout/reconnection, credential lifecycle, gateway authorization and direct-vs-relay behavior in controlled, read-only tests.

## Historical evidence and upstream sources

- [Investigation log](remote-nabto-investigation.md) — earlier hypotheses/captures; some old statements are superseded by this manifest.
- [RPC research](remote-nabto-rpc-findings.md) — historical RPC research, not a verified production Optima 270 query list.
- [SDK / identity research](nabto4-client-sdk-availability-and-identity-2026-11-19.md) — public distribution and CA model; older statements about portal/profile being unknown have now been resolved experimentally.
- [LS Control test app source analysis](lsc-nabto-test-app-analysis.md) — source definition of `ping.json` and its **local** demo. Our own later remote test independently proves the remote case.
- [HAOS test app notes](../haos-apps/genvex-nabto-runtime-test/DOCS.md) — isolated QEMU runtime design; not a production remote transport.
- Upstream LS Control query: https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js
- Upstream Nabto CLI: https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp
- Upstream Nabto legacy C API header: https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h

**Revision policy:** append or update VERIFIED rows only after actual reproducible results. Keep failed tests and unresolved hypotheses accurately labeled.
