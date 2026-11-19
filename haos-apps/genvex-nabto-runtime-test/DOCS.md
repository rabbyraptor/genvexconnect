# Genvex Nabto Runtime Test

This is an isolated, temporary architecture test for the Raspberry Pi 4 / Home Assistant OS ARM64 host.

## What it does

- Builds an ARM64 Home Assistant app.
- Includes the statically linked ARM64 QEMU x86-64 user-mode emulator.
- Downloads the official Nabto 4 CLI v1.3.0 release and its bundled Nabto Client SDK 4.9.11 shared library.
- Supplies an x86-64 Ubuntu 24.04 userspace library tree.
- Runs the Nabto CLI version command under QEMU.
- Writes the result to the app log.

## What it does not do

- It does not request or store Genvex credentials.
- It does not discover or contact a Genvex controller.
- It does not create a Nabto profile or session.
- It does not invoke RPCs or open tunnels.
- It does not change the existing Genvex integration.

## Expected result

A successful test includes a log entry similar to:

```text
PASS: official Nabto CLI started successfully under QEMU
```

A failure is still useful: the app log and Docker build output should identify whether the problem is the artifact download, ELF architecture check, missing interpreter/library, or QEMU execution.

## Stop the test

After inspecting the log, stop the app from Settings > Apps. It is configured for manual startup and does not start automatically after a reboot.

## References

- Nabto CLI v1.3.0: https://github.com/nabto/nabto-cli/releases/tag/v1.3.0
- Nabto CLI build: https://github.com/nabto/nabto-cli/blob/master/.github/workflows/build.yml
- QEMU user-mode documentation: https://www.qemu.org/docs/master/user/main.html
- Home Assistant app Dockerfile guide: https://contributors.home-assistant.io/apps/guides/dockerfile/
