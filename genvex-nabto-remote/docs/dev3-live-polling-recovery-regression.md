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

## Actual HAOS private network outage/recovery Gate G: PASSED (operator, 2026-11-21)

Before fault injection, the operator verified the installed live App container
was running, attached only to the Docker `hassio` bridge, without published
host ports, with restart policy `no`. The operator then executed a
time-bounded 180-second `docker network disconnect hassio` of the **running
DEV3 container**, with an independently launched reconnect watchdog.
Afterward the test explicitly reattached `hassio`, observed the
Home Assistant Recorder state transitions and queried Supervisor App state.

Exact sanitized operator markers:

```text
BASELINE: PASS
RECOVERY_WATCHDOG: ARMED
NETWORK_DISCONNECT: PASS
HA_UNAVAILABLE_DURING_OUTAGE: PASS
NETWORK_RECONNECT: REQUESTED
NETWORK_RECONNECT: PASS
RECOVERY_OBSERVATION: STARTED
APP_REMAINED_STARTED: PASS
HA_ALL_RECOVERED: PASS
GATE_G_RESULT: PASS
GATE_G_EXIT_CODE: 0
```

All five remote entities transitioned to recorded `unavailable` during the
outage and later back to numeric readings after restoring the private
network. Supervisor reported the App still `started`. This establishes
**live recovery across a container-network outage** without a
test-script-initiated App stop/start.

Limitations: the script checked Supervisor's `started` state, not a
continuous container PID, container ID, or start timestamp, so it does not
strictly rule out an automatic container restart. The exercise interrupted
**all** connectivity, including private Home Assistant IPC; it did not
isolate a Nabto-only UDP/RPC failure, and did not count SDK-specific errors.
A separate fault-injection trial must distinguish SDK session recovery from
the IPC reconnection behavior. No direct evidence about use of
`api.lscontrol.dk:4160` was collected in this test.

## Actual HAOS Core restart/maintenance Gate I.1–I.2: PASSED (operator, 2026-11-21)

Read-only preflight Gate I.1 confirmed one enabled `genvex_remote`
config entry, five registered entities, one device, and integration version
`0.1.0`. The sorted entity-ID signature was
`2be9240972de0a9d`.

With operator approval, Gate I.2 ran `ha core restart` on the actual
HAOS installation. The test compared Home Assistant Core container identity
and start time before and after, and independently compared the DEV3 App
container identity/start time, entity IDs, registries and latest Recorder
states after the Core restart. Operator output:

```text
BASELINE: PASS
ENTITY_ID_SIGNATURE: 2be9240972de0a9d
CORE_RESTART: REQUESTED
CORE_RESTART_COMMAND: PASS
CORE_RESTART_OBSERVED: PASS
CORE_RUNNING: PASS
DEV3_APP_UNCHANGED: PASS
ENTITY_IDS_UNCHANGED: PASS
INTEGRATION_REGISTRIES: PASS
RECORDED_NUMERIC_SENSORS: 5 /5
RECORDER_RECOVERY: PASS
GATE_I2_RESULT: PASS
GATE_I2_EXIT_CODE: 0
```

This verifies that Home Assistant Core restarted, the DEV3 container retained
the same identity/start time, the single enabled config entry and five
sensor entity IDs remained registered, and Recorder showed five numeric
values after the restart. The test did not directly query Home Assistant's
in-memory state machine or prove an independently fresh RPC45 poll
following Core restart; those remain distinct, optional checks.

The 30-minute Gate H and 24-hour passive stability soak are postponed
by operator request, not passed. No unattended-long-duration reliability
claim is made.

## HA entity naming and translation Gate J: PASSED (operator, 2026-11-21)

Home Assistant Core `2026.11.1`, with configured language `en`, initially
showed generic device-class names (`Temperature` / `Humidity`) for the
five existing `genvex_remote` sensors. Both `strings.json` and
`translations/da.json` were installed, but `translations/en.json` was
missing. Commit `a3090e50572afc65fadf4630064e32688ab58f87` supplied
`translations/en.json` and a file-level regression test.

After installing the English translation file and restarting Home Assistant
Core, a first Recorder-based naming test showed stale generic
`original_name` values and reported `REVIEW_REQUIRED`. Subsequent
operator checks confirmed that Core `loader.async_setup(hass)` and
`async_get_translations` returned **all five correct English and all five
correct Danish entity translations**, including key
`component.genvex_remote.entity.sensor.supply_air.name`:

- en: Supply air, Outdoor air, Exhaust air, Extract air, Humidity
- da: Indblæsning, Udeluft, Afkast, Udsugning, Luftfugtighed

A later read-only query of the latest Home Assistant Recorder states and
entity registry verified that **all five names had updated**:

| Sensor key | Registry original_name | Recorder friendly_name |
| --- | --- | --- |
| supply_air | Supply air | Genvex Connect Remote Supply air |
| outdoor_air | Outdoor air | Genvex Connect Remote Outdoor air |
| exhaust_air | Exhaust air | Genvex Connect Remote Exhaust air |
| extract_air | Extract air | Genvex Connect Remote Extract air |
| humidity | Humidity | Genvex Connect Remote Humidity |

