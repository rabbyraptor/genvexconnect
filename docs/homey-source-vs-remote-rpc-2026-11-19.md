# Homey Genvex Connect source inspection — relevance to remote RPC

Date: 2026-11-19  
Evidence: public source at https://github.com/andersdissing/com.genvex.connect (examined on default branch)

## Finding

The open-source Homey Genvex Connect app contains an extensive **local** Optima 270 register and packet implementation, but **does not implement the Nabto 4 remote SDK RPC interface**. It therefore cannot supply verified remote `unabto_queries.xml` query IDs beyond the independently established `ping.json` ID 17.

### Inspected source files

- `lib/nabto/NabtoClient.js`: discovery and local connection API.
- `lib/nabto/NabtoConnection.js`: Node.js `dgram` UDP socket to a supplied LAN IP on port 5570, local `U_CONNECT`, DATA packet exchange, keepalive. Uses a local account email.
- `lib/genvex/Optima270.js`: named datapoint and setpoint register maps and conversion formulas; calls `CMD_DATAPOINT_READLIST`, `CMD_SETPOINT_READLIST`, `CMD_SETPOINT_WRITELIST` through the local packet implementation.
- `lib/genvex/GenvexDevice.js`: local register polling, connection lifecycle and data conversion.
- `drivers/optima270/device.js`: Homey sensor and control entity mappings.

### Selected local Optima 270 datapoint addresses (**NOT** remote RPC IDs)

| Source field | Local datapoint address | Conversion | Source |
| --- | ---: | --- | --- |
| Supply temperature | 20 | `(raw - 300) / 10` | `Optima270.js` |
| Outdoor temperature | 21 | `(raw - 300) / 10` | `Optima270.js` |
| Exhaust temperature | 22 | `(raw - 300) / 10` | `Optima270.js` |
| Extract temperature | 23 | `(raw - 300) / 10` | `Optima270.js` |
| Humidity | 26 | `raw` | `Optima270.js` |
| Supply/extract fan duty | 18 / 19 | `raw / 100` | `Optima270.js` |
| Supply/extract RPM | 35 / 36 | `raw` | `Optima270.js` |
| Bypass active / alarm | 53 / 38 | `raw` | `Optima270.js` |

These address mappings come from a **public third-party local implementation**. They are useful for eventual entity mapping, but we have not independently verified each value via remote Nabto 4 RPC.

### Operational implications

1. Do **not** send local register addresses as Nabto 4 RPC query IDs; these are distinct layers.
2. The Homey library is a potential model/reference implementation for mapping **after** the correct remote RPC interface is available.
3. Find the production interface from the Genvex Connect mobile client resources, authorized firmware or LS Control/Nabto technical specification; do not blindly enumerate candidate IDs.
4. Keep local UDP and remote Nabto SDK paths isolated.

## Status

- **Verified:** independent remote `ping.json` through Nabto SDK 4.9.11 on Steam Deck and HAOS ARM64 through QEMU.
- **Source-established:** Homey repository implements known local register readings.
- **Open:** actual production remote read query name, numeric ID, request/response schema, and whether it wraps these local register operations.

Reference: [verified facts manifest](remote-nabto-verified-facts.md).
