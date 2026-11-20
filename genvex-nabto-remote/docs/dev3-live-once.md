# DEV3 single-shot RPC45 gate (experimental)

This branch adds `runtime/live_once.py`, an **operator-invoked** read-only
one-shot probe. It is deliberately **not** connected to `run.sh` or to the
Supervisor App options. The installed DEV2 remains stopped and untouched.

## Offline checks

From `genvex-nabto-remote/`:

```sh
python3 -m unittest discover -s tests -p 'test_live_once.py' -v
python3 -m compileall -q runtime
```

No Nabto network requests are made by these unit tests. The single-read test
mocks the SDK adapter.

## Before any live execution

1. Review the branch and run the offline tests in the intended build environment.
2. Confirm the App is stopped, manual-boot and isolated, with no host networking.
3. Keep the original profile untouched; the imported `/data/profile` must
   remain private (directory 0700; both PEM files 0600).
4. Review a separate, operator-controlled execution method for passing settings
   via stdin. Do **not** pass credentials in command-line arguments, environment,
   Supervisor options, shell history, logs or repository files.
5. Do not enable continuous polling as a substitute for a one-shot test.
6. Verify the output against known Genvex Connect readings. This first version
   reports validation status only; it does not expose values.

## Important limitations

- This is not a production-ready ARM64-native Micro Nabto implementation.
  The adapter still uses the x86_64 SDK through QEMU.
- No separate DEV3 image or Supervisor App version has been built or deployed.
- A successful SDK call does not by itself prove long-running reliability.
- The runner fails closed on malformed input or invalid snapshot and emits no
  credentials or raw SDK output.

## Isolated HAOS execution (operator gate, no App deployment)

The reviewed `scripts/haos_live_once_operator.py` can launch **one disposable**
Docker container using the already installed DEV2 image, without starting the
Supervisor-managed DEV2 App. It first checks that DEV2 is stopped, manual boot,
diagnostic flag remains true and all Supervisor credential options are empty.
It validates the existing App-private profile and the two root-owned staged
scripts. If these prerequisites fail, it makes **no** Nabto connection.

The launcher prompts for device ID, identity and key unlock secret via an SSH
TTY (getpass), constructs a single JSON input line in memory, and supplies it
to the container via stdin only. The image ID is obtained from the uniquely matching, locally installed Docker
image tagged `0.1.0-dev2` and revalidated against the ARM64 App/version labels.
A stopped Supervisor container is optional. If no matching image or multiple
matching images exist, the launcher **fails closed**.

The disposable container runs `live_once.py` as its entrypoint, with:
- Read-only root filesystem and read-only profile and script bind mounts.
- `--network bridge` (not host network), all Linux capabilities dropped,
  no-new-privileges, and PID/memory limits.
- Docker log driver disabled; ephemeral writable tmpfs for SDK session files.
- Maximum 110 seconds wall-clock, with a force-remove cleanup attempt even
  on timeout.

The operator must use a reviewed/pinned copy of the two scripts staged in
a root-owned 0700 directory, with each file mode 0600. The launcher does not
send credentials to Supervisor options, pass them as command-line arguments or
persist them to disk. It never runs the App's normal polling startup.

**Important limitations:** the separate Docker process is still root inside
its container, the x86_64 SDK executes through QEMU, and the temporary
container needs outbound network access to the remote endpoint. This is an
experimental supervised live probe, **not** a production integration.

After the offline regression tests pass, use the approved operator procedure
to stage the scripts and run the interactive one-shot test. Do not paste
credentials into chat or into commands.

## Safe failure classification (after first blocked live read)

The first real isolated run reached the container but returned the generic blocked
message. The runner now emits only allowlisted stage codes such as
`PROFILE_INVALID`, `SDK_STARTUP_FAILED`, `SDK_SESSION_FAILED`,
`SDK_RPC45_FAILED` and `SDK_RESPONSE_INVALID`; it never copies raw stdout,
SDK diagnostics, identifiers or secrets to the host output.

The host operator must stage **three** private 0600 scripts from the same
reviewed commit: `live_once.py`, `sdk_snapshot_adapter.py`, and
`scripts/haos_live_once_operator.py`. The two runtime scripts are mounted
read-only over their installed DEV2 image equivalents. The installation,
Supervisor options and original profile remain unchanged.
