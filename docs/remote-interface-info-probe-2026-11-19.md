# Read-only get_interface_info.json experiment — 2026-11-19

Baseline: [verified facts](remote-nabto-verified-facts.md).

## Evidence reported by user

Standalone Linux x86_64 Python/ctypes legacy Nabto 4 SDK test, with the previously working CA-signed RSA-1024 profile:

| Operation | Status |
| --- | ---: |
| nabtoStartup | 0 |
| nabtoInstallDefaultStaticResources | 0 |
| nabtoOpenSession | 0 |
| nabtoRpcSetDefaultInterface | 0 |
| nabtoRpcInvoke(.../get_interface_info.json) | **26** |
| nabtoCloseSession | 0 |
| nabtoShutdown | 0 |
| Temporary profile cleanup | YES |

No controller settings changed. Successful remote `ping.json` / query 17 on both Steam Deck and emulated HAOS remains independently verified.

## Important interpretation correction

The Nabto C API enum defines **`26 = NABTO_FAILED_WITH_JSON_MESSAGE`**: a detailed error may be in the returned JSON pointer, and the caller must free it using `nabtoFree`. The experiment's code invoked `take(response_ptr)` but, on a nonzero status, **discarded the resulting text**. Therefore we cannot yet say whether the operation was rejected for an absent local XML query, unsupported device capability, or another reason.

Critically, the supplied client XML contained **only `ping.json` / numeric ID 17**, not a `get_interface_info.json` query. Nabto's documented RPC invocation normally uses the client-side XML model to resolve query names into numeric IDs. Thus a local interface-definition rejection is a plausible explanation and **the experiment did not establish that any request reached the gateway**.

Nabto CLI's `checkInterface()` invokes `get_interface_info.json` only under optional strict interface checking and when an expected interface ID/version is provided. This convention does not make the operation universally supported. Do not guess numeric IDs to force it.

## Next action

Use a *single local-only* diagnostic or, if re-running with the legitimate profile, print only a sanitized/whitelisted status category from the JSON diagnostic. Do not log the full response or sensitive contents. First verify from upstream SDK/CLI code whether `get_interface_info.json` is registered internally or relies on the externally supplied XML. Avoid interpreting status 26 as an unsupported gateway function until the detailed error is classified.

Sources:
- https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h
- https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp

## Further upstream verification (2026-11-19)

The official Nabto Cordova error table maps specific P2P errors including `P2P_NO_SUCH_REQUEST = 3227` (request absent in interface or resource not found), `P2P_INTERFACE_DEF_INVALID = 3223`, and `P2P_RPC_INTERFACE_NOT_SET = 3267`; it also distinguishes the device-side `EXC_INV_QUERY_ID = 4007`. These are *mapping hints*, not proof that a particular numeric code will appear in this SDK's JSON diagnostic.

Source: https://github.com/nabto/cordova-plugin-nabto/blob/master/www/nabto-error.js

The official CLI's `checkInterface()` invokes `get_interface_info.json` in the strict-check path after registering an externally supplied XML interface; the implementation **does not supply a get_interface_info query in that function**. So it remains possible that the SDK recognizes the convention specially or that the externally registered interface must contain the query elsewhere. The diagnostic JSON is decisive and should be captured **only as a whitelisted error category and code**, not raw output.

Source: https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp

## Repeat test with expanded classifier (user output, 2026-11-19)

A second test used the same known-good identity, SDK and client XML. All initialization steps and shutdown again returned 0. `nabtoRpcInvoke` again returned `26`, and the classifier printed `OTHER_JSON_ERROR` with `Diagnostic codes: []`. The JSON was discarded after a narrow code/message scan; this **still does not establish whether a remote request reached the gateway**. The upstream Cordova error object uses nested `error.body`, `error.header`, and `error.event` fields that the initial classifier did not inspect.

Prepared a narrow follow-up test: [`scripts/diagnose_remote_interface_info.py`](../scripts/diagnose_remote_interface_info.py) inspects these additional fields, prints only categorical results and numeric codes, uses the pre-existing profile, and does not log raw JSON or identity data. It has **not yet been executed**. This is a diagnostic utility, not a product client.
