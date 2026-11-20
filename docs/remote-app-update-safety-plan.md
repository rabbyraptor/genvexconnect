# Genvex Remote App: safe post-diagnostic update design

Status: **planning only**. No update, source replacement, credential import or
real Nabto RPC is authorized by this document.

## Verified boundaries

- Installed Supervisor App: `local_genvex_nabto_remote`, version
  `0.1.0-dev1`, manually started only in the explicitly configured
  synthetic diagnostic mode.
- Operator-confirmed HAOS mount attestation: Docker container `/data`
  is the dedicated `/mnt/data/supervisor/apps/data/local_genvex_nabto_remote`;
  the host and container both report `0755`, UID/GID `0:0`, with an
  in-container UID probe reporting `0`.
- Synthetic diagnostic endpoint was present and production snapshot disabled.
  The App does **not automatically stop** after attestation. Verify stopped
  state before the next stage; never assume it from the successful audit.
- The isolated ARM64 image was built in GitHub Actions and the fake-only
  profile lifecycle passed with `/data` 0755, `/data/profile` 0700 and
  PEM files 0600, without network or host mounts.

## Pre-upgrade checks (read-only)

1. Obtain explicit confirmation that the operator stopped the dedicated
   experimental App; re-run `scripts/audit_haos_remote_phase_f_gate_v1.sh`.
   The old test App and working LAN integration remain untouched.
2. Re-verify available space, the Supervisor App lifecycle and current
   installed **and catalog** versions. Keep `boot: manual`.
3. Determine whether the App source folder on HAOS differs from the pinned
   audited source. Never assume that the old *new-folder-only* staging script
   can update an installed App: it deliberately refuses an existing target.
4. Review *which files* Supervisor would retain, change or regenerate when
   upgrading the same local slug. Do not modify `apps/data/.../options.json`
   or any other private data. Backups/rollback must account for Supervisor
   state and the old known-good image.
5. Create a **new, unique** development version, distinct from the installed
   `0.1.0-dev1`, before attempting Supervisor source refresh. Do not silently
   rebuild a different image under the existing version. Validate the full
   artifact checksum and the allowed archive contents.

## Update execution (requires separate explicit approval)

- Prepare a narrowly scoped, fail-closed replacement of the existing *source*
  directory only, with an independent backup and rollback. This is **not**
  the existing new-install staging script.
- No operations on the App-private `/data` and no changes to the existing
  Genvex LAN integration or separate legacy Nabto runtime test App.
- Refresh Supervisor's local store only after a verified source transaction.
  Inspect the new version without assuming that source replacement updates
  the installed image.
- Use a separately approved Supervisor update/build action (not installation
  retry). Verify stopped/manual state before and after; do **not** start
  credentialed polling. Investigate any unexpected App start or build failure
  rather than performing broad Docker cleanup.
- After update, start only in synthetic diagnostic mode with empty identity,
  secret, token and device ID, then check Core-to-App DNS/HTTP and mount identity
  against the updated version. Stop again and verify stop state.
- Keep certificate provisioning and live RPC45 in their own later approval
  stages. No private keys, tokens or passwords in repository archives,
  terminal output, copied App sources or GitHub Actions artifacts.

## Remaining questions and blockers

- The current source manifest still declares `0.1.0-dev1`. A new audited
  version and reproducible update artifact have **not** been prepared.
- Supervisor-specific **installed App update/rollback semantics** must be
  confirmed before adding a mutating update command. An ARM64 CI image PASS
  does not validate a Supervisor upgrade of an already-installed local App.
- The private profile must be delivered through a separately reviewed,
  confidential channel. File modes alone do not protect secrets against
  a root-privileged operator or other privileged containers.
- Confirm old diagnostic App stopped following the successful mount/UID test.

This document records a future decision gate, not permission to run one.
