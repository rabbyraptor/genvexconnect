# DEV3 reversible HAOS deployment gate — design only

**Status (2026-11-21):** no persistent deployment approved or performed.
The physical Optima 270 -> one legacy Micro Nabto RPC45 -> authenticated
private Docker HTTP -> actual Home Assistant reader, coordinator and five
sensor classes was confirmed by the operator on the real HAOS host.
The class test ran in a **separate ephemeral interpreter inside the Core
container**, not in the running Home Assistant process.

## Confirmed facts

- The DEV2 App has `boot: manual_only` and `host_network: false`; its
  production bootstrap requires an App-private encrypted client profile,
  a configured device identity, unlock secret and IPC bearer token.
- The candidate integration pins its runtime endpoint to the internal
  `local-genvex-nabto-remote` App hostname and port 18275; it does not
  collect Nabto unlock credentials.
- The real HA Core CI tests register five sensors and one device over
  actual TCP, verify fail-closed unavailable states for 401/503 and
  successful recovery, using synthetic snapshots.
- The actual HAOS one-shot tests use a **temporary Docker container** on
  the private `hassio` bridge with an ephemeral private address and
  one-shot HTTP server; they do not establish that the production App
  hostname resolves from the Core container or that its network is
  equivalent to the temporary bridge.

## Blocking production gates

1. **Networking and App name:** verify the installed App's *actual*
   Supervisor slug, container DNS hostname, private network reachability,
   and non-public exposure from Core. Do not assume the test container
   address or service DNS is identical to the App. No host-published port,
   broad wildcard endpoint or host networking should be added.
2. **Credential lifecycle:** design a private profile and token
   provisioning method that does not put the encrypted key, unlock
   passphrase or bearer token in command-line arguments, Docker inspect,
   shell history, logs, a Git repository, or unencrypted backups.
   Review the risk that Supervisor App options persist secrets, and
   decide how the Home Assistant config entry obtains the bearer token
   without revealing it in logs. Provide rotation and revocation.
3. **Runtime supervision:** verify startup, health/readiness, timeouts,
   bounded memory/CPU, DNS/UDP egress, QEMU architecture support, graceful
   stop, failed Nabto sessions, and unavailable state after expiry.
   Require a stable read-only polling loop, no remote writes, and a
   manual-only boot until separately approved.
4. **HA installation:** create a reviewed, version-pinned custom
   component package with an install manifest and a rollback plan.
   Verify no conflict with the existing working LAN Genvex integration,
   entity unique IDs, duplicate devices, reload, restart and uninstall.
   Back up before modifying the live `/config`.
5. **Operator consent:** obtain explicit approval for each of:
   installing the App, writing credentials to App-private storage,
   installing/enabling the custom component, and enabling unattended
   polling. Prior one-shot consent is not permission for these steps.

## Suggested staged acceptance sequence

- **Gate A — non-invasive preflight:** inspect App metadata and private
  Docker DNS/networking without reading or printing any credential.
  Only fixed PASS/BLOCKED diagnostics; no new SDK request.
- **Gate B — disposable fake-only integration:** use a temporary private
  test listener with synthetic data to verify that Core can reach the
  chosen Supervisor App network endpoint. No persistent Core changes.
- **Gate C — reviewed App credential provisioning:** user approves
  secure local entry, manual-only App launch and a bounded real read-only
  snapshot; never export secrets to the assistant.
- **Gate D — reversible HA integration install:** user approves backed-up
  and pinned component installation, one config entry and five entities;
  prove stable updates and unavailable/recovery on the live host.
- **Gate E — unattended operation:** separately approve polling
  interval, watchdogs, health checks, startup policy and rollback.

## Rollback invariants

- Leave the existing LAN integration untouched throughout.
- Do not enable automatic startup during the first live deployment.
- Stop and remove the experimental App before deleting its private
  profile; remove only the new remote config entry and component.
- Restore only the backed-up, explicitly identified files; never
  overwrite unrelated `/config` content.
- No production changes before the operator has inspected the
  exact commands and explicitly approved them.
