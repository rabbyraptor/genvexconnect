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
