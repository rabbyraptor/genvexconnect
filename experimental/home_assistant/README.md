# Genvex Remote — experimental Home Assistant integration

This directory contains the separately managed **`genvex_remote`** Home Assistant integration. It is **not** the existing `genvex_connect` LAN/HACS integration.

**Live development status (22 November 2026):** Version **`0.2.0`** was installed on one Home Assistant OS ARM64 system together with the separately isolated **Genvex Remote App `0.1.0-dev8`**. Following activation of raw-register mode, Home Assistant reported **23/23 available sensor entities**: five existing scaled readings, seventeen signed-int16 raw diagnostic register sensors and one data-age sensor.

See [the dated live verification](../../docs/dev8-live-verification-2026-11-22.md) for the actual Optima 270 readings. This is a tested development deployment, **not** a publicly released standalone integration.

## How the Home Assistant side works

The Nabto Micro SDK and any credentials used by it stay inside the **separate Supervisor App**, running a persistent SDK worker through QEMU. The HA component does not connect to the gateway or launch Nabto:

1. `config_flow.py` configures the twelve-digit device identifier and App pairing/IPC settings.
2. `runtime_client.py` reads a strictly pinned private, bearer-token-authenticated App snapshot endpoint. Manual token mode is supported; automatic Supervisor pairing can obtain and refresh the token. On IPC 401/403, paired mode permits one bounded refresh/retry.
3. `coordinator.py` fetches the latest snapshot every **60 seconds**, validates timestamps and device identity and applies the age/grace policy.
4. `sensor.py` exposes five scaled measurement entities and a data-age diagnostic. When v3 mode is enabled, it also creates **17 raw-register diagnostic entities**, retaining stable original entity identifiers.
5. `snapshot.py` validates the five-value legacy v1 schema; `raw_snapshot_v3.py` validates the optional v3 contract, including signed-int16 values.

The private App endpoint is fixed to `http://local-genvex-nabto-remote:18275` with paths:

| Endpoint | Content |
| --- | --- |
| `/v1/snapshot` | Five scaled baseline values |
| `/v3/snapshot` | Same five scaled values, five baseline raw values and up to twelve optional raw values |

The v3 endpoint does **not** initiate separate RPC45 reads on HTTP request. It returns the App's validated current snapshot.

## Enabling raw mode on an already provisioned DEV8 system

1. Enable `raw_registers_v3: true` in the **Genvex Remote App**, keeping `persistent_session: true`; restart that App.
2. Open the **Genvex Remote** Home Assistant integration options and enable **Expose all 17 RPC45 raw values**. Keep automatic Supervisor pairing selected if that is the existing authentication mode.
3. The integration reloads and adds 17 raw diagnostics. Their values are unscaled integers and are not yet verified physical units, alarm states or fan speeds.

Only one remote Optima 270 deployment has been live-verified. General remote profile onboarding, other controllers and proprietary SDK redistribution require separate work.

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

For the combined App/HAOS release gate, see [DEV8.4](../../docs/dev8-4-combined-release-gate.md). For the current public-facing overview, see the [root README](../../README.md). The existing LAN/HACS integration remains separate.
