# Genvex Nabto Runtime Test

## Version 0.4.0 — experimental authenticated read-only batch through QEMU

**Status: built, started, and read-only five-sensor authenticated RPC 45 batch SUCCESSFULLY EXECUTED on the user's Raspberry Pi 4 HAOS on 2026-11-19.**

This release extends the previously working 0.3.0 isolated test app without changing the existing local Home Assistant integration:

- Retains the working x86_64 Nabto CLI/SDK 4.9.11, QEMU, and Ubuntu 24.04 sysroot.
- Adds a prebuilt x86_64 Python 3.12 runtime from an official Python Linux amd64 image; no foreign-architecture commands are needed to prepare the build stages.
- Runs an x86_64 Python `ctypes` smoke test through QEMU at image build time and when the diagnostic addon starts.
- Bundles [`probe_remote_batch.py`](probe_remote_batch.py), a **one-shot** authenticated, **read-only** RPC 45 batch, reading only the five source-documented Optima 270 datapoints (20,21,22,23,26).
- By design the addon does **not** automatically open any remote authenticated session, load secrets, or send RPC requests when started. Its idle diagnostic flow stays unchanged.
- The authenticated batch runs only after a deliberate manual invocation from the separate [Steam Deck orchestration script](../../scripts/run_haos_qemu_remote_batch_from_deck.sh). The orchestrator prompts for the previously configured account/device identifiers and local encrypted key passphrase; transports the existing encrypted key and public certificate over an authorized SSH session to a random temporary directory inside the isolated test container, passes the passphrase over stdin and cleans up the temporary profile on normal exit.
- The orchestrator requires the same previously verified SSH access with the ability to call `docker exec` on the HAOS host; it does not enable or configure SSH.

### Build/installation prerequisite

Update **the existing local addon directory** on the HAOS host with all five files from this directory (`config.yaml`, `Dockerfile`, `run.sh`, `DOCS.md`, `probe_remote_batch.py`). Rebuild/reinstall the addon from the local addon store, then start it manually. **Changing the GitHub files alone does not update the installed addon.** How the local addon directory is mounted and how rebuild is triggered depend on the user's existing HAOS/SSH setup; do not guess a host path. Check the addon log for:

```text
Genvex Nabto runtime test v0.4.0 starting
PASS: x86_64 Python runtime works under QEMU
```

A build failure means the x86_64 Python dependency set needs correction before any authenticated test. No existing HA integration or its local transport should be touched.

### Run after the addon is confirmed running

From the Steam Deck with the existing encrypted Nabto profile and existing key-based SSH to HAOS:

```bash
umask 077
RUNNER=$(mktemp /tmp/genvex-haos-batch.XXXXXX.sh) || exit 1
curl -fsSL 'https://raw.githubusercontent.com/rabbyraptor/genvexconnect/remote-nabto-connection/scripts/run_haos_qemu_remote_batch_from_deck.sh' -o "$RUNNER" || { rm -f "$RUNNER"; exit 1; }
bash "$RUNNER"
STATUS=$?
rm -f "$RUNNER"
echo "HAOS batch test exit status: $STATUS"
```

