# Standalone repository extraction — DEV8

## State (22 November 2026)

Target: **`rabbyraptor/genvex-remote`**, initially private and empty.

Preparation branch in the original fork:
[`standalone-repo-migration`](https://github.com/rabbyraptor/genvexconnect/tree/standalone-repo-migration).
The source is pinned to DEV8 commit
`eb4e361f0d0dae351d8b825207d0a9e202cab653`.

The tested history extraction retains all remote-specific source, App,
tests, documentation and historical studies, and removes:

- `custom_components/genvex_connect/`: the original HACS LAN integration
- `hacs.json`: the original LAN distribution configuration
- `formatting.yaml`, `hacs.yaml` and `hassfest.yaml`:
  original upstream-specific workflows

The extracted tree **keeps existing DEV8 directory paths** to avoid conflating
repository separation with runtime refactoring. Old documentation links to
the upstream LAN code are rewritten to explicit upstream GitHub links
without adding the LAN code.

An automated GitHub Actions gate has verified:

- `MIGRATION_PREPARE: PASS` and `STANDALONE_VERIFY: PASS`
- **750 Git history commits** remain after remote-only filtering
- **352 tracked files** in the standalone tree
- Correct App `0.1.0-dev8` and HA `0.2.0` versions
- No LAN integration or LAN HACS metadata
- Documentation link and runtime source parity checks PASS
- 178 App offline tests and 123 HA offline tests PASS
- Combined DEV8 source package PASS

The tests use a fresh Git clone and `git-filter-repo`, with no live
HAOS access, vendor credentials, or write to another GitHub repository.

## Next operator step

Create an **empty private** GitHub repository:

- Owner: `rabbyraptor`
- Name: `genvex-remote`
- Leave **README, .gitignore and LICENSE uninitialized**.
- Retain the existing `rabbyraptor/genvexconnect` fork.

After creating it, run the [migration script](../scripts/prepare_standalone_repo.sh)
on a trusted workstation with working Git/GitHub authentication and
`git-filter-repo` installed:

```sh
bash scripts/prepare_standalone_repo.sh --prepare "$HOME/genvex-remote-standalone"
bash scripts/prepare_standalone_repo.sh --verify "$HOME/genvex-remote-standalone"
bash scripts/prepare_standalone_repo.sh --publish "$HOME/genvex-remote-standalone"
```

`--publish` refuses to modify a repository with existing refs and does not
use force push. It cannot run until the new repository exists.

## Post-publication tasks

1. Confirm the new GitHub repository's default `main` branch and grant
   the connected GitHub plugin access to it if the app uses selected-repo
   permissions.
2. Review workflows and source references that still name the old
   `rabbyraptor/genvexconnect` fork; replace only verified deployment
   references in a separate commit.
3. Validate the full offline/backend test suite and GitHub Actions on
   the new repository. Confirm that new releases/package archives build.
4. Keep existing installed App slug `genvex_nabto_remote`, integration domain
   `genvex_remote`, entity unique IDs and data contracts stable.
5. Leave the DEV8 HAOS installation running, then update its source
   repository registration only as a deliberate, separate deployment step.
6. Review historical Git objects, licensing and distribution assumptions
   before changing the new repository from private to public.
7. Plan code path simplification and historical-script archival after
   successful independent CI acceptance.

The original LAN repository and DEV8 live deployment remain intact during
this process.
