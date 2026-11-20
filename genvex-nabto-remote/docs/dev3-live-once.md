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
