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


## Deeper Smart Connect Center capability findings (brochure)

The official Genvex brochure provides more concrete details than the product landing page:

- Trend history is retained for **two years**.
- Trend logging interval is **five minutes**.
- Graphs can be zoomed and exported; the brochure explicitly lists CSV export.
- The UI has separate tabs for Data, Graphs, Event log and Set Points.
- Event log filters include all events, alarms only, set-point changes and communication errors.
- Event entries include timestamp, event type, description, action, level and username.
- The current-data view includes temperatures, humidity, pressure, fan percentages and RPM, relay states, compressor state, bypass and error list.
- Set-point view includes heating/humidity controls, temperature settings, boost duration, fan-level settings, minimum-air-volume settings and frost protection.

Sources:
- https://www.genvex.com/download/18.6d7c19c518cfe26c3038363/1745309256723/Brochure-Smart-Connect-Center.pdf

This is a significant product insight: Smart Connect Center's five-minute, two-year history and CSV export could provide a strong baseline for the kind of user-facing energy/comfort/ventilation history we want to build. It is not proof that an API exists, but it gives us a precise list of valuable data to request through a supported integration.

## Deeper Nabto authentication implications

Nabto's TEN036 security document clarifies three distinct legacy Micro authentication models:

1. **CA-signed client certificates with user identity**: the client certificate carries a user identity (often email); the basestation validates the certificate and forwards the identity to the device, which applies its ACL. This requires a central identity-management service. Nabto explicitly says it no longer provides the generic CA user-management service, while customers can integrate their own service.
2. **PPKA (paired public key authentication)**: a client creates an RSA keypair and the device authorizes its public-key fingerprint. The standard pairing flow requires the client and device to be on the same LAN (or another trusted provisioning route) to register the key. Once paired, remote access is possible.
3. **Application-level authentication**: the Nabto connection itself can be anonymous, with application credentials/session tokens validated by the device. Nabto warns that this is a poor fit for RPC unless credentials are included and validated in each RPC call.

Sources:
- https://downloads.nabto.com/assets/docs/TEN036%20Security%20in%20Nabto%20Solutions.pdf
- https://www.nabto.com/pairing-and-access-control-part-1-intro-and-device/

### Consequences for this Genvex investigation

- PPKA is not a shortcut that lets us connect to an arbitrary Genvex unit: the unit must already support the relevant ACL/pairing mechanism and our client public-key fingerprint must be authorized.
- The user's existing Genvex Connect account may be backed by a vendor-managed identity flow, but public evidence does not reveal the exact mechanism used by app v4.0.3.
- We must not derive or guess a Nabto password from the Genvex Connect password, and must not try undocumented credential endpoints.
- A supported third-party path likely requires LS Control to authorize an additional client identity, provide an API/SDK contract, or offer a Smart Connect Center integration.

## Nabto platform lifecycle

Nabto's current documentation says Nabto Edge is superseding Nabto Micro for new remote-control solutions. Nabto Micro remains supported for existing customers, but Edge and Micro are incompatible and cannot be substituted transparently. Micro uses its own static-interface RPC protocol; Edge uses CoAP and a different identity/device model.

Source:
- https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html

This reinforces the need to treat the Genvex integration as a compatibility client for an existing deployed Micro fleet—not to migrate the ventilation controller to Edge.

## Revised feasibility assessment

The Smart Connect Center route is now the strongest **commercially sustainable** candidate if LS Control will grant partner access. It has the clearest documented data model and historical value. The direct Nabto Micro route remains the strongest **technical reverse-integration candidate**, but the authentication and client SDK are gated by LS Control/Nabto cooperation.

No code has been added for cloud login or remote RPC: without a verified auth contract and a supported SDK binary for the target architecture, doing so would create fragile and potentially unsafe credential handling.


## Client SDK architecture: what is and is not confirmed

The public Nabto 4/Micro CLI documentation does not publish an architecture matrix for the legacy proprietary Client SDK. It only documents a Linux shared object (`libnabto_client_api.so`) and says the SDK must be obtained from Nabto support. Therefore, Linux ARM64/Raspberry Pi support remains **unconfirmed**, not disproven.

Do not confuse this with the current Nabto Edge SDK: its public embedded repository documents Linux targets including `linux_aarch64`, but Edge is incompatible with Micro and cannot connect to an existing Genvex Micro device merely because both products are made by Nabto.

Sources:
- https://github.com/nabto/nabto-cli
- https://github.com/nabto/nabto-embedded-sdk
- https://www.nabto.com/docs/developer/guides/overview/edge-vs-micro.html

