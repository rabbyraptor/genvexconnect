# One combined Genvex Remote HA installation and end-to-end test

The test system is one Home Assistant OS 18.5 Raspberry Pi, Core 2026.11.1,
Supervisor 2026.11.0. The already-running DEV6 App version 0.1.0-dev6 remains
the Nabto transport. The combined **HA Core integration version 0.2.0**
contains the existing five live read-only sensors, Data Age, manual IPC
fallback, DEV7 trusted Supervisor pairing and the DEV8 offline projection
contracts. This is ONE HA integration installation, not several patch rounds.

## Single installation

Pin the exact reviewed integration branch commit and use the operator runner:

    bash scripts/run_unified_ha_install_from_deck.sh --apply <40-char-commit>

The runner downloads only the pinned repository commit, packages the
experimental/home_assistant/custom_components/genvex_remote component,
sends the source plus a fixed installation transaction to the HAOS host via
the operator SSH connection and performs one guarded in-place replacement.
The previous component is retained at
/mnt/data/supervisor/homeassistant/custom_components/.genvex_remote_pre_unified_backup.
It runs ha core check, then one HA Core restart and verifies the Core state.
If the check or restart fails, it restores the previous component and
attempts to restart Core. It does not touch App credentials, App runtime,
config entries, or the working legacy Genvex LAN integration.

## One live acceptance

1. HAOS: confirm the original genvex_remote config entry remains loaded,
   the device identity and original six entity IDs are preserved, and the
   Data Age stays low with all five genuine v1 measurements present.
2. Configure the existing Genvex Remote integration (Settings → Devices &
   services → Genvex Remote → Configure) and enable **Pair automatically via
   Home Assistant Supervisor**. This is a one-time in-place option change;
   the options flow verifies the started App before removing the stored
   manual IPC bearer token. Core reloads that same config entry. Do not add
   a duplicate integration.
3. Verify the entry reloads successfully and sensor values continue to
   update; reloading/restarting Core should obtain the current IPC token
   from Supervisor, not from a locally stored secret.
4. Verify the DEV6 App remains running, RPC45 polls continue, the SDK worker
   is reused, and no unexpected Core/App error or restart appears.

DEV8's fan duty addresses and schema v2 are **offline-only proposals**.
The installed DEV6 runtime's RPC45 batch consists of addresses 20, 21, 22,
23 and 26 and its v1 API has no fan fields. Therefore the combined
installation deliberately preserves the five real measurements instead of
registering two misleading unavailable or synthetic fan sensors.
Validation of the raw 18/19 values is a future *data acquisition task*,
not a reason for separate DEV7/DEV8 HA installation cycles.

## Offline acceptance

The combined branch's GitHub Actions candidate workflow tests runtime
source parity, the full App and HA suites, source packages and an ARM64 App
image. experimental/home_assistant/tests/test_unified_installer.py exercises
the one-step installer with a fake HAOS filesystem: checksum failure,
archive traversal, old-source retention, one restart, and rollback on failed
config check.

The general HACS Validate workflow currently fails on repository metadata
(missing GitHub topics and disabled Issues), not on the source itself.

Use a single consolidated report after the installation and Core pairing,
then resolve any findings on the same branch.
