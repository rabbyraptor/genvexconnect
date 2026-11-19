# Genvex Nabto Runtime Test

This is an isolated test app for the Raspberry Pi 4 / Home Assistant OS ARM64 host.

## Version 0.2.0 — runtime and CLI inspection

The app:

- Runs natively as an ARM64 Home Assistant app.
- Includes the statically linked ARM64 QEMU x86-64 user-mode emulator.
- Uses the official Nabto 4 CLI v1.3.0 release and its bundled Nabto Client SDK 4.9.11 shared library.
- Supplies an x86-64 Ubuntu 24.04 userspace library tree.
- Reports the CLI ELF interpreter and shared-library dependencies captured at build time.
- Runs the Nabto CLI version command under QEMU.
- Runs the Nabto CLI `--help` command under QEMU so the available CLI operations can be reviewed.
- Writes the diagnostic output to the app log.

## What it does not do

- It does not request, store, or print Genvex credentials.
- It does not create a Nabto certificate or private key.
- It does not discover or contact a Genvex controller.
- It does not open a Nabto profile or session.
- It does not invoke RPCs or open tunnels.
- It does not change the existing Genvex integration.

The version and help checks are intended to verify that the CLI and its dynamic dependencies can be loaded and that the command parser runs under QEMU. They do not prove that remote networking, authentication, RPC, or tunnelling works.

## Expected result

The app log should contain:

```text
PASS: Nabto CLI/SDK version command completed
PASS: Nabto CLI help command completed
```

The help output should list the available CLI options. The ELF report should show the x86-64 interpreter and shared-library dependencies identified during the image build.

## Install the update

After updating the local app files, use Settings > Apps to check for updates/reload local apps, then rebuild/reinstall version 0.2.0 if prompted. Open the app log after starting it.

## Stop the test

Stop the app from Settings > Apps after inspecting the log. It is configured for manual startup and does not start automatically after a reboot.

## References

- Nabto CLI v1.3.0: https://github.com/nabto/nabto-cli/releases/tag/v1.3.0
- Nabto CLI README and documented operations: https://github.com/nabto/nabto-cli
- Nabto CLI build: https://github.com/nabto/nabto-cli/blob/master/.github/workflows/build.yml
- QEMU user-mode documentation: https://www.qemu.org/docs/master/user/main.html
- Home Assistant app Dockerfile guide: https://contributors.home-assistant.io/apps/guides/dockerfile/
