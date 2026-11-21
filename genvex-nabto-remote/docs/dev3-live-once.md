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
6. First confirm the status-only probe still succeeds. Then run once with
   `--show-values` to compare the five validated values to Genvex Connect.

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
It validates the existing App-private profile and the three root-owned staged
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

The operator must use a reviewed/pinned copy of all three scripts staged in
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

## Opt-in five-value comparison

The operator launcher now accepts a single, non-secret display switch:
`python3 /tmp/genvex-dev3-once/haos_live_once_operator.py --show-values`.
No display switch is needed for the established status-only smoke test.

This does not create a daemon, enable polling, or change the App config.
The switch is forwarded only as a literal Docker argv option and the three
credentials are still collected via hidden interactive stdin. The output is
generated **only after** the complete snapshot passes device ID, freshness,
five-key and finite numeric validation. It prints a fixed block:

```text
PASS: one read-only RPC45 snapshot validated
READINGS_BEGIN
VALUE supply_air: <number> °C
VALUE outdoor_air: <number> °C
VALUE exhaust_air: <number> °C
VALUE extract_air: <number> °C
VALUE humidity: <number> %
READINGS_END
```

No device identifier, Nabto endpoint, identity, passphrase, certificate, raw
response or diagnostic text is printed. Values are rounded to one decimal
for temperatures and a whole percent for humidity. The display is for
manual comparison, **not** a sensor-plausibility or calibration verdict.

To validate, make one read and record its time, then compare against the
Genvex Connect app within a short interval. Check these mappings:
- `supply_air`: supply / indblæsning (address 20)
- `outdoor_air`: outdoor / udeluft (address 21)
- `exhaust_air`: exhaust / afkast (address 22)
- `extract_air`: extract / udsugning (address 23)
- `humidity`: relative humidity / luftfugtighed (address 26)

Only the five numerical values and app comparison readings are needed for
review; no identity or account information should be sent. Differences may
reflect timing or vendor display rounding and require investigation before
enabling persistent polling. The first success proves the transport and
schema, **not** the exact agreement of displayed values.
