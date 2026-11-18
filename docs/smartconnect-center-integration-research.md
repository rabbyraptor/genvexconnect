# Genvex Smart Connect Center and Nabto authentication findings

Date: 2026-11-18

## New potential integration route: Smart Connect Center

Official Genvex documentation confirms that **all Genvex systems with Optima 270 control can be connected to Smart Connect Center**. The service is aimed at professional administrators, housing associations, facility management and installers—not ordinary end users.

The official product page lists:
- current operating values and historical operating data;
- alarms and event logs;
- service history;
- remote adjustment/optimization of operating parameters;
- immediate notifications when systems develop faults or go offline;
- grouping systems by property.

Sources:
- https://www.genvex.com/produkter/genvex-tilbehor/smart-connect-center
- https://www.genvex.com/en/products/genvex-accessories/smart-connect-center

LS Control's own product page says SmartConnect Center is not intended for end users; it is a fleet-management system for manufacturers and service companies, with access potentially resold to dealers/service providers for selected products:
https://lscontrol.dk/products/ls-smartconnect-center/

### Why this matters

This is an official cloud-side route that explicitly supports Optima 270, and it already exposes much of the data a smart-home hub would want. It may offer a better-supported integration path than independently recreating the Genvex Connect mobile app's Nabto client.

However, no public API, developer access, OAuth flow, or third-party integration documentation has been found. The fact that the professional dashboard can access data does not imply that its backend API is available or licensed for a third-party HA integration.

For the commercial plug-and-play product, a partner/API arrangement with LS Control or Genvex could be a more sustainable route. It might also enable additional historical data and alarm/event history beyond the consumer app.

## Important Nabto authentication correction

The current public Cordova Nabto plugin documentation says the legacy `createSignedKeyPair(email, password)`, `signup`, and `resetAccountPassword` operations are deprecated. Nabto says its CA services are no longer part of the standard platform and require customer-specific setup. New Nabto solutions should use PPKA or the basestation authentication-token approach (`setBaseStationAuthJson`), subject to device/basestation configuration.

Source: https://github.com/nabto/cordova-plugin-nabto

At the same time, Nabto's LS Control partner page still describes the LS Control architecture as using Nabto CA-based authentication integrated with LS Control's custom identity management:
https://www.nabto.com/partners/ls-control/

This means we must **not** assume that the current Genvex app simply calls the generic legacy `createSignedKeyPair(email,password)` function. The public docs describe a historical architecture and a deprecated generic mechanism; LS Control may have a customer-specific CA service, a modified flow, or another identity arrangement.

## Official legacy SDK availability

Nabto's own `nabto-cli` repository explicitly says the Nabto 4/Micro Client SDK libraries are not included and must be requested from Nabto support. The CLI expects a native `libnabto_client_api.so` plus headers. The public README describes Linux generically but does not publish an ARM64 build matrix.

Source: https://github.com/nabto/nabto-cli

The SDK is therefore not something we can responsibly bundle from the public repository today. We need Nabto to confirm:
- whether the legacy client library is available for Linux aarch64;
- whether a build for Raspberry Pi 4 / 64-bit Linux can be supplied;
- whether redistribution in a commercial Home Assistant appliance is permitted;
- which SDK release and security/authentication mechanisms LS Control currently supports.

## Updated route comparison

| Route | Advantages | Unknowns / constraints |
|---|---|---|
| Nabto 4/Micro direct RPC client | Closest to the mobile app's known communication stack; P2P/relay remote access | Current identity flow, Optima 270 RPC definitions, SDK ARM64 availability and redistribution |
| Smart Connect Center integration | Official Optima 270 cloud service; current/history data, alarms and remote settings | Professional account, no public API docs or third-party authorization found |
| Existing local UDP/Micro client | Working community route, no cloud dependency | Requires same LAN; not suitable for remote-only setup |
| TCP tunnel through Nabto | Could expose a TCP service if device endpoint supports/configures it | Existing Optima 270 UDP protocol is not transparently transported by a TCP tunnel |

## Recommended next step

Seek a technical/partner conversation with LS Control and Nabto, asking for the supported third-party route for a customer-owned Optima 270:
1. Is there an API or partner integration route to Smart Connect Center?
2. Does Genvex Connect 4.0.3 use Nabto 4/Micro, and what is the current account/device authentication flow?
3. Can an authorized third-party client use the existing Genvex device identity and RPC interface?
4. Can Nabto supply an ARM64 Linux legacy Client SDK and commercial redistribution terms?

Until these points are answered, keep all cloud work read-only and avoid guessing endpoints or credential flows.