All five entity registry `name` overrides were `None`; the same five
registered entity IDs were preserved in earlier post-restart checks
(signature `2be9240972de0a9d`). English display names are expected
because the installation language is `en`. Danish lookup passed in the
loader but display-name switching to Danish was **not** exercised live.
This closes the English naming/translation regression without manually
renaming entities. The original earlier Gate J check was premature.

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

## Gate K: integration source upgrade and recovery (2026-11-21)

- **K.1 PASS:** installed `genvex_remote` version `0.1.0`, 11 files,
  valid en/da translations, one enabled entry, five sensors, one device,
  App version `0.1.0-dev3` started with manual boot, no pre-existing
  upgrade backup; entity ID signature `2be9240972de0a9d`.
- **K.2 PASS:** pinned source `d7ad38a6` successfully checked; only
  `translations/da.json` differed from installed integration.
- **K.3 PASS:** explicit upgrade executed; all 11 installed source files
  and all 11 backup files hash-verified. No Core restart in this gate.
- **K.4 REVIEW_REQUIRED:** Core restarted, App stayed started, names and
  entity IDs stable, but five sensor states remained unavailable.
- **K.5 PASS (diagnostic):** authenticated private HTTP returned 200,
  complete five-value numeric snapshot, matching device ID, age 36 seconds;
  five Recorder states still unavailable.
- **K.6–K.7:** Core logs isolated startup failure at
  `2026-11-21T20:52:33Z`: `Unable to import component: No module named
  'custom_components.'`. Old update installer had stored hidden backup
  inside `/config/custom_components`, causing the import failure.
- **K.8 PASS:** moved old backup to `/config/.genvex_remote-upgrade-backup`
  (outside integration discovery tree) and restarted Core. All five
  sensors recovered numeric values with 15-second latest-state age,
  translated English names unchanged, entity IDs unchanged.

Installer fix `faffc01c` moves *future* backup directories outside
`custom_components`; regression tests cover the backup location and
rejection of the legacy hidden backup. The corrected upgrade writer has
not yet been live exercised. The existing backup remains available; the
30-minute/24-hour soak gates are still postponed.

## Actual legacy Micro Nabto session reuse and post-error recovery: PASSED (operator, 2026-11-21)

The installed DEV3 polling adapter starts a fresh QEMU SDK subprocess per
poll, while its existing read-only probe opens and closes a Nabto session
for each RPC45 request. An isolated opt-in persistent trial
(`runtime/probe_persistent_session_trial.py`) instead uses one QEMU
process, one `nabtoStartup`, one `nabtoOpenSession`, one RPC interface
registration, and one final close/shutdown, with serial read-only RPC45
requests and 60-second spacing. The active DEV3 App continued polling
in parallel; results are **not** an isolated comparative reliability claim.

Previous A+B.2: SDK startup/resources/session/interface status all 0,
RPC45 success (1197ms), success (24ms), status 26 (13235ms). Two of
three reads succeeded, all using the same session handle.

Previous A+B.3: four RPC45 successes (1217ms, 29ms, 27ms, 28ms)
followed by status 26 (13422ms). The last-call failure did not allow an
in-session recovery attempt; `RECOVERED=False` was inconclusive.

**A+B.4 PASS** (source revision `2626da3614f87536505acd85efb4e76cca6ddcad`):

```text
SDK_STARTUP_STATUS: 0
SDK_RESOURCES_STATUS: 0
SESSION_OPEN_STATUS: 0
RPC_INTERFACE_STATUS: 0
PROCESS_REUSE: ONE
SESSION_OPEN_COUNT: 1
SESSION_HANDLE_REUSED: YES
RPC45_1: status=0 values=5 elapsed_ms=1004 session_reused=first
RPC45_2: status=26 values=0 elapsed_ms=5046 session_reused=yes
RPC45_3: status=0 values=5 elapsed_ms=384 session_reused=yes
RPC45_4: status=0 values=5 elapsed_ms=27 session_reused=yes
RPC45_SUCCESS_COUNT: 3/4
RPC45_FAILURE_COUNT: 1
RPC45_FAILURE_OBSERVED: True
RPC45_POST_FAILURE_ATTEMPTS: 2
RPC45_RECOVERED_IN_SAME_SESSION: True
SESSION_CLOSE_STATUS: 0
SDK_SHUTDOWN_STATUS: 0
TRIAL_EXIT_CODE: 0
GATE_AB4_RESULT: PASS
```

**Established:** a legacy Nabto SDK session can remain usable after an
RPC45 return status 26, without calling `nabtoCloseSession` /
`nabtoOpenSession` or restarting the SDK process. This does not identify
what status 26 means, does not establish an advertised session TTL, and
does not prove long-term reliability or eliminate gateway concurrency as
a cause. Future work: compare failure rate under isolated, mutually
exclusive persistent versus one-shot polling; exercise bounded recovery
and resource cleanup in an offline test harness before any live migration.
