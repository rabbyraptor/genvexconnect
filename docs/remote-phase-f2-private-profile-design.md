# Phase F2 — private Nabto Micro profile provisioning design

Status: **read-only source preflight implemented with offline unit tests; 13 tests passed on Steam Deck; not yet executed on HAOS.** No importer, credential migration or live enrollment authorized.

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

## Implementation milestone\n- `scripts/remote_profile_preflight.py` checks a source directory and PEM envelopes without creating or copying files. It rejects symlinks, unsafe modes, oversized/missing/malformed PEM, and existing destinations. It intentionally does not certify the destination mount mapping.\n- `tests/test_remote_profile_preflight.py` contains 13 synthetic-fixture test cases. All 13 tests **passed on Steam Deck** (0.004 s), as reported by the user; no HAOS execution yet. The atomic importer, race-resistant source pinning and concurrent-import protection are **not implemented**.\n- Run offline from the repository root: `python3 -m unittest discover -s tests -p test_remote_profile_preflight.py -v`. Do not point the preflight at any real profile without separate approval.\n\n## Known blocker
The App bootstrap currently validates `/data/profile/client.crt` and `client-encrypted.key` but does **not** provide a secure enrollment method. A design document alone does not solve this blocker.

## Stop conditions
Any ambiguous host path, permission mismatch, unexpected App state, existing target, symlink, or potentially exposed secret means stop with no modifications.

## F2.2 synthetic atomic-promotion prototype (7/7 passed on Steam Deck)
- `scripts/remote_profile_atomic_prototype.py` generates **only built-in fake PEM fixtures** under an empty, private test directory; it cannot accept a real profile source and has no command-line interface.
- It stages two files with private permissions, fsyncs them, and promotes the directory; on injected failure it removes staging files.
- `tests/test_remote_profile_atomic_prototype.py` adds seven synthetic tests for promotion, permissions, injected rollback, nonempty-root refusal, symlink refusal and repeated invocation. **7/7 tests passed on Steam Deck** (0.002 s).
- Run on Steam Deck in the existing repository: `git pull --ff-only && python3 -m unittest discover -s tests -p 'test_remote_profile_atomic_prototype.py' -v`.
- The original `os.rename` limitation was addressed in F2.3 below. The prototype remains synthetic-only and unfit for real credential migration.

## F2.3 atomic no-clobber and concurrency (2026-11-20)
- Replaced `os.rename` with Linux `renameat2(RENAME_NOREPLACE)` through ctypes, **without a fallback** that could overwrite an empty destination directory.
- Staged fake files are private (`0600`), staging directory `0700`, and fsynced before promotion. Injected failures remove staging; success retains a private lock marker to prevent re-use of the same disposable test root.
- Added tests for destination creation during staging (including empty directory and symlink), two concurrent importer simulations, and rejection when atomic no-replace is unavailable.
- **12/12 tests passed in an isolated local Linux environment** (0.076 s); **12/12 passed on Steam Deck (0.019 s), reported by the user**. The 7/7 F2.2 tests were separately reported passed by the user.
- Run: `python3 -m unittest discover -s tests -p 'test_remote_profile_atomic_prototype.py' -v`.
- **Not a production importer:** code creates only built-in fake PEM data. No real-profile reading, source-race protection, approved Supervisor mount mapping, or real credential migration is implemented. Path race hardening, crash/power-loss testing and long-running concurrency stress remain outstanding.

## F2.4 next gate — read-only Supervisor data-path attestation
- Confirm the experimental App remains stopped and its credential options remain empty, with no private profile or IPC token present.
- Inspect only directory metadata and mount mappings for the Supervisor-managed App data directory; never dump options, PEM files, tokens, or environmental variables.
- A host path under `/mnt/data/supervisor/apps/data/` is an observation, not proof of the container `/data` mapping; verify it independently against actual Supervisor/Docker metadata before any sensitive copying.
- Keep the App stopped; no install, rebuild, SDK startup, enrollment, or LAN integration changes are authorized by the F2.4 audit.
