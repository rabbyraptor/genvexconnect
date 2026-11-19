# Remote Nabto 4 — verified facts manifest

**Status:** remote read-only RPC proven on 2026-11-19.  
**Target:** Genvex Connect / Optima 270; eventual Home Assistant OS on Raspberry Pi (Linux aarch64).  
**Evidence level:** successful end-to-end read-only remote RPC both on Linux x86_64 Steam Deck (Python ctypes + Nabto 4 SDK 4.9.11) **and on Raspberry Pi HAOS ARM64** (x86_64 Nabto CLI/SDK through QEMU user-mode). This is emulation, not a native ARM64 client or production integration.  
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
| Native Linux aarch64 Nabto 4 client | **OPEN** | No native Linux aarch64 SDK/client found or validated; no completed Home Assistant remote adapter. |
| Non-ping Genvex RPC operations | **OPEN** | No production Optima 270 telemetry or control RPC interface identified/validated yet. Local UDP point mappings are **not** automatically the remote Nabto RPC schema. |
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
            -> RPC 17, ping.json -> JSON response
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

## Safety, privacy and engineering guardrails

1. **Do not commit** actual client certificates, private keys, account passwords, local passphrases, device identifiers, or unredacted PCAP/HAR captures.
2. RSA-1024, SHA-1-era certificates and 3DES are **legacy compatibility mechanisms**, not appropriate cryptographic defaults for new systems. Evaluate ongoing security and vendor-supported alternatives before deployment.
3. Keep remote tests read-only until the individual RPC calls, authorization, error paths and timeout behavior are verified.
4. Do not confuse Nabto **Micro/4** with **Nabto Edge/5**; Edge binaries and APIs are not compatible drop-in replacements.
5. No changes to `custom_components/genvex_connect` without a separate implementation decision. Preserve the existing working local UDP integration.
6. Publicly redistributing the proprietary Nabto SDK requires reviewing permission/licensing. Test access to the shared library does not establish redistribution rights.
7. Isolated diagnostics should set timeouts, minimize sensitive output, and securely manage keys. Successful `ping` does not validate controller write capabilities, transport resilience or ARM64 portability.

## Next experiments (ordered)

1. **Map more *read-only* RPCs:** obtain the actual Optima 270 / LS Control query model (`unabto_queries.xml`) from available firmware, app resources or manufacturer documentation; do **not** guess IDs or perform writes. Verify one safe telemetry RPC on x86_64 with the already-working client, recording its schema and sanitized result here.
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
