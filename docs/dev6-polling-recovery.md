# DEV6 — polling-loop recovery (source-only gate)

**Base:** the existing DEV5 source-parity draft branch (`dev4-source-parity-onboarding-20261122`).

## Failure addressed

The periodic read scheduler previously invoked `SnapshotState.refresh()` without
an outer exception guard. Ordinary SDK failures are already converted to a
`False` result by `SnapshotState`, but an unexpected internal exception could
terminate the background polling task permanently, leaving the private HTTP
server running without further RPC45 attempts.

The scheduler now invalidates the cached snapshot and reports a failed cycle
when an unexpected ordinary exception escapes, then continues at the next
scheduled interval. Cancellation still propagates to shutdown. No exception
message, credentials, or raw SDK response is printed.

## Package version and source attestation

This branch advances the App manifest and ARM64 CI build tag to
`0.1.0-dev6`. The historical DEV5 post-install verifier remains pinned to
the exact installed DEV5 blobs; a DEV6 checkout must fail the old DEV5
full-source attestation. Eighteen unchanged DEV5 source files are still
checked against the original fingerprints in the offline regression suite.
The DEV5 upgrade and rollback scripts remain historical, not DEV6 installers.

## Offline gate

```sh
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py' -v
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m compileall -q genvex-nabto-remote/runtime experimental/genvex_remote
```

The `test_unexpected_refresh_exception_recovers_without_leaking` regression
test uses a synthetic state that fails once and succeeds on its next call;
it checks continued task life, fail-closed invalidation and no leaked details.
The mirrored source modules must stay byte-identical.

## Live acceptance gate (not executed here)

After review/merge and a separately approved DEV6 deployment, verify with
MCP and HAOS that the App remains running, five-value schema v1 snapshots
continue after simulated failures, the worker is re-used or recycled as
expected, and the HA Data age entity follows its configured grace policy.
This PR neither performs a live write nor enables additional sensors.
