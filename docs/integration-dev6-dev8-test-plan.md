# Combined DEV6–DEV8 integration candidate (22 November 2026)

This source-only branch was created from `dev6-polling-recovery-20261122`
(PR #5) and then received the complete tracked file sets of:
- PR #6: DEV7 Core Supervisor IPC pairing and offline config-entry lifecycle
- PR #7: DEV8 optional seven-reading sensor projection (five by default)
- PR #8: offline SHA-guarded development MCP preflight policy

The DEV6 base already includes the versioned DEV5 runtime source in PR #4.
All original PRs remain drafts and independent review units.

## Combined acceptance gates

1. Runtime/App: verify source parity, DEV6 App version, read-only mode and
   versioned compatibility fixtures, historical DEV5 attestation contract,
   SDK worker recovery and correct filtering of sensitive RPC45 diagnostics.
2. Core pairing: verify the fixed Supervisor App identity, default-off
   pairing, pinned internal endpoint, no persisted automatic IPC token,
   refresh on entry reload and manual-token fallback.
3. Sensor projection: verify five stable default entities; only explicitly
   opting in enables the two additional fan readings.
4. Development MCP: verify SHA-guarded patch preview remains **non-writing**
   and the allowlisted offline test runner cannot execute arbitrary commands.
5. Artifact build: generate the ARM64 App candidate and HA development
   integration package using ordinary GitHub Actions without production
   credentials.

## CI and live gates

GitHub Actions run offline tests on the combined branch. Offline success
alone does not prove actual HAOS/Core activation or Nabto certificate setup.

After review, an explicit HAOS live-test decision is needed for:
- current installed App/HA Core pairing and Supervisor options visibility
- actual temperature/humidity readings and availability continuity
- optional fan-duty readings versus the official Genvex Connect UI
- at least one controlled App restart/recovery and an explicit rollback path

Do not conflate the user's network extender relocation/firmware update with
changes to the Nabto runtime. The installed `0.1.0-dev5` App is not changed
by this source integration branch.

No merge or deployment to the canonical branch is implied by this candidate.
