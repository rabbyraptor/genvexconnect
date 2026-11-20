# Architectural decision: a real Home Assistant integration backed by an internal Nabto runtime

**Status: design approved as the target direction; not implemented or installed.** This document records the requested user experience and the engineering/security work remaining. See [resource catalogue](remote-nabto-resources.md), [verified experiments](remote-nabto-verified-facts.md), and [first five entity plan](remote-ha-entity-plan.md).

## Why did development move from an integration to an App?

It did **not** permanently move. The existing Home Assistant integration `genvex_connect` runs inside HA Core and uses a local-only Python Micro Nabto library. The vendor's official legacy Nabto 4 Client SDK that we got working is a Linux **x86_64** native binary; the user's HAOS is **aarch64** Raspberry Pi. Loading that binary into Home Assistant's aarch64 Python process is not possible. The test **App** is a Supervisor-managed isolated Docker container where `qemu-x86_64-static` runs the vendor's x86_64 SDK and an x86_64 Python probe. This enabled remote RPC 17 and RPC 45 **without breaking the working local integration**. It was a research/runtime component, not the envisioned final integration or its device/entities.

In the desired final product, **both components coexist**. QEMU is **user-mode translation, not a full virtual machine**. It need not technically run inside a separate Docker container, but keeping it in an isolated Supervisor App avoids loading incompatible x86_64 binaries in ARM64 HA Core and permits independent resource/process limits. No CPU/RAM measurements have yet been taken, so any claim of negligible overhead is unverified; runtime design should avoid starting a fresh QEMU interpreter or redundant sessions unnecessarily, use serial bounded polling and capture Pi 4 CPU/RSS metrics during soak tests.



```text
Home Assistant UI
  Settings → Devices & services → Add integration → Genvex Remote
      - device ID, email, account password (during enrollment only)
      - status/reconfigure/reauthenticate
            |
            v
  custom_components/genvex_remote (HA Core, native aarch64)
      - config flow + DataUpdateCoordinator
      - 5 sensor entities, device registry, availability
      - authenticated internal API client
            |
            v
  Genvex Nabto Runtime App (Supervisor-managed, ARM64 container)
      - private, persistent encrypted key and signed cert
      - automatic CSR/CA enrollment and renewal/repair lifecycle
      - isolated QEMU x86_64 legacy Nabto SDK
      - rate-limited, read-only serial polling of RPC 45
      - credential-free internal snapshots / health
            |
            v
  <12-digit-id>.remote.lscontrol.dk → authenticated legacy Nabto Micro gateway
```

No iPhone translation layer, no end-user SSH, no terminal or manual certificate copies.

## UI: recommended responsibility split

**Primary setup UI: Home Assistant integration Config Flow**, not command-line scripts. The user enters:

1. **Device ID** — exactly twelve ASCII digits; app derives `<id>.remote.lscontrol.dk`, no separate hostname field.
2. **Genvex/LS Control account email**.
3. **Account password** needed for legacy certificate registration. Mark confidential; **do not write in debug logs**, platform entities, URLs or published repository. Do not assume it is the local SDK key-encryption passphrase.
4. Optional readable status/retry on errors (invalid credentials, CA unavailable, certificate invalid/expired, Nabto unreachable, unsupported controller, runtime unavailable).

The integration requests a one-time **enrollment action** from the App over a constrained, authenticated internal channel. After success, the App returns only nonsecret status (never the key, its passphrase or the registration password). The HA integration then creates a **Genvex Remote** device and five independent sensor entities. Reconfigure/reauthenticate flows handle changed credentials and gateway. An App configuration screen under **Settings → Apps** may expose technical runtime state and advanced settings, but **should not be the primary onboarding flow**.

**Short-term interim possibility:** a Supervisor App `options`/`schema` UI can get user input without SSH, but Supervisor serializes options in `/data/options.json`; putting registration credentials into long-lived app options is an avoidable security risk. Prefer one-time enrollment via integration UI and delete/discard registration password after completion. If choosing an App UI for the prototype, validate ingress authentication, CSRF, secret non-retention and API privilege boundaries before implementation.

## Automated account-owned certificate provisioning (no transfer from Steam Deck)

The previous *manual* test demonstrated a successful HTTPS enrollment at `https://lscontrol.nabto.com/service/register` using `email`, `password` and a PEM CSR, with response status `0` and signed X.509 certificate. That establishes an *observed* registration mechanism, not a guaranteed supported public provisioning API.

Proposed App sequence:

