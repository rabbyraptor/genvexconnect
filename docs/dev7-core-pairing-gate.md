# DEV7 — opt-in Core Supervisor pairing (source only)

**Dependency:** DEV5 source-parity draft PR #4. This branch contains no
HAOS deployment or automatic certificate enrollment.

## Implemented

- `core_supervisor_loader.async_fetch_paired_token(hass, device_id=...)`
  calls Home Assistant Core's authenticated
  `get_supervisor_client(hass).addons.addon_info("local_genvex_nabto_remote")`
  API. Core's Supervisor connection handles authentication.
  No user-selected URL, generic Supervisor bearer token or external HTTP
  request is involved. The adapter projects only `slug`, `state`,
  `options.device_id` and `options.ipc_token`.
- `supervisor_pairing.async_load_app_ipc_token` validates the pinned App slug,
  `started` state, 12-digit device identity and bounded IPC-token format.
  A ten-second timeout and sanitized failures prevent secret-bearing backend
  exception text from reaching the config flow.
- The config flow adds a **disabled-by-default**, explicit
  `pair_from_app` checkbox. Selecting it loads the matching token from
  Core's Supervisor connection; otherwise a manually entered IPC token is
  still accepted. The App endpoint is fixed, never user-editable.
- English and Danish config-flow labels and error messages are updated.

## Verification

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m compileall -q experimental/home_assistant/custom_components/genvex_remote
```

Unit tests use a fake Supervisor client and check one fixed App slug,
successful pairing, invalid device ID, wrong/stopped App, missing token,
mismatched identity, sanitized transport errors, and cancellation. Source
contracts ensure that the manual fallback and fixed endpoint remain.

**Not yet verified in HA Core:** the actual installed Supervisor's options
visibility, import compatibility across the target HAOS Core version, and
entry-creation UI behavior. The CI checks operate without running Core;
passing them does not establish production pairing.

## Remaining work

1. Test the proposed Core path on the exact installed HA Core version,
   including a started App with matching options and network access to the
   pinned snapshot endpoint.
2. Verify token refresh/rotation and stopped-App recovery. Existing HA config
   entries hold a copied IPC token and do not automatically update on rotation.
3. Integrate the separate trusted legacy CA enrollment and private profile
   lifecycle before claiming fully automatic onboarding.
4. Once accepted, deploy via the normal reviewed development process.

The existing manual IPC-token option and five-sensor v1 runtime remain
unchanged on the installed HAOS.
