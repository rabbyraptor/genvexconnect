# DEV3 polling and Home Assistant availability review

Status: **source-only, not deployed**. Keep the existing LAN integration
untouched; the installed Genvex Remote DEV2 App remains stopped.

## Confirmed live transport and mapping

One isolated HAOS/QEMU Nabto Micro RPC45 batch returned a valid five-value
snapshot. The operator compared it with the official Genvex Connect application:
four temperatures differed by 0.1-0.2 °C and humidity agreed exactly.
This corroborates the five known addresses (20/21/22/23/26) and conversions,
but one matching batch does not establish reliability under periodic load.

## Proposed runtime behavior

The existing runtime already implements serial, read-only polls, a 60..3600
second App configuration interval, a snapshot API requiring bearer auth, and
an 85-second single-read SDK timeout. It does not run until separately enabled.

The DEV3 snapshot-state change strengthens this contract:

- A successful five-value batch is projected into an owned, validated copy.
  Mutating the SDK's returned object after validation cannot change published
  readings.
- During an in-flight poll, the last known good result may remain available
  **only while its age is at most 180 seconds**. This avoids an unnecessary
  unavailable blip during normal slow reads.
- A failed read invalidates the entire five-value batch immediately; no
  partial readings or lingering old-success state.
- Cancellation or explicit stop invalidates the snapshot.
- A completed successful read replaces the old values atomically. Later
  successes may recover all five sensors.
- PollingService performs one read at a time and waits its configured interval
  after each completed attempt. No catch-up burst or concurrent RPC calls.

The Home Assistant `GenvexRemoteCoordinator` fetches one authenticated
snapshot every 60 seconds, rejects stale, invalid or wrong-device snapshots
and raises `UpdateFailed` for expected fetch/validation failures.
`CoordinatorEntity` then supplies the standard HA unavailable behavior.
The existing HA integration is a **scaffold**, not a verified installation.

## Offline regression tests

```sh
# From genvex-nabto-remote/
python3 -m compileall -q runtime ../experimental/home_assistant/custom_components/genvex_remote
python3 -m unittest discover -s tests -p 'test_*live_once*.py' -v
python3 -m unittest discover -s tests -p 'test_dev3_polling_state.py' -v
python3 -m unittest discover -s ../experimental/home_assistant/tests -p 'test_dev3_coordinator.py' -v
```

The new state tests cover copies, failure invalidation, recovery, stale expiry,
concurrent refresh serialization, in-flight values, cancellation and shutdown.
The HA coordinator tests use minimal API stubs and do **not** prove behavior
inside an installed HA Core version. Neither suite talks to the gateway.

## Gates before enabling a live polling service

1. Offline regression tests pass.
2. Review the bearer-token provisioning and private App DNS channel on HAOS,
   without exposing credentials in command lines, public ports or logs.
3. Build a separate DEV3 App image; keep DEV2 stopped/manual and preserve LAN.
4. Stage a strictly bounded, operator-approved multi-poll trial (few attempts,
   no writes); capture success/failure timing without credentials.
5. Confirm HA coordinator failures mark the five entities unavailable on
   a supported Home Assistant version, and recovery restores all five.
6. Only then consider persistent App startup and automatic restart policy.

No production installation or unattended periodic polling is authorized by
this branch.

## Explicit bounded reliability trial (not continuous polling)

For an operator-approved HAOS field test, the staged
`haos_live_once_operator.py` supports `--trial-three`. This **never** starts
the Supervisor-managed App or a background polling service. It prompts once
for the private credentials and attempts exactly three independent,
read-only RPC45 batches using the same read-only isolated Docker profile.
There are 60 seconds **after each completed attempt** before the next starts
(no catch-up bursts, zero hidden retries). Each attempt has the existing
110-second Docker CLI deadline and per-attempt force-remove cleanup.

- Before *every* attempt, the launcher verifies the DEV2 App is stopped/manual,
  confirms empty credential options, and rechecks the pinned image and
  private profile permissions. If any gate changes, the trial aborts.
