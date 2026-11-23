# Remote endpoint attribution and Shelly Cloud IP assessment

Date: 2026-11-19  
Branch: `remote-nabto-connection`

## Decision and conclusion

The public remote Nabto Micro UDP endpoint observed in the iPhone capture is `80.208.69.3`. Public IP routing records attribute its prefix `80.208.0.0/17` to `AS44869 FIBIA P/S`. The customer reports that the summer-house ISP is Waoo, associated with Fibia. This is a useful circumstantial match, **not a verified match to the summer-house WAN IPv4**.

The observed HTTPS POST operations to `api.lscontrol.dk:4160` instead target `77.247.79.106:4160`. The two HAR bodies return HTTP 200 with `{"Status":"1"}`, whose application-level meaning is not documented. These calls do not themselves show a TCP-to-UDP upgrade. The separate HTTP `101 Switching Protocols` responses in the capture are WebSocket upgrades (TCP remains TCP).

The highest-value next observation is an independent, contemporaneous WAN IPv4 reading from the summer-house network or its router/provider, compared with a fresh iPhone Nabto session's destination IP. Do not treat Fibia ownership alone as proof of direct P2P.

## Passive packet-level corroboration (no network probes)

Inspection of the largest supplied `genvex-fan-change-v3.pcap` shows four successively observed UDP sessions to the same IPv4 address:

| Remote UDP port | First observed packet, Copenhagen time | Initial exchange |
| --- | --- | --- |
| 30721 | 15:00:15.136938 | 26-byte U_CONNECT request, 36-byte response, 44-byte client packet |
| 30723 | 15:07:45.951200 | 26-byte U_CONNECT request, 36-byte response, 44-byte client packet |
| 30725 | 15:10:40.235184 | 26-byte U_CONNECT request, 36-byte response, 44-byte client packet |
| 30727 | 15:16:37.356886 | 26-byte U_CONNECT request, 36-byte response, 44-byte client packet |

These are packet-observed session addresses and times, **not prescribed connection ports**. The subsequent encrypted Nabto DATA exchange is bidirectional. Port variation and the U_CONNECT exchange are consistent with Nabto connection setup, but do not conclusively distinguish direct P2P from a relay or otherwise attribute the public address to the physical gateway.

### Important capture deduplication correction

The uploaded `genvex-fan-change.pcap`, `genvex-fan-change-v2.pcap` and `genvex-fan-change-v3.pcap` are **successive cumulative byte-prefix captures**. Exact raw byte-prefix comparisons confirm the first file is a prefix of the second and the second is a prefix of the third.

Therefore observations from the three files **must not be summed as independent packet counts**. The previous documentation counted `571 + 938 + 1,325 = 2,834` server-to-phone DATA/CRYPTO packets, double/triple-counting earlier packets. The correct unique count in the largest file is **1,325**. All 1,325 still exhibit the same responder-side 16-byte IV field `00 01 ... 0f`. The crypto anomaly therefore remains observable, but with a corrected unique sample size.

The three fan-change windows (15:08, 15:12, 15:17) and nine marked changes are distinct events inside the ongoing recording, despite the files being cumulative snapshots.

## Shelly Plus Plug S and Cloud Control API

The customer has a Shelly Plus Plug S remotely integrated through Shelly Cloud API into a different Home Assistant installation and cannot configure scripts or Actions on the plug through their current access.

Official documentation for Shelly Cloud Control API v2 describes retrieving device `status` and `settings`, and sending specific output-control commands. The Wi-Fi status `sta_ip` is the **local IP of the Shelly on its network**, not the external WAN IP. The documented Cloud Control API **does not expose arbitrary on-device `HTTP.GET` or a generic remote RPC execution endpoint**. While the device-local RPC API supports `HTTP.GET`, that is not evidence that Shelly Cloud can invoke that method on the customer's remotely hosted plug.

It is therefore **not justified** to claim the existing Shelly Cloud integration can reveal the site's public IPv4 without further access, or to toggle the plug in hopes of obtaining it. Calling `api.ipify.org` from Home Assistant outside the summer-house network would show that Home Assistant's public egress, not the summer-house address.

References:
- https://shelly-api-docs.shelly.cloud/cloud-control-api/communication-v2/
- https://shelly-api-docs.shelly.cloud/cloud-control-api/
- https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/WiFi/
- https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/HTTP/
- https://ipinfo.io/ips/80.208.69.0/24

## Practical next measurement

1. Find an **existing**, already-authorized way to read the summer-house router's WAN IPv4 remotely (router app / management portal), or ask the Waoo/Fibia connection provider whether they can provide the current WAN IPv4 for that subscriber. The provider may or may not expose this information.
2. Record **when** the WAN address was read. Dynamic address changes and CGNAT can complicate attribution.
3. Open the Genvex Connect app on the iPhone from outside that LAN, record a short, passive new-session PCAP on the SteamOS hotspot, and identify the endpoint IPv4 of the Nabto DATA session (do not rely on a hard-coded port).
4. Compare the contemporaneous public IP readings. If they match, the direct-P2P-to-WAN hypothesis becomes strong; if not, do not immediately infer relay without checking whether the WAN IPv4 changed or the router is behind CGNAT.

A WAN IP match would clarify endpoint attribution, **not** solve the independent Nabto 4 profile/CA authorization and remote RPC interface blockers.

No Home Assistant integration source or Shelly settings were changed, and no active probing or packet replay was performed.
