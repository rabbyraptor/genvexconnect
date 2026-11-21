# DEV3 continuous-polling recovery regression (offline)

Status: **source-only regression test**. The real HAOS operator has separately
verified the installed `0.1.0-dev3` App running on the private `hassio`
network and returning authenticated, fresh RPC45 readings. The real Home
Assistant `genvex_remote` installation has one enabled config entry, one
device and five active sensor states with values matching RPC45.

The test `tests/test_dev3_polling_http_recovery.py` exercises the actual
`PollingService`, `SnapshotState` and `SnapshotHTTPServer` together over
an actual **127.0.0.1-only** TCP socket with an injected synthetic reader:

1. A successful scheduled read publishes five sensor readings via HTTP 200.
2. A request without the IPC token returns HTTP 401.
3. A simulated SDK/RPC failure invalidates the entire batch. The
   authenticated HTTP endpoint returns 503, never stale HTTP 200.
4. The next scheduled read, without restarting the poller or HTTP server,
   publishes a new complete batch as HTTP 200.
5. Stopping the poller invalidates the snapshot and leaves HTTP at 503.

Run from `genvex-nabto-remote/`:

```sh
python3 -m unittest discover -s tests -p 'test_dev3_polling_http_recovery.py' -v
```

This is **not** a claim that a physical gateway disconnection has been
induced and recovered from on HAOS. It does not probe a live SDK failure,
Home Assistant's UI availability transition, OS process supervision,
automatic App restart or SDK resource leaks. A live fault-injection
exercise requires its own reviewed procedure and operator action.

## Actual HAOS App stop/start recovery: PASSED (operator, 2026-11-21)

The operator ran DEV3 Gate E.2 against the installed real HAOS App
`local_genvex_nabto_remote` version `0.1.0-dev3`, configured for manual
boot and live polling. The test read the five `genvex_remote` entities'
latest recorded states through the local Home Assistant Recorder database.
Exact observed markers:

```text
APP_STATE: started
BASELINE_NUMERIC: 5
BASELINE: PASS
APP_STOP: REQUESTED
APP_STOP: PASS
HA_ALL_UNAVAILABLE: PASS
APP_RESTART: REQUESTED
APP_RESTART: PASS
HA_ALL_RECOVERED: PASS
GATE_E2_RESULT: PASS
GATE_E2_EXIT_CODE: 0
```

This verifies five numeric Recorder states before stopping the installed App,
all five recorded as `unavailable` during the outage, and all five returning
to numeric states after the App was started again. No integration reinstall or
config-entry reload was part of the test. The App restart was initiated by
the operator's bounded test script, **not by a demonstrated automatic
Supervisor restart**.

**Scope:** This is real App stop/start recovery observed in Recorder. It does
not by itself prove current in-memory HA state at every instant, physical
Nabto connection loss while the App remains running, an SDK subprocess
failure/recovery under unattended polling, or long-term CPU/memory stability.
Do not treat it as a live SDK fault-injection test.

The first version of the Gate E script aborted before touching the App because
the minimal HAOS host Python lacked `sqlite3`; a second run failed its
aggregated baseline gate. A separate read-only Gate E.1 then verified five
numeric states and a started App. The corrected Gate E.2 completed with
the PASS markers above.

## Actual HAOS polling stability Gate F: PASSED (operator, 2026-11-21)

Four passive readings of the already running live DEV3 App, spaced by
70 seconds, produced four HTTP 200 responses with complete, validated,
fresh five-value snapshots and four distinct snapshot timestamps:

| Sample | Snapshot age | Container memory | Process count |
| --- | ---: | ---: | ---: |
| 1 | 63.9 seconds | 76.75 MiB | 9 |
| 2 | 4.0 seconds | 17.98 MiB | 8 |
| 3 | 9.8 seconds | 18.38 MiB | 8 |
| 4 | 15.6 seconds | 18.07 MiB | 8 |

Exact operator markers: `FRESH_VALID_SAMPLES: 4 /4`,
`DISTINCT_SNAPSHOTS: 4`, `PROCESS_COUNT_MIN: 8`,
`PROCESS_COUNT_MAX: 9`, `GATE_F_RESULT: PASS` and
`GATE_F_EXIT_CODE: 0`.

This establishes successful short-term polling and fresh snapshots.
The initial memory and process-count spike may have coincided with a
short-lived SDK/QEMU subprocess, but **the process identities were not
inspected** and the cause is not established. Four samples are insufficient
for a memory-leak or long-duration reliability claim. Next inspect bounded
SDK child lifecycle and perform an extended passive soak; a real SDK
connection-failure/recovery test is still pending.

## Actual HAOS SDK process lifecycle sampling: PASSED (operator, 2026-11-21)

The operator collected eight read-only `docker top` samples 20 seconds
apart, while DEV3 continued normal polling:

```text
SAMPLE_1: processes=8 zombies=0
SAMPLE_2: processes=8 zombies=0
SAMPLE_3: processes=8 zombies=0
SAMPLE_4: processes=9 zombies=0
SAMPLE_5: processes=8 zombies=0
SAMPLE_6: processes=8 zombies=0
SAMPLE_7: processes=8 zombies=0
SAMPLE_8: processes=8 zombies=0
PROCESS_MIN: 8
PROCESS_MAX: 9
PROCESS_FIRST: 8
PROCESS_LAST: 8
MAX_ZOMBIES: 0
UNIQUE_PROCESSES_OBSERVED: 9
PROCESS_LIFECYCLE_RESULT: PASS
PROCESS_GATE_EXIT_CODE: 0
```

No zombie processes or cumulative process-count growth were observed.
One transient additional process is compatible with the polling SDK/QEMU
child, but its executable identity was not determined. This is
short-duration process sampling, not proof of leak-free operation.

## Correct interpretation of the operator's Recorder evidence

The operator's real Home Assistant Recorder contained five numeric
`genvex_remote` states matching the latest live RPC45 snapshot:
supply 7.3 °C, outdoor 4.2 °C, exhaust 4.8 °C, extract 7.7 °C
and humidity 68%. Four states showed an older `last_updated_ts`
than one changed temperature. That timestamp is **not a polling heartbeat**:
unchanged values can retain their update timestamps. The operator separately
confirmed all five numeric states in the active Developer Tools state view.

For future on-host freshness checks, inspect the runtime's
`timestamp_utc` from an authenticated snapshot and, where available,
Home Assistant's state `last_reported` / actual coordinator events,
rather than infer a failed poll solely from Recorder `last_updated_ts`.
