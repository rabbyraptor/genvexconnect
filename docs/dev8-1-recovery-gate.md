# DEV8.1 — in-session recovery (staged, not deployed)

**Branch:** `dev8-staging` (draft PR #16). **Base:** `remote-nabto-connection`.

DEV8.1 is the first step of a staged DEV8 release. Changes remain in source
until DEV8.1–DEV8.4 have been combined, tested, and approved for a **single**
HAOS transfer. Do not install a partial DEV8.1 package.

## Failure cases and behavior

| Condition | Intended behavior |
| --- | --- |
| Healthy snapshot (200) | One request; keep existing in-memory bearer token |
| App restart / temporary network failure / 503 | Existing coordinator polling retries next cycle; keep last validated sample within its ten-minute grace period; no Supervisor lookup |
| App rotates IPC bearer token, endpoint returns 401/403 | Fetch the new token from the fixed started App via Home Assistant Core's authenticated Supervisor client; retry that read exactly once |
| Supervisor unavailable, wrong device, token unchanged/invalid | One sanitized failure; preserve old in-memory token and retry a later polling cycle |
| Retry is also unauthorized | Fail the cycle; no recursive refresh or unbounded request loop |
| Concurrent 401/403 | Only one Supervisor refresh for the same stale token; other calls reuse the rotated value |
| Manually paired entry | No automatic Supervisor lookup or token substitution |
| Core starts while App stopped | Existing `ConfigEntryNotReady` path defers setup until Supervisor pairing is available |

The normal startup path still fetches the token from Supervisor for each paired
config-entry load/reload. In-session recovery is **in-memory only**:
`ConfigEntry.data` retains no IPC token. The fixed IPC endpoint, App ID,
device matching, HTTP no-redirect policy and read-only snapshot contract are
unchanged. No extra sensor registers or write commands are introduced.

## Security and scheduling boundaries

- Only explicit IPC HTTP 401/403 responses request a token refresh. Neither
  503 nor a socket/SDK error is treated as a token mismatch.
- Every HTTP attempt keeps the existing 20-second timeout and 4096-byte body
  limit. A replacement-token lookup has its own 12-second upper bound, while
  the underlying Supervisor adapter uses ten seconds.
- A single snapshot read can use at most two HTTP attempts and one Supervisor
  metadata lookup. The caller's coordinator continues its 60-second poll
  cadence and the original measurement age/grace policy.
- Replacement tokens are validated before use and never placed in config,
  logs, HTTP error strings or outbound URLs. A rejected, malformed or
  unchanged replacement never reaches the snapshot endpoint.
- Cancellation propagates; no recovery retries occur after cancellation.

## Offline verification

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m unittest discover -s experimental/genvex_remote -p 'test_*.py' -v
python3 -m unittest discover -s genvex-nabto-remote/tests -p 'test_*.py' -v
python3 -m compileall -q experimental/home_assistant/custom_components/genvex_remote
```

`test_dev8_recovery.py` covers rotation, repeated authorization rejection,
non-auth failures, manual mode, same/invalid token, redaction, concurrency,
cancellation, bounded lookups and App restart with/without rotation.
`test_setup_auto_pairing.py` checks that only paired entries receive the
refresh callback.

## Combined-release live acceptance (deferred)

After all DEV8 substeps are staged and the combined package is installed
once, use MCP to verify:

1. Normal 60-second RPC45 polling and live sensor updates.
2. App stop / start with an unchanged IPC token: the integration resumes
   automatically, preserving last valid readings during the grace period.
3. Controlled token rotation: a 401/403 leads to a single Supervisor refresh
   and new data without a manual integration reload.
4. Temporary loss of the Supervisor lookup: credentials do not leak into
   Core logs or config, and subsequent polling recovers.
5. Home Assistant Core restart while the App is stopped: entry retries setup
   once the App is available.
6. Grace expiration marks unavailable and a later valid sample restores
   availability; existing entity IDs stay stable.

**Status:** implemented and covered by offline tests; combined HAOS live
acceptance is pending DEV8 packaging and deployment. DEV8.2–DEV8.4 are not
included in this step.
