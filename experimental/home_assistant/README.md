# Genvex Remote: Home Assistant integration scaffold (not installed)

**Status:** Development-only, **do not copy to `/config/custom_components` yet**. This is an isolated native ARM64 Home Assistant integration skeleton for the user-facing part of the remote solution. The installed `custom_components/genvex_connect` LAN integration remains untouched.

The skeleton contains:
- `config_flow.py` (12-digit ASCII device ID, unique ID, only *non-secret* data stored);
- `coordinator.py` (60-second update interval; one atomic five-reading result);
- `sensor.py` (five sensor entities with stable IDs, device registry grouping, measurement state classes);
- `snapshot.py` (strict, freshness-bounded complete-schema validation);
- `runtime_client.py` (safe-default unconfigured bridge that always raises; plus a separately injectable authenticated HTTP snapshot consumer, **not activated** by integration setup);
- English and Danish translated labels.

**Deliberate behavior:** If installed prematurely, a Config Entry can be created, but startup cannot succeed because `UnconfiguredReader` raises `RuntimeUnavailable` on first refresh. There is **no working authenticated runtime IPC** and **no automated CA onboarding**. Therefore this is not a live or installable product release.

## Runtime bridge acceptance criteria

1. Strictly authenticated HA Core -> isolated App communications, using a nonpublic endpoint and narrow token scope; validate HAOS/Supervisor networking, and avoid unauthenticated host-network listeners.
2. App generates an atomic snapshot from one authorized read-only RPC 45 of addresses 20,21,22,23,26, after successful SDK session. No static example sensor data should be reachable through the runtime API.
3. Reauth and certificate registration must use the actual independently authenticated legacy CA; never send an account password into the current unconfigured reader or save a password in the config entry.
4. Coordinator rejects stale (>180s), future (>30s), partial, nonnumeric and wrong-device readings and marks entities unavailable upon update failure.
5. Test coordinator/flow/entities on real HA Core or HA test framework before moving to `custom_components/genvex_remote`.
6. SDK redistribution permission and Home Assistant packaging must be resolved.

The separate [certification prototype](../genvex_remote/enrollment_core.py) and [runtime test App](../../haos-apps/genvex-nabto-runtime-test/DOCS.md) provide earlier validated building blocks. The 51/51 offline Python test suite was validated on HAOS, **before** this HA scaffold; it is not evidence that the new Home Assistant files themselves have passed HA startup tests.

To run parser and mocked HTTP consumer tests without Home Assistant installed:

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p "test_*.py" -v
```


## Measurement-age grace policy (development branch, 22 November 2026)

The coordinator now retains the last validated five-value measurement during
temporary transport or schema failures. The grace period is **600 seconds from
the original device snapshot timestamp**, not 600 seconds from a failed poll or
a repeated cached HTTP response. During grace, the five measurement entities
remain available with the last confirmed values; after expiry they become
unavailable. A later valid snapshot restores availability automatically.

An additional read-only diagnostic sensor, **Data age**, reports elapsed
minutes since that original measurement and refreshes with the coordinator's
60-second cycle. This entity is intended for optional dashboard display in
neutral styling, without alert-color transitions at 3 minutes. A fresh
measurement is still required for initial integration setup.

This code is not proof of deployment to HAOS. The previously deployed five
measurement entities and DEV4 App are separate from this new source change.