- An individual failed attempt is counted; it does not trigger an immediate
  retry. The trial continues to the next scheduled attempt (unless interrupted
  or preflight fails).
- The only extra host output is numbered PASS/FAILED attempts and the aggregate
  `TRIAL SUMMARY: n/3 validated`. No raw SDK output, identity, ID or values
  are recorded.
- Abort immediately with Ctrl-C; no daemon continues running.
- All three successes are required for an exit status of zero. Intermittent
  failures are evidence for further SDK/session recovery work, not grounds for
  enabling persistent App polling.

The trial takes several minutes, must be run interactively by the authorized
operator, and is **not** started by installing or importing the module.

## Optional sanitized SDK diagnostics

The last three-attempt field trial validated two RPC45 reads and returned
`SDK_RPC45_FAILED` for the third. The generic category cannot distinguish
a transient Nabto RPC status from a long-running request. The new
`--trial-diagnose` operator mode retains the same **exactly three** isolated
read-only attempts and 60-second spacing, but forwards `--diagnose` into
the one-shot container.

On a failed SDK RPC the adapter extracts only the exact integer markers
`Batch RPC status:` and `RPC elapsed_ms:` from the bounded SDK stdout.
It prints:

```text
BLOCKED: SDK_RPC45_FAILED
DIAG RPC45_STATUS: <integer or unknown>
DIAG RPC45_ELAPSED_MS: <integer or unknown>
```

No raw SDK output, host, identity, device ID, certificate, URL, JSON
diagnostic or unlock secret is exposed. Invalid, duplicate, negative or
out-of-range markers are rendered as `unknown`. On a success the normal
one-shot PASS marker is printed, without extra diagnostics.

This is a diagnostic experiment, **not a workaround**: it does not alter
SDK timeouts, retry logic, credentials, QEMU architecture, gateway requests
or persistent service behavior. `--diagnose` is also available for a
single isolated read, but an intermittent failure may not reproduce.
Only stage/status/timing markers should be shared.

## Second field trial: SDK status 26

Operator-reported `--trial-diagnose` yielded PASS / FAIL / PASS. The
failed second read returned `SDK_RPC45_FAILED`, native SDK status **26**,
and an RPC invocation duration of **14291 ms**. This is **not** the adapter's
85-second timeout, and a subsequent independent invocation succeeded.
There is not enough evidence to assign a specific Nabto meaning to 26:
no authoritative legacy SDK error-code mapping has yet been verified.
Do not equate 26 with a particular network, authorization or gateway cause.

Two consecutive three-attempt trials each succeeded twice, with failures
at different positions. This is evidence of intermittent RPC-level failure,
not a reliable estimate of long-run success probability. Do not start the
persistent App or infer that increasing the 85-second timeout will help.

Next investigation should inspect legacy SDK error-code definitions and the
numeric event codes already emitted by `classify_error()` in the isolated
probe, while continuing to suppress raw SDK diagnostic JSON and secrets.
Any additional live test needs explicit operator approval.

## Legacy Nabto error-code source and redacted events

Nabto's legacy TEN025 (Writing a Nabto API Client Application, appendix 7)
lists **diagnostic event** `1000026 = CONNECT_TIMEOUT`, as well as
`1000009 = CONNECTION_ERROR`, `1000021 = MICROSERVER_BUSY`, and other
million-range codes. These are **not** the same namespace as the observed
`nabtoRpcInvoke()` API return status **26**. The numeric coincidence must
not be used to conclude that SDK status 26 means CONNECT_TIMEOUT. TEN025
also directs readers to the `nabto_client_api.h` API status enum for
function return codes; the matching installed legacy header has not been
verified.