For an HAOS appliance, the supported implementation choices remain:
- a legacy Micro Client SDK binary supplied by Nabto for the appliance architecture, if available and licensed for redistribution;
- an officially supported Smart Connect Center/API integration;
- or, only if the user accepts an externally hosted component, a separately maintained service on an architecture supported by the legacy SDK. This last option would introduce an operational dependency and is not the preferred plug-and-play design.

No evidence currently supports using the public Edge ARM64 library as a substitute for the Micro client library.


## New route: EU Data Act data-access and third-party sharing

Genvex now publishes a dedicated EU Data Act page for Smart Connect Center. It explicitly states that the service records and processes data related to product use and operation, and that Smart Connect Center customers may request access to data under the Data Act. Genvex directs customers to contact its team to ask questions or submit a data-access request. The page links to a myUplink-hosted Smart Connect Center information notice.

Sources:
- https://www.genvex.com/om-genvex/dataforordningen-eu-data-act
- https://myuplink.com/legal/eu-data-act-information-notice/da
- https://www.genvex.com/en/about-genvex/eu-data-act

The Data Act provides two potentially relevant routes:
- Article 4: where data cannot be directly accessed by the user, the data holder must make readily available product and related-service data, with relevant metadata, accessible to the user under the conditions in the Regulation.
- Article 5: on the user's request, the data holder must make readily available data and relevant metadata available to a third party chosen by the user, under the conditions in the Regulation.

Official legal source:
- https://eur-lex.europa.eu/eli/reg/2023/2854/oj/eng/pdf

The European Commission's explainer clarifies that users include natural or legal persons who own, rent or lease a connected product, and that third-party sharing can be requested by the user. The Danish Agency for Digital Government (Digitaliseringsstyrelsen) confirms it is Denmark's competent authority and that consumers can have rights to access data generated by their connected products:
- https://digital-strategy.ec.europa.eu/en/factpages/data-act-explained
- https://digst.dk/tilsyn/dataforordningen/

### Important scope and timing caveats

This is a promising lawful access route, **not proof that Genvex already offers an API** or that every historical record and every derived metric must be provided. The scope depends on what qualifies as readily available product/related-service data, the applicable contracts, the user's role, personal-data rules and the technical feasibility/conditions in the Regulation.

The Data Act generally applies from 12 September 2025. Article 3(1)'s design obligation for direct access applies only to connected products and related services placed on the market after 12 September 2026. That later date does not erase the separate user-access and third-party-sharing provisions in Articles 4 and 5, but it is important not to overstate the design obligation for an older installed Optima 270.

Genvex's page specifically describes rights for customers using Smart Connect Center as a related service. The user's current use of Genvex Connect should therefore not be conflated with having a Smart Connect Center subscription. We should ask Genvex to clarify:
1. Whether the ECO 360 R H / Optima 270 installation's product data can be requested under Articles 4 and 5 even if the customer currently uses Genvex Connect rather than Smart Connect Center.
2. Whether Genvex treats Smart Connect Center as a related service for this specific installed system, and whether a Smart Connect Center subscription/account is required for the relevant service data.
3. Whether the data can be shared directly with a nominated third-party recipient (our Home Assistant integration) through a documented API, secure data export, or recurring machine-readable feed.
4. Which fields, sampling intervals, historical retention, formats and metadata are available.
5. Whether there are any reasonable third-party compensation, security, privacy or technical conditions.

### Practical impact for this installation

The Genvex Smart Connect Center product page says Optima 270 systems connect via LAN cable. The user's summer-house network bridge already provides an Ethernet path to the ventilation unit, based on the current setup discussion. This may satisfy the network-connectivity prerequisite, but does not prove the unit is registered or enabled for Smart Connect Center. Do not change controller settings or assume that Genvex Connect registration automatically provisions Smart Connect Center.

### Recommended order of work

1. First make a written data-access / third-party-sharing request to Genvex, naming the exact unit (ECO 360 R H with Optima 270) and asking for a documented, supported machine-readable route.
2. In parallel, ask whether the same installation can be activated in Smart Connect Center and whether that service exposes the requested data to an authorised third party.
3. Only if Genvex cannot provide an appropriate data-sharing route should we return to the Nabto Micro client/SDK investigation as the main route.

This route may materially reduce implementation and maintenance costs for a commercial Home Assistant appliance, while keeping the integration within an officially supported data-sharing arrangement. It does not remove the need for technical validation or a clear commercial agreement if the integration is later distributed to other customers.
