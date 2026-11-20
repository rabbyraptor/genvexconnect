# Optima 270 remote v2 — isolated polling implementation gate

**Date:** 2026-11-20. **Status:** source committed; new tests still require an observed PASS.

## Implemented (inert)

- `experimental/genvex_remote/v2_polling_state.py`: an injected, single-flight async reader for exactly `(20,21,22,23,26,18,19)`; one authorized read-only RPC45 callback per requested poll; bounded timeout, no retries.
- `V2SnapshotState`: all-or-nothing required five-sensor baseline, optional fan-duty pair; invalid optional range gives an empty fan pair without false zeroes. A failed required read clears the previous snapshot; late/stale/wrong-device documents are rejected.
- `experimental/genvex_remote/test_v2_polling_state.py`: eight offline test methods, including serialization, failure/recovery, unavailable/zero semantics, cancellation and input validation.
- The existing v2 parser, HTTP endpoint and Home Assistant projection remain prototypes. The currently installed App and five-sensor v1 runtime are **not** wired to v2 by these changes.

## Offline verification

On an up-to-date checkout of `remote-nabto-connection`:

```sh
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m compileall -q experimental/genvex_remote experimental/home_assistant
```

CI workflow `.github/workflows/remote-nabto-offline.yml` already discovers these tests on branch pushes. A green CI run has not yet been independently observed for this change.

## Next gates — do not skip

1. Confirm offline suite PASS both on CI and on isolated HAOS ARM64 Python with no real credentials. Inspect any failures before enabling networking.
2. Prepare separate, explicit v2 SDK subprocess adapter; validate response/stop/shutdown and ensure no writes or unverified addresses.
3. Run a single operator-authorized seven-address RPC45 on isolated HAOS/QEMU. Steam Deck success **does not** prove this path.
4. Wire a separate opt-in v2 state provider to an authenticated private App HTTP endpoint and test a full synthetic/real v2 App-to-HA bridge. Preserve stable five existing sensor unique IDs.
5. Perform bounded repeated-poll tests, failure/recovery, restart/shutdown cleanup, secret handling and network isolation before unattended deployment.
6. Validate fan-duty percentage semantics against official UI; do not label these RPM values.

No automatic production changes, vendor enrollment, new remote network action or credential migration should occur while completing offline gates.
