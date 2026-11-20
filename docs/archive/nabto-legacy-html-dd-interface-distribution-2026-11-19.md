# Nabto 4 official sources: where remote RPC interfaces come from

Date: 2026-11-19  
Status: source-level findings; **not** a recovered production Genvex interface.

## Key architectural discovery: centrally distributed HTML Device Driver (HTML-DD)

The upstream Nabto Cordova README explicitly says the `unabto_queries.xml` used with `rpcSetInterface` / `rpcSetDefaultInterface` was **formerly distributed centrally through HTML-DD bundles** in the `nabto` subdirectory. The upstream `nabto/unabto/apps/html_device_driver/README.txt` documents a ZIP package containing:

```text
html_dd.zip
├── nabto/
│   └── unabto_queries.xml
└── static/
    ├── css/
    ├── img/
    ├── index.html
    ├── js/
    └── libs/
```

The README says the Nabto Plugin historically downloads this ZIP *from the server* when connecting to a uNabto device and that a developer uploaded such bundles through the Nabto Portal. This is an **important alternative to the assumption that the Genvex production XML must reside inside the physical gateway or phone**. Legacy deployments could have registered the query model centrally.

This historical mechanism is deprecated in modern Cordova plugin usage. **It does not prove that an accessible LS Control HTML-DD bundle still exists in 2026**, that the current mobile application uses it, or that Nabto's newer Client SDK can automatically retrieve it. No LS Control production bundle was recovered in this investigation.

Sources:
- https://github.com/nabto/cordova-plugin-nabto/blob/master/README.md (RPC interface setup)
- https://github.com/nabto/unabto/blob/master/apps/html_device_driver/README.txt

## RPC versus fetching files

The public legacy C API header exposes `nabtoRpcSetDefaultInterface`, `nabtoRpcSetInterface`, `nabtoRpcInvoke`, plus a separate deprecated `nabtoFetchUrl`. These are **different API calls**: `nabtoRpcInvoke` needs a client-side XML model, while `nabtoFetchUrl` is the historical HTML-DD-style URL fetch. The header does not promise that `nabtoFetchUrl` can retrieve a device's registered query model. In particular, do not assume `nabto://<device>/nabto/unabto_queries.xml` is valid on Genvex.

Source: https://github.com/nabto/nabto4-python-wrapper/blob/master/extension/linux64/include/nabto_client_api.h

## Optional strict-interface metadata is not the query model

In `nabto/nabto-cli/src/nabto_cli.cpp`, `checkInterface()` issues the built-in/convention-based `nabto://<host>/get_interface_info.json` and compares the returned `interface_id`, `interface_version_major`, `interface_version_minor` against caller-supplied expected values. This is **interface identification only**. It does not list query names, numeric RPC query IDs, response types, or controller registers.

The function is only used if `--strict-interface-check` is enabled; our successful `ping.json` runs did not enable it. Device support is **unverified**. Lack of support would not undermine our successful ping.

Source: https://github.com/nabto/nabto-cli/blob/master/src/nabto_cli.cpp

## What a manufacturer-specific RPC interface requires

Nabto's `unabto/TESTING.md` states an RPC operation must be defined in the client-side `unabto_queries.xml` **and** implemented by the uNabto device's `application_event()` handler. Nabto's official LS Control Cordova test app includes only **query 17** (`ping.json`); other demo XML files are for their respective demo firmware and are not safe guesses for Optima 270.

Sources:
- https://github.com/nabto/unabto/blob/master/TESTING.md
- https://github.com/nabto/cordova-lsc-test/blob/master/www/js/index.js

## Decision

1. Prefer recovering the actual LS Control production client interface from a legitimately obtained mobile app package, provisioned HTML-DD asset, or direct vendor documentation.
2. The only *verified on this unit* remote RPC remains `ping.json` / ID 17; telemetry, fan control, setpoints remain **OPEN**.
3. A separate, strictly read-only test of `get_interface_info.json` is reasonable for metadata, **not** a claim of automatic interface enumeration; if attempted, whitelist just interface ID/version and status and time-limit it.
4. Do not try a sequence of guessed RPC IDs; maintain the already-working HAOS QEMU/Steam Deck reference and local HA integration intact.

Cross-references: [verified facts](../remote-nabto-verified-facts.md) · [RPC and ARM64 plan](remote-nabto-next-steps.md).
