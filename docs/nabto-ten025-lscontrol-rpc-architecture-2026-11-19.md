# Official Nabto TEN025 and LS SmartConnect architectural implications

Date: 2026-11-19. **No device commands executed.**

## Stronger primary source: Nabto TEN025

Nabto's original `TEN025 Writing a Nabto API Client Application`, section 5.2.4, explicitly explains the migration from `nabtoFetchUrl` HTML Device Driver (HTML-DD) bundles to `nabtoRpcInvoke`. Most later clients **bundle the original `unabto_queries.xml` with the application as a file or literal source string**, rather than downloading it from the historical central HTML-DD repository. The client then installs XML with `nabtoRpcSetInterface` or `nabtoRpcSetDefaultInterface`. This explains the proven local `2000027 QUERY_MODEL_NO_SUCH_REQUEST` for `get_interface_info.json`: that query was missing in the client's installed XML, although its support on the device remains untested.

Source: https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf , sections 5.2.1, 5.2.4 and 6.1.

The same manual confirms:
- The `id` attribute is the compact opcode sent to device; caller-supplied name and XML are not discoverable automatically by SDK.
- Request/response types include `uint8`, `uint16`, `uint32`, signed analogues, `raw`, `list`. Exact fields and mapping are required before decoding.
- `nabtoFetchUrl` is deprecated for old HTML-DD documents; **not a general method to fetch the production RPC model from a current gateway**.
- `nabtoTunnelOpenTcp` is specifically **TCP** tunneling to an actual device-side TCP endpoint. It does not carry the existing LAN **UDP** 5570 register protocol without an additional supported service/proxy; neither has been established.
- `nabtoStreamOpen` requires a device-side streaming endpoint and its application protocol; cannot assume local UDP is available through it.
- The documentation's successful client session alone proves only that the local key can be opened, **not** remote device access.

## Another source: LS Control's manufacturer-specific bridge

The current LS Control product description states **LS SmartConnect Gateway** supports Modbus-equipped controllers and is **programmed by LS Control to expose the manufacturer-selected parameters**. Consequently one should not assume every local Optima 270 register has a corresponding remote RPC, or that an arbitrary Modbus mapping is valid remotely.

Source: https://lscontrol.dk/en/products/ls-smartconnect-gateway/

The historical LS SmartConnect brochure also distinguishes different platform designs, with some translations occurring in the gateway and others in cloud services. **Caution:** the sources describe a *product family*, not a reverse-engineered statement about the exact Optima 270 model or its currently installed firmware.

Brochure: https://exhibitorsearch.messefrankfurt.com/images/original/userdata/bata/175187/5c791c97accc2.pdf

## Result and priorities

1. The genuine **LS Control/Genvex-specific client-side RPC interface** remains the necessary missing piece. There was no trustworthy public Optima 270 production XML in searches of Nabto's repo and public materials.
2. Favor original Genvex Connect iOS/Android assets (when legitimately available), authorized legacy HTML-DD bundle, or direct manufacturer engineering support. Do not endlessly retry `get_interface_info.json` without a verified query-model entry.
3. Any future remote data operation must use a confirmed **read-only** query with verified opcode and response schema, in isolation from the currently working Home Assistant local transport.
4. Continue to treat the successful HAOS ARM64 QEMU `ping.json` as the authenticated remote connectivity baseline; evaluate distribution licensing and secret hygiene before product integration.

## Targeted support question

For the Optima 270 / Genvex Connect project, request an **official read-only Nabto 4/Micro RPC interface document (`unabto_queries.xml` or equivalent query ID, name, request and response schema)**, or a supported remote telemetry API. Ask whether the model is bundled in the current iOS app or hosted in a legacy HTML-DD archive, and whether third-party Home Assistant integration is permitted. Separately inquire about a licensed Linux aarch64 SDK, given success with existing x86_64 SDK under QEMU.

Do not disclose private client certificates, device IDs or personal access credentials in such an inquiry.
