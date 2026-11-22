# DEV8.3 — all 17 raw RPC45 registers (staged, no HAOS deployment)

**Branch:** `dev8-staging`, draft PR #16. **Status:** source implementation
and offline test gate. This step supersedes the narrower proposal to
expose only two fan-duty readings: the requested scope is **all raw values**.

## Contract

The established `/v1/snapshot` remains exactly five scaled measurements
with unchanged device/entity identifiers, availability and grace policies.
A separate, explicitly opt-in `/v3/snapshot` carries:

- Five validated, scaled measurements in `values` (same keys as v1);
- Five mandatory signed-int16 registers in `raw_values` for addresses
  `20,21,22,23,26`;
- Twelve *additional* signed-int16 registers in
  `optional.raw_registers` for the exact historical order
  `24,18,19,35,36,41,42,53,40,114,115,50`.
  This group is either complete or `{}`, **not** a mix of invalid,
  missing and zero-valued registers.

There are **17 raw register entities in addition to five scaled sensors**.
The existing data-age sensor is kept. HA entity unique IDs are
`<device_id>_rpc45_raw_<address>`, independent of translated labels.

All 17 raw entities are diagnostic sensors with numeric signed-int16 states,
**no unit and no inferred temperature, fan RPM, percent, alarm or hardware
presence**. Address 18 raw value `6000` is displayed as `6000`,
not `60 %`; address 114 raw `0` is not displayed as "no alarm".
Raw values are enabled when the explicit v3 option is enabled.

## Runtime architecture

A single persistent Nabto SDK worker supports two commands:

- `POLL\n` performs the original single five-register RPC45 and yields
  an unchanged v1 snapshot.
- `POLL3\n` performs the same five-register RPC45 first, then a second,
  serial RPC45 with the twelve source-backed additional addresses.
  The second read is not a scan and never uses RPC42 or a write RPC.
  If it fails, v3 still provides the valid five scaled and five raw
  baseline values, while the other twelve are unavailable.

The v3 state owns one atomic snapshot, projects a separate strict v1
response, and exposes the complete or empty optional raw group via the
same private bearer-token authentication. Only the pinned
`http://local-genvex-nabto-remote:18275/v3/snapshot` Core endpoint is
accepted in addition to pinned v1. DEV8.1's in-session token recovery
also applies to the v3 client.

No new sockets are exposed publicly. `raw_registers_v3` is a boolean
App option requiring `persistent_session: true`, default **false**.
Home Assistant's existing options flow has a separate
`raw_registers_v3` opt-in; default **false**. The App mode must be
enabled before selecting the HA option or the v3 reader remains
unavailable. Existing manual and Supervisor token pairing remains.

## Semantic evidence boundary

Earlier user-authorized reads proved *transport readability* for all
17 registers; they do not prove the physical meaning of every raw value.

- Five mandatory baseline addresses: repeatedly validated.
- Fan-duty 18/19: source scaling agrees numerically with an earlier,
  non-simultaneous official Genvex Connect screenshot.
- Other ten: raw-only. A zero may be a real zero, idle value or missing
  hardware. Do not turn alarm words into a binary alarm sensor,
  or raw frost-protection 0 into a physical −30 °C measurement.

The **combined 5+12 two-RPC sequence** has not been live-tested on
the running user's HAOS. Single-shot seven-register HAOS/QEMU
and twelve-register Steam Deck reads are prior partial evidence only.

## Offline acceptance

- App: legacy five-register `POLL` unchanged; v3 `POLL3` calls the
  exact fixed 5+12 addresses serially; optional failure keeps baseline.
- Snapshot: strict version, device identity, timestamp, signed-int16 type,
  exact allowlisted keys, and baseline/raw consistency.
- IPC: bearer auth before route access; v1 and v3 independent responses;
  no credentials or raw SDK JSON outside allowlisted values.
- Home Assistant: five original scaled sensor IDs plus 17 opt-in raw
  diagnostic entity IDs; missing optional values become unavailable,
  not `0`; Core paired token refresh remains active.
- Package: canonical/installed runtime source parity, fake credentials,
  no live RPC, and compilation.

Run the offline suites through CI, or locally with:

```sh
python3 scripts/check_remote_runtime_parity.py --check
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py' -v
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m compileall -q genvex-nabto-remote/runtime experimental/home_assistant/custom_components/genvex_remote
```

**Live gate deferred:** DEV8.4 runs the combined package offline tests,
then stages and transfers one reviewed DEV8 package to HAOS and verifies
normal polling, v1 continuity, all 17 raw values, optional failures,
token rotation and controlled restart. No partial DEV8 deploy.