The existing isolated probe already reduces any vendor diagnostic JSON to
`('ERROR_JSON', [bounded integer event codes])` or
`('NO_JSON_DIAGNOSTIC', [])`. DEV3 now extracts that *redacted* marker
with a bounded, non-executing literal parser, and can print
`DIAG RPC45_EVENTS: 1000026` (or `none`) only in opt-in
`--diagnose` / `--trial-diagnose` mode. The parser rejects duplicated
markers, duplicate/unsorted codes, non-integer values, oversized content
and malformed input. No raw JSON or diagnostic strings are propagated.

Reference: https://downloads.nabto.com/assets/docs/TEN025%20Writing%20a%20Nabto%20API%20client%20application.pdf

The next approved field trial may distinguish a transport-level
`CONNECT_TIMEOUT` event from an RPC failure without such an event.
Until then, SDK status 26 remains an **unmapped API return code**.

## Inert recovery-policy prototype (offline only)

`runtime/recovery_policy.py` introduces a narrowly scoped, explicit
`read_with_one_recovery(poll_once)` callable. It is **not connected** to
`live_once.py`, the HAOS App, `PollingService`, or Home Assistant.
It does not start a service, perform a live call on import, change the
installed SDK, or introduce polling.

Only the **exact** combination `SDK_RPC45_FAILED`, SDK return status
`26`, and redacted diagnostic events `(1000015,)` may trigger a
single retry. It waits **60 seconds**, then calls the injected reader
exactly once more; that reader must create a fresh disposable SDK session.
A second failure terminates immediately; there is no third request or
loop. Missing, conflicting, malformed or different diagnostics are
non-retriable. Cancellation stops work. No raw SDK exception, secret or
profile data is logged.

The policy is conservative and experimental, not a claim that these
codes are always transient. It has SDK-free regression tests for success,
missing/unrelated event codes, maximum attempts, delay and cancellation.
The current fail-closed snapshot/coordinator semantics are unchanged:
known failed reads invalidate published data; no stale values may
be represented as fresh. Any future integration into a real worker
requires a separate design review and field-test authorization.

## Manual recovery-only field-test candidate

The offline-tested recovery policy is now wired **only** to the explicit
`--recover-once` option of the disposable single-shot test runner and
the HAOS SSH operator. The normal one-shot, `--diagnose`,
`--show-values`, `--trial-three`, and `--trial-diagnose` modes retain
their prior behavior; there is no combined three-trial/recovery flag.

To run the operator's experiment after staging the *matching pinned*
`live_once.py`, `sdk_snapshot_adapter.py`, `recovery_policy.py`, and
`haos_live_once_operator.py` to the existing root-owned directory:

```sh
ssh -tt -p 22222 root@rabbyshome.duckdns.org \
  python3 /tmp/genvex-dev3-once/haos_live_once_operator.py --recover-once
```

The operator still checks the DEV2 App is stopped/manual, verifies the
exact local image and private profile, passes credentials via stdin, binds
the profile and staged code read-only, and deletes the disposable Docker
container on exit. The single-shot runner creates an entirely fresh
SDK/QEMU subprocess for each request.

There is **one initial RPC45 read and at most one conditional final
read**. Only `SDK_RPC45_FAILED` + return `26` + exact diagnostic
`(1000015,)` triggers a 60-second delay and one further attempt.
Other failures stop immediately. The ordinary container deadline is
still 110 seconds; only this opted-in recovery experiment has a
260-second host deadline, allowing two independently bounded 85-second
SDK calls and the 60-second cooldown. Ctrl-C aborts the experiment.
No raw diagnostics, credentials or values are shown by default.
No HAOS App or LAN integration is modified.

This is a **candidate**; despite passing SDK-free tests it has not yet
demonstrated a successful live recovery. Do not turn on unattended
polling until a separate reliability review.

## Offline recovery outcome observability

The operator's last opt-in live trial completed on the **first** RPC45
read, without exercising the recovery branch. To make a future trial
unambiguous, the one-shot runner now prints an allowlisted outcome only
when the exact eligible error actually triggers a conditional retry:

- `RECOVERY: eligible RPC45 event; waiting 60 seconds before final attempt`
  means the first read failed with the exact allowlisted signature.