1. Receive authorized enrollment request only from trusted HA UI/backend. Validate device ID and email; rate-limit registrations to avoid account lockouts and unwanted certificate issuance.
2. Inside the App's **private, persistent data volume**, create a new private key and CSR *on the HAOS device*. The tested legacy client path currently needs **RSA-1024**, which is cryptographically weak today. Before automating, confirm whether the CA/SDK supports any safer key size for this exact gateway. If it does not, explicitly communicate the compatibility/security tradeoff and keep the key highly protected. Never commit or transfer private keys.
3. Use **TLS certificate validation** for the known enrollment host; submit the enrollment fields once. Do not log or persist the login password, request body, full CSR/cert, or unredacted server errors.
4. Verify the returned cert is parseable, currently valid, corresponds to the generated key and chains to the **correct legacy Nabto CA**. The observed legacy chain requires compatibility handling; do not confuse this with normal public WebPKI TLS verification. Handle failure with cleanup and clear UI errors.
5. Protect the identity in the App's persistent private volume with restrictive ownership and modes. The proven SDK expects files in `users/<email-with-@-replaced-by-_at_>.crt/.key`. Keep the private key encrypted if the SDK can unlock the chosen supported encryption format. A randomly generated local passphrase must itself be stored in a restricted secret store or equivalent private App state for restart automation; never require a person to type it on every polling run. Do not claim true at-rest protection from a compromise of the host when the same system stores the unlock secret.
6. Establish authenticated SDK session; perform one known **read-only** RPC 45 five-item batch as final verification. On failure keep prior working cert safe and report recoverable error. Never silently overwrite a working credential set.
7. Record issue/expiry metadata only (not key material) for UI status; support controlled re-enrollment at or before expiry, rotation, explicit reauthentication, and full removal during integration uninstall. Verify CA behavior for repeated enrollment, quota and invalidation before making automatic renewal promises.

**Hard design gate:** understand SDK/CA registration rules and licensing, key format and expiration handling before enabling unattended issuance. The old RSA-1024 protocol is a compatibility constraint, not a secure modern design endorsement.

## Automatic polling and failure semantics

- One worker owns the SDK session. No two RPC operations overlap. Start with **one five-address read-only RPC 45 every ~60 s**, subject to timeout/backoff; performance/uptime not guaranteed by three observed successful batches.
- Strict decoded schema: five signed int16 in order 20,21,22,23,26; **reject whole snapshot if any missing/invalid**. Use `experimental/genvex_remote/sensor_model.py` as the shared specification, restructured when packaging.
- Publish only `{schema_version, device_id, timestamp_utc, values, health}` over an **authenticated, nonpublic** backend interface. Avoid HTTP listening on all interfaces by default. Document internal app→HA isolation, network topology and permission model; don't assume localhost is shared by the two containers.
- HA coordinator rejects stale (> configurable maximum) and mismatched-device snapshots and reports *unavailable* on errors. No indefinite stale values masquerading as live data.
- Device registry identifier tied to domain and 12-digit ID; five entity keys with units/classes/state measurement. No write, button, number, climate or switch entities in v1.
- HAOS reboot, App restart, disconnect/reconnect, CA/server errors, temp cleanup and private data persistence must be tested before declaring production ready.

## Work breakdown (incremental, independently testable)

**Phase A — certificate enrollment prototype**: **STARTED, OFFLINE-ONLY**. The source is now at [enrollment_core.py](../experimental/genvex_remote/enrollment_core.py) with [fake-CA unit tests](../experimental/genvex_remote/test_enrollment_core.py). It generates a candidate RSA-1024 private key and signed CSR, exports encrypted PKCS#8, validates the observed legacy CA response envelope, rejects mismatched/expired certificates and sanitizes failure messages. Six corresponding unit tests passed in the local development runtime (cryptography 46.0.4). **No real registration request was sent; the source has no network calls and does not modify /data or the running HAOS App.** Before live usage, implement and verify authentic legacy CA trust-chain validation, exact SDK-compatible encrypted-key format, safe atomic rotation and private persistent storage, controlled account-owned CA HTTP enrollment and secret handling. A fake test certificate is not a trusted CA response. Then test approved real enrollment through the future UI.

**Phase B — unattended runtime:** read-only polling worker with deterministic JSON snapshot, internal authentication, bounded execution, graceful shutdown and credential lifecycle. Validate standalone on HAOS. No terminal required after initial App install.

**Phase C — real `genvex_remote` integration:** config flow, runtime discovery/setup, enrollment/reauth, DataUpdateCoordinator, five device-linked sensors, no external account password retained following enrollment.

**Phase D — UX and release:** UI test on HAOS, device dashboard, availability/history, safe uninstall/cleanup; inspect licensing before SDK redistribution.

## Explicit non-goals

- No changes to `custom_components/genvex_connect` existing LAN paths.
- No user-managed manual cert copy, CLI login or SSH for routine setup.
- No iPhone traffic interception, iPhone translator, vendor webview or VPN.
- No unverified write RPCs or remote control in first release.
- Do not describe the prototype as installed, dashboard-ready or fully secure until implemented and tested.

## Official UI development references

- [Integrations versus Apps](https://www.home-assistant.io/docs/apps-and-integrations/)
- [Config flows](https://contributors.home-assistant.io/core/integrations/config-flow/)
- [Config entries](https://contributors.home-assistant.io/core/integrations/config-entries/)
- [App configuration/options](https://contributors.home-assistant.io/apps/reference/configuration/)
- [App options](https://contributors.home-assistant.io/apps/guides/options/)
- [App ingress UI](https://contributors.home-assistant.io/apps/guides/ingress/)
