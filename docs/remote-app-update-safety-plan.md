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
  After attestation, the operator ran the read-only Phase F stop gate again
  and confirmed that Supervisor reported **stopped/manual/dev1**, with no
  residual dedicated Docker container. No App data or keys were accessed.
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
- **Completed:** the operator independently confirmed the diagnostic App
  stopped after the mount/UID test using Phase F. A fresh stop check is still
  required before any mutating future upgrade.
- The installed source file fingerprints must be checked before drafting a
  replacement source transaction; only allowlisted code/configuration paths
  may be read. The dedicated App data directory must not be enumerated.

This document records a future decision gate, not permission to run one.

## Read-only source fingerprint gate prepared

`scripts/audit_haos_remote_update_source_readonly_v1.sh` has an inert
`--preflight` and explicit `--execute-readonly`. It checks Supervisor
`stopped/manual/0.1.0-dev1`, refuses a running dedicated Docker container,
and computes SHA256 **only** for fixed allowlisted existing local App *source*
files (manifest, Dockerfile, entrypoint and two runtime modules). It does not
read or enumerate `/mnt/data/supervisor/apps/data`, options, profile or tokens,
and does not stage, install, update, reload or start anything. A missing
expected source file blocks rather than guessing. The test uses fake source,
fake Supervisor and Docker; real HAOS execution is not yet verified.

The fingerprint result must be reviewed before any approval to replace an
existing local Supervisor source tree. This is not itself an upgrade.

**Offline regression:** Source fingerprint gate passed [GitHub Actions 44829263224](https://github.com/rabbyraptor/genvexconnect/actions/runs/44829263224): 277 backend tests and 27 HA tests in each of two environments, including stopped/running/automatic-boot, missing code file and linked source path. No actual HAOS source fingerprints have yet been collected, and no update was performed.


## Verified source fingerprint and new dev2 candidate

The operator ran the stopped/manual `0.1.0-dev1` source-only audit on HAOS. The fixed five-file SHA256 inventory was:

| File | Installed SHA256 | Comparison with then-current development source |
| --- | --- | --- |
| `config.yaml` | `5c15ac644063f1a0fbcbcc3fd2050a56715922bf7f7f5640032b6f49bcdbfaac` | identical before version bump |
| `Dockerfile` | `5c7edfb109ccad4b09a19ff28c3173e405bcb33eb26034174ee10de83d2f4cdd` | identical |
| `run.sh` | `50c68a9defb3c47621ab6d3b901b3e645ac19f539616457f469a1cb76a91f398` | identical |
| `runtime/app_bootstrap.py` | `9e8862450d6204d21136baae25ce37aa24aa591f1008842c5914911517db7db1` | identical |
| `runtime/profile_provision.py` | `3d35505bfc12b24cc0f68e0a437c6fce047ffe2613ab13ccb10fe2959ec1fe82` | differs as expected (new hardened importer only in development) |

The hashes above contain no credentials. They establish equality of those
**five files only**, not a whole-directory proof. The audit did not enumerate
private data, source runtime modules beyond the allowlist, or Supervisor options.
The installed App remained stopped, manual, without an App container.

The development manifest now declares **`0.1.0-dev2`** for the new candidate,
distinct from installed `0.1.0-dev1`. The ARM64 CI image build argument and
label assertion also target `0.1.0-dev2`, with a regression test enforcing
consistency. This is **source-only**; the installed App remains `0.1.0-dev1`.
The new version must pass its build, packaging and offline tests before any
source update is proposed. The existing first-install staging script cannot
upgrade an existing local App directory.

**Explicit approval boundary:** No copying source to HAOS, Supervisor reload,
App update/rebuild, manual start, profile transfer or live polling is authorized
by the source comparison or by the new dev2 version tag.
