# DEV7 — trusted Core pairing gate (source only)

**Dependency:** DEV5 source-parity draft PR #4. This change deliberately does
not start certificate enrollment, access Supervisor credentials itself or
change the installed HA config flow.

The existing `supervisor_pairing.extract_app_ipc_token` validates that a
Core-obtained Supervisor response describes the fixed, started Genvex Remote
App and the expected 12-digit device ID. New
`async_load_app_ipc_token(load_app_info, expected_device_id=...)` runs a
**trusted injected** metadata loader with a bounded deadline, always requests
only `local_genvex_nabto_remote`, and returns a token only after validation.

This function cannot read HAOS Supervisor API on its own: the final Core-side
transport must provide the independently authenticated loader. We have not
implemented or live-verified such a loader in this PR.

## Verification

```sh
python3 -m unittest discover -s experimental/home_assistant/tests -p 'test_*.py' -v
python3 -m compileall -q experimental/home_assistant/custom_components/genvex_remote
```

The tests cover a matching device, a wrong device, invalid inputs before any
Supervisor call, sanitized backend errors, deadlines and cancellation.

## Next gate before automatic onboarding

1. Implement and test a Core-privileged Supervisor metadata adapter using
   supported Home Assistant interfaces, with explicitly bounded reads.
2. Verify token synchronization, rotation and unavailable-App recovery.
3. Separately verify trusted legacy CA enrollment and private profile
   provisioning; the existing injected enrollment prototype is not yet wired
   to a production credential path.
4. Test actual HA Core config flow and successful five-value snapshot on HAOS.

Neither a token alone nor a passing synthetic test establishes end-to-end
onboarding. No live configuration or device state was modified.