The script asks for: HAOS SSH target (user@host **without** `-p`), a **separate SSH port** (default `22222`; the user's current HAOS SSH forwarding uses this port), Nabto identity, Nabto device hostname, and the existing key passphrase. Port 22 is not assumed. The SSH account must have access to `docker exec` on the HAOS host; merely reaching an SSH terminal addon does not guarantee that permission. Do not commit or paste secrets into GitHub or public logs.

Expected success: x86_64 Python SDK startup=0, resources=0, profile session=0, query XML setup=0, RPC status=0, `Read-only batch decoded: 5/5`, clean SDK shutdown. **All these statuses were confirmed** in the user's live HAOS/QEMU batch output; 5/5 responses were decoded in 1,150 ms for the single RPC invocation.

**Safety caveats:** This is proprietary Nabto 4 SDK under emulation with legacy RSA-1024 credentials. Profile transfer via SSH is transient, but does leave sensitive encrypted key material briefly in the addon container's writable filesystem. The passphrase is transmitted via SSH over stdin and exists in both processes' memory. A hard crash or lost SSH connection may leave the temporary directory; remove any leftover `/tmp/genvex-haos-batch.*` folders from the isolated addon container before next tests, and do not expose debug output containing identity/hostname. SDK redistribution terms remain unresolved. Runtime stability, timeouts and subsequent reconnects remain untested.

---

This is an isolated test app for the Raspberry Pi 4 / Home Assistant OS ARM64 host.

## Version 0.3.0 — SDK API and local-network checks

The app:

- Runs natively as an ARM64 Home Assistant app.
- Uses host networking so the local Nabto discovery operation can access the physical LAN; the app exposes no listening ports and remains manual-start only.
- Includes the statically linked ARM64 QEMU x86-64 user-mode emulator.
- Uses the official Nabto 4 CLI v1.3.0 release and its bundled Nabto Client SDK 4.9.11 shared library.
- Supplies an x86-64 Ubuntu 24.04 userspace library tree.
- Reports the CLI ELF interpreter and shared-library dependencies captured at build time.
- Runs the CLI version command with an isolated temporary Nabto home directory.
- Calls the CLI certificate-list operation against that empty temporary home; certificate output is suppressed.
- Calls the CLI local-discovery operation with a 25-second timeout; all discovered device identifiers and raw output are suppressed.
- Removes the temporary test home and captured output when the app stops.

Important source-code clarification: the Nabto CLI calls `nabtoStartup()` and `nabtoInstallDefaultStaticResources()` in its common initialization path before processing `--version`, `--help`, `--certs` or `--discover`. Therefore, the successful 0.2.0 version/help checks already proved that this SDK startup path completed. Version 0.3.0 adds separate SDK API calls and a local-network discovery test.

## Safety and scope

- No Genvex credentials are requested, stored or printed.
- No certificate or private key is created.
- The test uses a fresh temporary home directory, so it does not inspect any existing Nabto user profiles or certificates.
- Certificate names/fingerprints and discovered device identifiers are never written to the app log.
- Local discovery is read-only and limited to the local network. Host networking is enabled because Home Assistant documents it as necessary for apps that must see real network interfaces or perform discovery protocols; this lowers the app's security rating, so it remains a manual diagnostic app.
- No remote hostname is contacted.
- No user profile/session is opened.
- No RPC, pairing, stream, tunnel or controller command is invoked.
- The existing Home Assistant Genvex integration is not changed.

The `--discover` CLI branch calls Nabto's local-device discovery API. This is a useful first test of QEMU-translated networking, but it does not prove remote connectivity, authentication, RPC or tunnelling.

## Expected result

The app log should show:

```text
PASS: Nabto SDK startup, static-resource installation and version API completed
PASS: Nabto certificate enumeration API completed
Nabto discovery process returned
```

Discovery may report zero output lines if no compatible Nabto device is found on the local network. The current upstream CLI implementation exits with status 0 after calling its discovery helper even if that helper reports failure, so a zero exit status alone is not proof that discovery succeeded. The output line count is recorded, but device identifiers and raw output are suppressed. A timeout or empty result is diagnostic information, not proof that remote connectivity is impossible.

## Install the update

Use Settings > Apps to reload/check local apps and install version 0.3.0. Start the app and inspect its log. If the Supervisor offers a rebuild option, rebuild the local app image after updating the files.

## Stop the test

Stop the app from Settings > Apps after inspecting the log. It is configured for manual startup and does not start automatically after a reboot.

## References

- Nabto CLI source and initialization flow: https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp
- Nabto CLI v1.3.0: https://github.com/nabto/nabto-cli/releases/tag/v1.3.0
- Nabto CLI README: https://github.com/nabto/nabto-cli
- Legacy Nabto API client application guide (TEN025): https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf
- QEMU user-mode documentation: https://www.qemu.org/docs/master/user/main.html
- Home Assistant app Dockerfile guide: https://contributors.home-assistant.io/apps/guides/dockerfile/
- Home Assistant app host networking and discovery guidance: https://contributors.home-assistant.io/apps/guides/hardware/

## Verified HAOS ARM64/QEMU five-sensor RPC 45 batch — 2026-11-19

**VERIFIED from the user's successful Raspberry Pi 4 HAOS terminal test**, orchestrated from Steam Deck through SSH on its explicitly configured port, into the running isolated test addon v0.4.0. The addon boot log independently showed `aarch64`, functioning QEMU x86_64, successful x86_64 Python ctypes import, and Nabto 4 Client SDK **4.9.11**. The temporary encrypted client profile was transferred for the test; the remote query was run with the bundled x86_64 Python probe under QEMU, **not native ARM64 code**.

- SDK startup **0**, static resources **0**, authenticated profile session **0**, reconstructed RPC interface XML registration **0**.
- Exactly **one read-only RPC ID 45** with ordered obj=0 addresses **20, 21, 22, 23, 26**, and trailer=1. RPC status **0**, elapsed **1,150 ms** for this invocation.
- Response decoded **5/5** signed 16-bit values in requested order:

| Sensor | Address | Raw int16 | Interpreted value |
| --- | ---: | ---: | ---: |
| Supply air | 20 | 367 | 6.70 °C |
| Outdoor air | 21 | 295 | -0.50 °C |
| Exhaust air | 22 | 313 | 1.30 °C |
| Extract air | 23 | 377 | 7.70 °C |
| Humidity | 26 | 65 | 65 % |

- Client session closed **0**, SDK shutdown **0**, SDK temporary profile cleaned, and orchestration reported success.

**Milestone:** real device telemetry from an authenticated proprietary Nabto 4/Micro gateway is now proven **from HAOS Raspberry Pi ARM64 via isolated x86_64 QEMU SDK runtime**. This is a single successful test run, **not** a supported native ARM64 SDK, a shipping Home Assistant integration, a latency benchmark, a long-running polling service, or verified writes. Batch response value order is strongly corroborated by the independently verified single-address measurements but is not accompanied by per-item response identifiers. The existing LAN UDP integration remained unchanged. Maintain credential protection and check the licensing/redistribution rights of the proprietary SDK before production distribution.

**Next safe engineering work:** establish restart/reconnect behavior, bounded polling and secret lifecycle in the isolated test runtime; then design a remote data-coordinator/transport adapter isolated from the working LAN integration. No write RPCs.

