# Genvex Nabto Runtime Test

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
