# Phase F2 — private Nabto Micro profile provisioning design

Status: **read-only source preflight implemented with offline unit tests; tests not yet executed on HAOS.** No importer, credential migration or live enrollment authorized.

## Verified baseline (2026-11-20)
- `local_genvex_nabto_remote` v0.1.0-dev1 installed, manual boot, stopped.
- `diagnostic_only: true`; device ID, identity, unlock secret and IPC token empty.
- No `profile` or `ipc-token` in the experimental App's private data.
- `app_local_genvex_nabto_remote` absent from running Docker containers.
- Existing `app_local_genvex_nabto_runtime_test` remains running.
- Synthetic Core-to-App HTTP diagnostic passed; this is **not** a live Nabto session.

## Objective
Safely provision an **already authorized** Nabto Micro client certificate and encrypted private key into the experimental App's own `/data/profile`, without copying through HAOS `/share`, exposing a network enrollment endpoint, modifying the existing working profile, or printing secrets.

## Proposed trust boundary
1. A separately reviewed, explicitly approved operator-only import tool runs on the HAOS host, never as an unauthenticated App HTTP route.
2. Its source profile is an explicitly selected, pre-existing profile. It must refuse symlinks and unexpected file types, validate bounded sizes and PEM envelopes, and never print content or credentials.
3. Destination is the new App's Supervisor-managed private data folder only, verified by exact App slug and directory ownership/mount mapping. No writes to the existing test App or LAN integration.
4. Import must be **copy-only**, with private temporary staging, `0700` directory and `0600` files, atomic promotion after complete validation, and rollback on any failure. Existing destination must not be overwritten implicitly.
5. No unencrypted key, unlock passphrase, account email, or IPC bearer token in CLI arguments, logs, GitHub, shell history or public network. Passphrase/token setup is a separate explicitly approved workflow.
6. App stays stopped and `diagnostic_only: true` throughout this phase. No Nabto SDK session or gateway traffic.

## Offline implementation and acceptance gates
- First write a pure Python, dependency-light validator/import planner with an explicit dry-run mode, using only temporary fake PEM fixtures.
- Unit tests: missing source, malformed PEM, oversized input, symlinked directory/file, wrong modes, pre-existing destination, partial failure, concurrent import, cleanup, and no-secret logging.
- Verify the proposed path against Supervisor's actual App data mount before any host import; never assume the container `/data` path maps to a host path without verification.
- CI/offline tests must pass before proposing an operator command. Operator review and separate approval are mandatory before touching any real profile.
- Only after that gate: design private IPC token provisioning and bounded read-only live RPC45 diagnostics as distinct approvals.

## Implementation milestone\n- `scripts/remote_profile_preflight.py` checks a source directory and PEM envelopes without creating or copying files. It rejects symlinks, unsafe modes, oversized/missing/malformed PEM, and existing destinations. It intentionally does not certify the destination mount mapping.\n- `tests/test_remote_profile_preflight.py` contains 13 synthetic-fixture test cases. Test execution and outcomes are **pending**. The atomic importer, race-resistant source pinning and concurrent-import protection are **not implemented**.\n- Run offline from the repository root: `python3 -m unittest discover -s tests -p test_remote_profile_preflight.py -v`. Do not point the preflight at any real profile without separate approval.\n\n## Known blocker
The App bootstrap currently validates `/data/profile/client.crt` and `client-encrypted.key` but does **not** provide a secure enrollment method. A design document alone does not solve this blocker.

## Stop conditions
Any ambiguous host path, permission mismatch, unexpected App state, existing target, symlink, or potentially exposed secret means stop with no modifications.