- `RECOVERY_RESULT: SUCCESS` means the fresh final attempt returned a
  **complete, validated** snapshot; it is printed only after validation.
- `RECOVERY_RESULT: FAILED` means the second attempt failed, or its
  returned data failed validation. The normal `BLOCKED` marker follows.
- Neither result is printed after an ordinary first-attempt success or
  an ineligible failure. A user-initiated cancellation still aborts.

These markers do not contain any device identifiers, credentials,
SDK response text, sensor readings, or vendor diagnostic strings.
The API and runtime request counts remain unchanged, at most two
RPC45 calls under explicit `--recover-once`. This is verified by
offline tests only; successful on-device recovery is not yet proven.

## Process-based offline recovery verification

The single-shot runner now emits **RECOVERY_RESULT: SUCCESS** only after
the second snapshot has passed the same five-sensor validation, and
**RECOVERY_RESULT: FAILED** if a triggered second attempt fails or its
snapshot is invalid. Successful first attempts produce no recovery result
marker. The event that triggered the cooldown remains the exact
SDK status 26 plus event (1000015,). No SDK or host diagnostics are
printed in either outcome marker.

`tests/test_dev3_recovery_subprocess.py` exercises the *real adapter*
process creation and stdout parsing using only a local stub Python
executable. A synthetic first child emits SDK 26/event 1000015;
a second newly spawned child emits a valid five-sensor snapshot.
The regression verifies two distinct child PIDs, one 60-second logical
cooldown request, and one validated final snapshot. A second scenario
uses nonmatching event 1000026 and asserts only one child process and
zero cooldown calls. The cooldown function is stubbed for speed.
This remains an **offline simulation**, not a successful field retry.

No additional remote calls, HAOS App changes, credential storage or
continuous polling were introduced by these tests.

## Offline child-process safety fault injection

`tests/test_dev3_process_safety.py` now runs three local, SDK-free
subprocess fault-injection scenarios against the actual
`SDKSnapshotAdapter`:

1. A child which hangs after consuming stdin must terminate at the
   adapter's timeout and yield only `SDK_TIMEOUT`.
2. A child which produces more than the 32768-byte stdout cap must
   terminate and yield a redacted `SDK_PROCESS_FAILURE`.
3. Cancellation during an in-flight child must terminate the child,
   propagate `CancelledError` and release the single-flight lock.

These tests involve fake local processes only, not real Nabto calls.
They demonstrate bounded cleanup behavior at the Python adapter level,
but do not certify network reliability or native-QEMU termination on
every hardware/platform variant. The explicit manual recovery experiment
and all previous read-only constraints remain unchanged.

## Bounded recovery reliability experiment (manual only)

The HAOS SSH operator now also accepts
`--recovery-trial-three`, which is intentionally distinct from
`--trial-three` and `--trial-diagnose`. It performs exactly
**three isolated initial read attempts**, at least 60 seconds apart.
For each trial, and only when the first read fails with the exact
`SDK_RPC45_FAILED` + return 26 + `(1000015,)` event signature, the
existing recovery policy may issue **one additional** read after its
own 60-second cooldown. Therefore a complete operator invocation
can issue **at most six RPC45 reads** (three initial, three conditional),
all serialized, with no background scheduling or daemon.

Each complete trial is in a separate ephemeral Docker container, uses
the stopped DEV2 App image, mounts the existing encrypted profile
read-only and passes credentials only through stdin. After each trial
the container is forcibly removed. The existing preflight runs before
every trial; failures terminate or are counted, not bypassed. Ctrl-C
aborts the sequence. Recovery status markers distinguish whether an
eligible retry was taken and whether its final snapshot validated.
The normal trial modes and the single `--recover-once` mode are
unchanged.

This is explicitly a **manual field experiment**: it must not be
scheduled, wired into Home Assistant polling or triggered automatically.
The offline CI checks validate the operator's strict count and call
arguments, but do not establish live network reliability. No more
than three initial attempts and six total SDK RPC45 operations may
be performed by this command.


