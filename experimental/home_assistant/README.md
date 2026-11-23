# Genvex Remote — experimental Home Assistant integration

The **`genvex_remote`** component is independent of the original `genvex_connect` LAN/HACS integration. Its current **verified deployment baseline is DEV9**: App `0.1.0-dev9`, HA component `0.3.0`, one Optima 270 / HAOS ARM64 test installation, 24/24 registered available sensor entities with v4 and raw v3 enabled.

Changes on `overnight-refactoring` are source-branch work, not a deployed update.

## Data flow and identities

1. `config_flow.py` collects the 12-digit device ID and either a manually supplied private IPC token or automatic Supervisor pairing.
2. `runtime_client.py` fetches the authenticated, private HTTP snapshots, using one bounded token-refresh/retry on IPC 401/403 in auto-paired mode.
3. `coordinator.py` validates device identity, schema version, timestamp and signed raw data; it polls the App cache on a fixed interval and enforces the freshness grace policy.
4. `sensor.py` registers five scaled readings, a data-age entity, one RPC42 selected stage and optionally seventeen raw RPC45 diagnostics. Unique IDs remain stable.
5. The Nabto Micro SDK, encrypted session, actual RPC reads and gateway credentials remain exclusively inside the separate HAOS App.

| App endpoint | HA content |
| --- | --- |
| `/v1/snapshot` | Five scaled sensor values |
| `/v3/snapshot` | Five scaled + 17 raw RPC45 values (optional twelve all-or-nothing) |
| `/v4/snapshot` | V3 plus selected RPC42 stage 0–4 or null |

The App serves already-validated cached samples; an HTTP GET does not trigger a fresh Nabto request.

## Sensor names and icons for new/imported entities

Every entity has a stable unique ID. Five baseline readings, stage and data-age sensors use native Home Assistant translation keys. All seventeen raw diagnostic sensors now use `raw_<key>` translation keys instead of an overriding hardcoded Danish name. English (`strings.json` and `translations/en.json`) and Danish (`translations/da.json`) are supplied, so Home Assistant chooses displayed default entity names according to the **user's selected UI language**; other languages use Home Assistant's normal translation fallback.

Default semantic icons (temperature, humidity, fans, heating, bypass, alarms and diagnostics) are sourced from `register_catalog.py`. Existing user-renamed entities are not automatically renamed. To add new sensor definitions, update the canonical register catalog and regenerate language resources with:

```sh
python scripts/sync_remote_entity_localizations.py --sync
python scripts/sync_remote_entity_localizations.py --check
```

The CI gate refuses missing catalog names/icons.

## Enabling DEV9 data on an already provisioned setup

Enable `persistent_session: true`, `raw_registers_v3: true` and `fan_level_v4: true` in the separate App, then enable matching **Raw registers v3** and **Fan level v4** integration options. Automatic Supervisor pairing remains supported. The stage is a **selected setpoint**, not a fan RPM, speed percentage or verified airflow reading. Raw candidate fields are unitless signed integers.

Only the tested Optima 270 setup is live-verified. No additional controller or remote write support is implied. See [DEV9 architecture](../../docs/overnight-architecture-baseline.md) and [protocol library](../../docs/micro-nabto-protocol-library.md).

## Availability and recovery

- Five mandatory raw registers `20, 21, 22, 23, 26` must be present for a valid poll.
- Twelve optional registers `24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50` are read in a second serial RPC45 request. A failed optional batch does **not** invalidate the baseline readings.
- Missing optional raw sensor values become **unavailable**, rather than appearing as numeric zero.
- Home Assistant retains the most recent *validated* snapshot for up to **600 seconds from the original gateway measurement**, not from HTTP retrieval time. Once that grace expires, the coordinator marks sensors unavailable until another valid sample arrives.
- The data-age diagnostic shows elapsed minutes since the gateway measurement.
- Token refresh and timeout/recovery conditions have passed offline tests; additional live fault-injection and longer stability tests remain pending.

## Offline development tests

From the repository root:

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py' -v
python3 scripts/check_remote_runtime_parity.py --check
```

For the combined App/HAOS release gate, see [historical DEV8.4](../../docs/dev8-4-combined-release-gate.md). For the current public-facing overview, see the [root README](../../README.md). The existing LAN/HACS integration remains separate.
