# DEV8 live acceptance — 22 November 2026

## Deployment

One combined DEV8 App and Home Assistant package was installed from
immutable commit `027dbf807e4eb2a04c2d52b01e64c09420b083b4`.

- Source package: 41 members
- SHA256: `80b86f438cc250cfcafa9d2bb83ec8789f4377cf0fdade21889a286edfaabd0`
- Operator gate: `DEV8_COMBINED_INSTALL: PASS`, `STEAM_DECK_EXIT_CODE: 0`
- HAOS App image confirmed from read-only MCP:
  `local/aarch64-addon-genvex_nabto_remote:0.1.0-dev8`
- App running, zero container restarts
- `genvex_remote` Home Assistant config entry: `loaded`

## v1 baseline after combined update

Immediately after deployment, while the raw v3 feature was not yet
enabled, five baseline physical measurement entities and the existing
data-age entity remained available. App logs showed five successful RPC45
polls, initial cold read 12.88 s and subsequent persistent-process
reads of 0.03–0.11 s with unchanged worker PID 93.

## Opted-in v3 raw snapshot: all 17 addresses available

After the user enabled `raw_registers_v3` for both the Supervisor App and
the Home Assistant Genvex Remote integration, read-only MCP checks
confirmed:

- App running with image version `0.1.0-dev8`, zero restarts
- Integration state `loaded`
- **17/17 raw numeric sensors available**
- **5/5 old scaled sensors available**
- **1/1 old data-age sensor available**
- **23/23 total Genvex Remote sensors available**
- No missing, `unavailable`, or `unknown` raw values
- Raw values correspond to actual enabled v3 gateway polling, not
  synthetic demo or local fake test fixtures

First fully verified raw sensor snapshot, at approximately
**2026-11-22 20:42:00 UTC** (21:42 CET):

| RPC45 address | Raw value |
| --- | ---: |
| 20 | 371 |
| 21 | 335 |
| 22 | 345 |
| 23 | 373 |
| 26 | 62 |
| 24 | 0 |
| 18 | 6000 |
| 19 | 5800 |
| 35 | 2416 |
| 36 | 2268 |
| 41 | 0 |
| 42 | 0 |
| 53 | 0 |
| 40 | 0 |
| 114 | 0 |
| 115 | 0 |
| 50 | 10 |

The concurrent five scaled HA readings were:

- Tilluft `7.1 °C`, matching raw 371 / prior offset convention
- Udeluft `3.5 °C`, matching raw 335
- Afkastluft `4.5 °C`, matching raw 345
- Fraluft `7.3 °C`, matching raw 373
- Luftfugtighed `62 %`, matching raw 62

The refreshed App log showed two consecutive successful v3-mode
RPC45 cycles:

```text
20:41:30 UTC OK 10.71s PID_BEFORE=None PID_AFTER=93
20:42:30 UTC OK 0.07s  PID_BEFORE=93   PID_AFTER=93
```

These are production read-only observations, not simultaneous
cross-checks against the official mobile app. Raw labels do not establish
semantics of optional/bypassed sensors or nonzero/zero alarm bits.

## Remaining acceptance work

The following are not yet independently live-verified for DEV8:

- Controlled IPC token rotation during an active v3 session
- App stop/start, Supervisor outage, or forced SDK timeout after v3 activation
- Multi-hour physical gateway/worker stability under enabled 17-register mode
- Simultaneous independent confirmation of all physical interpretations
  against Genvex Connect UI at different operating points

Existing offline CI covers these edge conditions with fixtures, including
360 synthetic cycles. The live checks above establish successful
combined deployment and actual 17/17 register availability but not all
long-duration or fault-injection criteria.