## Latest operator trial: session failures before RPC45

The operator ran the explicit \`--recovery-trial-three\` study. All three
separate initial attempts failed as \`SDK_SESSION_FAILED\`, so the summary
was **0/3**. There was no \`RECOVERY:\` marker: all failures occurred
at \`nabtoOpenSession\`, **before** the read-only RPC45 invocation.
The conservative recovery policy correctly performed **no** retries;
the earlier RPC45 status 26 / event 1000015 policy is unrelated to
this new, earlier-stage failure.

The cause cannot be inferred from the generic classification. In
particular, neither bad credentials nor a network outage has been
established. Prior successful sessions make broad claims of permanently
invalid profile data inappropriate.

The next **single-read** investigation uses existing manual
\`--diagnose\` mode, now extended to print \`DIAG SESSION_STATUS:
<number|unknown>\` only when the classified SDK error is
\`SDK_SESSION_FAILED\`. The stage marker \`Profile session: N\` is
already generated by the isolated Nabto probe; the adapter filters it
to a single bounded 0..100000 integer, rejecting duplicated, malformed,
oversized and non-UTF-8 output. No SDK diagnostic JSON, account,
device ID, key or password is surfaced. Nothing is retried on
session failure. The new status must be collected before assigning
a specific SDK failure mechanism or changing the recovery policy.

This discovery blocks unattended polling. Neither DEV2 nor the existing
LAN integration is modified.

## Five-entity HA availability lifecycle (offline stub tests)

The experimental Home Assistant coordinator validates all five readings
as one atomic snapshot. Its `UpdateFailed` path is used both when the
runtime is unavailable (regardless of whether a real SDK session or an
RPC45 call failed) and when snapshot validation rejects a stale,
wrong-device or incomplete batch. It does not expose private runtime
exception strings.

`experimental/home_assistant/tests/test_dev3_sensor_availability.py`
now imports the **real candidate sensor entity and coordinator source**
through minimal Home Assistant API stubs, then simulates the HA
`DataUpdateCoordinator.last_update_success` transition. The tests
verify that:

- a prior complete five-sensor snapshot becomes unavailable on a
  subsequent pre-RPC session failure even if the coordinator retains its
  previous in-memory data;
- an analogous RPC45 failure makes all five unavailable, and a later
  *validated* five-sensor snapshot restores all five together;
- an incomplete snapshot never becomes an available partial state;
- an invalid initial read exposes no available values;
- the five sensor entity identifiers remain unique for the device.

This is an **offline behavioral contract**, not an installed HA Core
integration test: the coordinator's success flag and entity availability
are represented by intentionally small HA stubs. The tests do not
start HAOS, enable polling or modify the installed LAN integration.
Actual Core entity-registry/state-machine behavior still requires a
separately approved test in an isolated HA environment.

## Isolated Home Assistant Core integration-test gate

An additional, **separate** GitHub Actions workflow,
`.github/workflows/dev3-real-ha-core.yml`, uses Python 3.14 and
pins `homeassistant==2026.11.2` and
`pytest-homeassistant==2026.11.2`. It is deliberately distinct from
the fast Python 3.12 mock-based contracts and from any HAOS deployment.

The real-Core test module lives at
`experimental/home_assistant/tests_core/test_real_core_availability.py`.
It constructs the **actual** Home Assistant
`DataUpdateCoordinator`/`CoordinatorEntity` classes together with
our remote coordinator and sensor source. The only injected component
is an offline snapshot reader with a fixed finite sequence; there are
no Nabto SDK calls, external network sockets, host credentials or real
device values. It covers success -> runtime unavailable -> valid
recovery for all five sensor objects, plus failure on incomplete
snapshots.

The initial gate validates Core's coordinator/entity availability
contract, **not** a fully registered entity-state-machine integration
or an installed Supervisor app. Even a green workflow cannot authorize
continuous Nabto polling. The workflow must report a passing result
before treating this as verified against Home Assistant Core.
