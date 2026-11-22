# DEV8.4 — combined integration, regression and single HAOS release gate

**Scope:** DEV8.1 recovery + DEV8.2 evidence ledger + DEV8.3 all seventeen
raw RPC45 sensor values. All changes remain in the dedicated
`dev8-staging` draft PR #16 until release readiness is established.

## DEV8.4.1 — completed: full simulated transport chain

The CI-only tests use one fake persistent SDK child process, a real local
127.0.0.1 HTTP listener, the actual versioned state projection, and the
Home Assistant HTTP reader/coordinator:

- one worker/session reused for repeated polls;
- exactly five mandatory registers and twelve optional candidates;
- one cached v1 snapshot and one independently authenticated v3 snapshot;
- HTTP requests never trigger new RPC45 calls;
- missing optional registers do not invalidate the five mandatory values;
- App bearer token rotation produces 401, one Core Supervisor refresh and
  then a successful retry, without a manual integration reload;
- a temporary 503 does not trigger a Supervisor token lookup;
- an SDK-child timeout invalidates both projections; a new child can recover;
- an unsuccessful token lookup leaves the last valid Core sample within grace.

**These use fake credentials, no real Nabto, and loopback sockets only.**

## DEV8.4.2 — completed: source/register parity

The immutable Optima 270 register order is compared across:

1. the evidence-aware 17-register catalog;
2. the App's v3 raw-int16 schema;
3. Home Assistant's 17 raw diagnostic entity keys and addresses.

The tests use the archived signed-int16 fixture and 200 deterministic synthetic
signed-int16 groups, including negatives, to check that HA receives
the exact raw integer without applying fan, temperature, alarm or PWM
interpretation. Missing optional keys must be absent, never fake zeros.

## DEV8.4.3 — completed: accelerated failure and recovery checks

The offline coordinator was exercised through 360 rapid synthetic update
cycles with intermittent network failures, optional register loss and
reappearance. Separate tests cover ten-minute grace expiration followed by
a fresh baseline and all seventeen raw registers being restored.

This is an accelerated regression, **not** a measured 360-minute live
session or proof of recurring RPC45 availability on the physical gateway.

## DEV8.4.4 — combined source package

- Genvex Remote Supervisor App: `0.1.0-dev8`.
- Home Assistant component: `0.2.0`.
- A single deterministic archive:
  `genvex-remote-dev8-combined.tar.gz`.
- Both source trees and `DEV8_RELEASE_MANIFEST.json` with per-file SHA256,
  exact versions, schema version 3 and 17 address numbers.
- Independent `DEV8_COMBINED_SHA256SUMS` checksum and source-parity gate.
- CI compiles/tests components and builds the native ARM64 image without
  real credentials. The release archive remains **source-only**; Supervisor
  builds/updates the App on HAOS from the staged source.
- No integration IDs or stored credentials appear in the archive.

The combined package is emitted as a CI artifact by
`.github/workflows/remote-app-offline.yml`, while the separate
App/HA artifact builders remain for diagnostics.

## DEV8.4.5 — prepared combined installer, live deployment pending

`scripts/run_dev8_combined_from_deck.sh` takes one immutable 40-hex Git
source commit and supports two modes. It builds and sends **one combined
component archive** over the existing authenticated SSH path, plus the
small reviewed host-side installer:

- `--preflight` verifies the pinned sources, hashes, App version,
  installed HA component, Core health, filesystem capacity and eligible
  rollback paths without modifying installed components.
- `--apply` repeats preflight, stages both components, stops the existing
  DEV6 App, retains its prior source, asks Supervisor to update to DEV8
  with backup, restarts the App, swaps the HA component with a separate
  prior-source backup, checks Core and restarts it once.
- On a pre-install App failure, restore DEV6 source and restart the old App.
  On HA component check/restart failure, restore the old HA integration.
  A successfully installed DEV8 App retains v1 support, even if Core
  cannot be upgraded in that transaction.
- The runner clears the operator terminal before final output, so the
  complete result can be copied with Ctrl+A / Ctrl+C.

**Actual installed App checked via MCP on 22 November 2026:** version
`0.1.0-dev6`, running, restart count 0. The `genvex_remote` config
entry was loaded and six legacy sensor entities returned values. This
satisfies the *expected old version* condition, but the host-side
archive/install preflight has not yet been executed.

### Runtime activation after one package installation

The App initially keeps the existing v1 mode because
`raw_registers_v3` is explicitly off by default.

To activate 17 raw diagnostics after the combined install:

1. Set Supervisor App option `raw_registers_v3: true` while keeping
   `persistent_session: true`, then restart that App.
2. In Genvex Remote integration options, enable `raw_registers_v3`;
   the integration reloads and reads the pinned `/v3/snapshot`.
3. Verify that the five existing scaled sensors and their IDs are
   unchanged, the data-age diagnostic remains, and 17 new raw
   diagnostic sensors have numeric states for signed-int16 values.

Expected installed entities in raw mode: **23** total
(5 old scaled + 1 old data age + 17 new raw). If the optional
twelve-register RPC45 fails while the baseline succeeds, only the
five raw baseline sensor values remain available until the next
complete optional batch; existing five scaled values continue.

### Live acceptance required before declaring DEV8 complete

- Package source, App version, installed HA component and Supervisor
  pairing verified after Core reload.
- Five mandatory readings update every sixty seconds.
- Twelve additional raw values read successfully as a serial RPC45
  request following the mandatory batch; one persistent worker reused.
- App restart and temporary gateway unavailability recover without
  manual intervention.
- Controlled IPC token rotation invokes a single re-pair and new
  readings without storing a token in the HA config entry.
- Synthetic tests do not replace an actual multi-hour observation of
  the physical Optima 270 remote connection.

No DEV8 App or Home Assistant component has been transferred to the
live HAOS yet. The draft PR must remain staged until the single
deployment and acceptance checks have completed.
