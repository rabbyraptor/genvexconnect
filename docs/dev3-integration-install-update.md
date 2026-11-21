# DEV3 Home Assistant integration: source installation and upgrades

**Experimental (2026-11-21).** The operator's HAOS already runs the
separate `genvex_remote` integration and the DEV3
`local_genvex_nabto_remote` App. Live RPC45, sensor unavailability/recovery,
Core restart and translated English sensor names were verified. The
30-minute and 24-hour soak tests are deferred.

## Source packaging

`genvex-nabto-remote/scripts/haos_install_remote_component.py`
copies exactly eleven files from
`experimental/home_assistant/custom_components/genvex_remote/`:

```text
__init__.py
config_flow.py
const.py
coordinator.py
manifest.json
runtime_client.py
sensor.py
snapshot.py
strings.json
translations/en.json
translations/da.json
```

The installer validates the source Python, manifest, matching five entity
keys and both language bundles. Missing `en.json` blocks installation.
This source installer is separate from the Supervisor App distribution.

## New installation

From a reviewed checkout, point `--source` at the folder above
and `--config` at the HAOS configuration directory
(`/mnt/data/supervisor/homeassistant` on the host):

```sh
python3 genvex-nabto-remote/scripts/haos_install_remote_component.py \
  --source experimental/home_assistant/custom_components/genvex_remote \
  --config /mnt/data/supervisor/homeassistant
```

This performs a **read-only preflight** by default. Add `--install`
for an approved new install. Existing integrations are not overwritten.

## Upgrading the existing remote integration

Use `--upgrade-preflight` for a read-only check, then `--upgrade`
only after reviewing the intended source revision and host backup:

```sh
python3 genvex-nabto-remote/scripts/haos_install_remote_component.py \
  --source experimental/home_assistant/custom_components/genvex_remote \
  --config /mnt/data/supervisor/homeassistant \
  --upgrade-preflight
```

The explicit `--upgrade` mode stages a validated complete replacement
and retains the old component as
`custom_components/.genvex_remote-upgrade-backup`. If publishing the
new component fails, it attempts to restore the previous directory.
A leftover backup blocks further upgrades until reviewed. The update
does not modify Home Assistant's entity/config/device registries or the
separate `genvex_connect` LAN component. Restart Home Assistant Core
after the approved update so Python and translations reload.

**The new upgrade procedure has not been performed on live HAOS yet.**
The rollback feature is verified by simulated filesystem failures in
offline tests, not by a live restoration of a broken installation.
Future rollback must be an explicitly reviewed separate host action.

## Post-install verification

Check one enabled config entry, one device, five registered numeric
sensors and unchanged entity IDs. In Home Assistant `en`, expected
names include `Genvex Connect Remote Supply air` and
`Genvex Connect Remote Exhaust air`; the Home Assistant translation
loader has also verified all five Danish counterparts.

The current operator's entity-ID signature is `2be9240972de0a9d`.
It is host-specific and must not be assumed for other installations.

## Outstanding release blockers

Proprietary x86_64 Micro Nabto SDK redistribution rights, user-friendly
secure enrollment, unattended App lifecycle, soak validation and fully
tested upgrades across different HAOS installations remain open.
