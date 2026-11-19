# Remote Nabto — next RPC discovery and ARM64 validation

Date: 2026-11-19  
Baseline: [verified facts manifest](remote-nabto-verified-facts.md)

## 1. Finding the real telemetry RPC schema

**Confirmed:** authenticated remote `ping.json` / query 17 works on Linux x86_64 with an official Nabto 4 SDK; it returns identifiers and a pong word. It is **not** a controller telemetry endpoint.

**Not confirmed:** any production Optima 270 query ID, JSON name, parameter type, or mapping from the existing LAN UDP point model to Nabto RPC.

### Discovery order

1. Inspect app assets or an authorized firmware bundle for `unabto_queries.xml`, `<unabto_queries>`, XML snippets, and Nabto `rpcSetDefaultInterface` / `rpcSetInterface` usage. An interface definition is **data**, not necessarily a standalone file.
2. Inspect any manufacturer-provided schema or technical docs; check concrete request IDs and response field types against the Optima 270 model before issuing RPC.
3. Once a specific **read-only** RPC is established by source evidence, run it through the *existing* x86_64 Python/ctypes reference client; whitelist numeric/known nonsensitive response fields.
4. Record one experiment per operation: provenance of XML definition, query name and numeric ID, input types, output types, successful SDK return code, sanitized output, and device/firmware version. No writes until read operations have been fully characterized.

**Do not** enumerate or brute-force query IDs or infer a write command from captured DATA packet lengths. Lack of a documented interface is a real discovery gate. A `get_interface_info.json` request appears in Nabto CLI's **optional strict-check** code path but must **not** be assumed supported by this controller or treated as the full interface description.

### Known RPC model

```xml
<query id="17" description="Ping" name="ping.json">
  <request>
    <parameter name="ping" type="uint32"/>
  </request>
  <response format="json">
    <parameter name="Pong" type="uint32"/>
    <parameter name="Devicenumber" type="uint32"/>
    <parameter name="Model" type="uint32"/>
    <parameter name="Version" type="uint32"/>
    <parameter name="SlaveDevicenumber" type="uint32"/>
    <parameter name="SlaveModel" type="uint32"/>
    <parameter name="UserNames:" type="raw"/>
  </response>
</query>
```

Source: https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js . This is the verified control/sample query, not the complete Optima 270 query model.

## 2. ARM64 decision gates

The native library reference runs **Linux x86_64**. Raspberry Pi 4 with 64-bit HAOS runs **Linux aarch64**. **2026-11-19 update: the already-installed isolated HAOS test app successfully executed an authenticated remote `ping.json` through QEMU x86_64** and got the exact six numeric values recorded on Steam Deck. This proves emulated runtime compatibility for the tested RPC, **not** a native ARM64 library or production suitability. Simply using `ctypes` does not remove the native architecture dependency.

| Candidate | Present status | Verification needed |
| --- | --- | --- |
| Native legacy Nabto 4 Client SDK for Linux aarch64 | Not located/verified | Ask Nabto for compatible binary/source access and SDK licensing, plus redistribution terms |
| Separate x86_64 user-mode QEMU runtime in an isolated ARM64 Home Assistant app | **Verified end-to-end remote ping from HAOS via QEMU** (CLI exited 0; JSON pong and gateway values matched Steam Deck; temporary profile removed) | Benchmark CPU/memory/reconnect/restarts, isolate credential storage and process arguments, review emulator and proprietary SDK licensing |
| Separate x86_64 host/sidecar | Technically plausible but additional host dependency | Operational and security tradeoffs, not plug-and-play |
| Pure Python native Micro Nabto client | Not implemented | Substantial authentication, key exchange, transport, crypto, relay and RPC work; cannot claim compatibility from observed packet headers |
| Nabto Edge Linux ARM64 | Available for *different* protocol generation | Not a compatible Micro client; do not substitute |
| Android arm64-v8a JNI artifact | Android ABI, not GNU/Linux ABI | Cannot use as drop-in native HAOS library |

**Recommended sequencing:** first establish telemetry RPC schemas on the proven x86_64 reference. The same read-only ping **already succeeded** inside the isolated HAOS QEMU test app. Next evaluate whether that proven emulated fallback is maintainable while seeking a native/licensed ARM64 SDK. Integrate only after these gates are met.

## 3. Secrets and reproducibility

- Never publish full account email, device ID/hostname, private key, encrypted key, password, remote capture, or raw responses with user names.
- Keep testing inside isolated directories and the already-created test app. Preserve working local UDP paths.
- Treat 1024-bit RSA / 3DES / old CA signatures as compatibility-only and a security constraint; production suitability requires additional review.
- Do not claim path is peer-to-peer vs relay solely from successful `nabtoRpcInvoke`.
- Restrict experiments to a user-authorized gateway.
