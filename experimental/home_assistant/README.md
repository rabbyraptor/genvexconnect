# Genvex Remote: experimental Home Assistant integration

**Verified on the operator's HAOS installation (2026-11-21):** The separate
`genvex_remote` custom integration is installed with one enabled config entry,
one device and five live numeric sensors backed by authenticated DEV3 RPC45
snapshots. App stop/start, private-network outage/recovery and HA Core restart
were tested successfully. Five entity IDs were retained across Core restart.
The original LAN integration `genvex_connect` remains a separate component.

This is an experimental, manually managed integration; automated onboarding,
SDK redistribution rights, and 30-minute/24-hour soak tests remain outstanding.
The installer supports an explicit backup-retaining upgrade mode; it is
not yet live-tested on HAOS. See [procedure](../../docs/dev3-integration-install-update.md).

The skeleton contains:
- `config_flow.py` (12-digit ASCII device ID, unique ID, internal IPC endpoint and bearer token in config entry);
- `coordinator.py` (60-second update interval; one atomic five-reading result);
- `sensor.py` (five sensor entities with stable IDs, device registry grouping, measurement state classes);
- `snapshot.py` (strict, freshness-bounded complete-schema validation);
- `runtime_client.py` (authenticated private-HTTP snapshot consumer used by the live setup);
- English and Danish translated labels.

Home Assistant Core 2026.11.1's own translation loader verified all five keys
in both `translations/en.json` and `translations/da.json`. The installed
English-language Core uses correct translated English friendly names; no
manual entity renaming was needed. The source installer requires **both**
translation files. Live switching to Danish has not been exercised.

## Runtime bridge acceptance criteria

1. Strictly authenticated HA Core -> isolated App communications, using a nonpublic endpoint and narrow token scope; validate HAOS/Supervisor networking, and avoid unauthenticated host-network listeners.
2. App generates an atomic snapshot from one authorized read-only RPC 45 of addresses 20,21,22,23,26, after successful SDK session. No static example sensor data should be reachable through the runtime API.
3. Reauth and certificate registration must use the actual independently authenticated legacy CA; never send an account password into the current unconfigured reader or save a password in the config entry.
4. Coordinator rejects stale (>180s), future (>30s), partial, nonnumeric and wrong-device readings and marks entities unavailable upon update failure.
5. Test coordinator/flow/entities on real HA Core or HA test framework before moving to `custom_components/genvex_remote`.
6. SDK redistribution permission and Home Assistant packaging must be resolved.

The separate [certification prototype](../genvex_remote/enrollment_core.py)
and [runtime test App](../../haos-apps/genvex-nabto-runtime-test/DOCS.md)
are earlier building blocks. The source integration has since passed real
Home Assistant Core integration tests in CI and live end-to-end validation
on the operator's HAOS host (see
[DEV3 live recovery evidence](../../genvex-nabto-remote/docs/dev3-live-polling-recovery-regression.md)).

To run parser and mocked HTTP consumer tests without Home Assistant installed:

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p "test_*.py" -v
```
