#!/usr/bin/env python3
"""One manual live RPC45 -> actual HA reader/coordinator/sensor-class probe.

Imports the source-only integration into a separate, short-lived Python
interpreter INSIDE the running Core container, entirely in memory. It does
NOT install the integration, create HA registry entries, alter Core's running
process, enable polling, or add persistent credentials/configuration.
Reuses the pinned, credential-safe Docker launcher and its single RPC45 read.
"""
from __future__ import annotations

from pathlib import Path
import sys

import haos_core_live_once_operator as base

STAGING = Path("/tmp/genvex-dev3-once")
COMPONENT = STAGING / "ha_component"
MODULES = ("const", "runtime_client", "snapshot", "coordinator", "sensor")
SUCCESS = 'print("PASS: one real Genvex RPC45 snapshot reached HA Core over private HTTP")'

# Appended after the existing four real HTTP checks (401,401,200,404).
# The token and device ID remain in the existing bounded Docker stdin only.
# No private material, sensor readings or traceback can reach stdout.
HA_CLASSES_PROBE = r"""
phase = "HA_IMPORT"
try:
    import asyncio
    import importlib
    import ipaddress
    import socket
    import types

    from aiohttp import ClientSession, TCPConnector
    from aiohttp.abc import AbstractResolver

    # This namespace exists only in the isolated python3 -c process, not in
    # the persistent Home Assistant Core interpreter or its import registry.
    package = "genvex_remote_probe"
    root = types.ModuleType(package)
    root.__path__ = []
    sys.modules[package] = root
    for module_name in ("const", "runtime_client", "snapshot", "coordinator", "sensor"):
        fullname = package + "." + module_name
        mod = types.ModuleType(fullname)
        mod.__package__ = package
        sys.modules[fullname] = mod
        exec(compile(SOURCES[module_name], "<read-only-ha-module>", "exec"), mod.__dict__)

    phase = "HA_MODULES"
    const = importlib.import_module(package + ".const")
    runtime_client = importlib.import_module(package + ".runtime_client")
    coordinator_module = importlib.import_module(package + ".coordinator")
    sensor_module = importlib.import_module(package + ".sensor")

    if len(const.SENSORS) != 5 or {
        spec.key for spec in const.SENSORS
    } != {"supply_air", "outdoor_air", "exhaust_air", "extract_air", "humidity"}:
        raise ValueError("Unexpected sensor contract")

    if not isinstance(ipaddress.ip_address(target), ipaddress.IPv4Address):
        raise ValueError("Expected private IPv4 runtime")

    target_port = port

    class OnlyPrivateRuntimeResolver(AbstractResolver):
        async def resolve(self, host, port=0, family=socket.AF_INET):
            if (host, port) != ("local-genvex-nabto-remote", 18275):
                raise OSError("Unexpected hostname")
            return [{
                "hostname": host, "host": target, "port": target_port,
                "family": socket.AF_INET, "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }]

        async def close(self):
            pass

    async def verify_actual_ha_classes():
        global phase
        phase = "HA_CONNECTOR"
        connector = TCPConnector(
            resolver=OnlyPrivateRuntimeResolver(),
            use_dns_cache=False, force_close=True,
        )
        async with ClientSession(connector=connector, trust_env=False) as session:
            reader = runtime_client.AuthenticatedSnapshotReader(
                session,
                endpoint=runtime_client.EXPECTED_APP_ENDPOINT,
                token=token,
            )
            # This performs the actual production HA coordinator's snapshot
            # fetch + freshness, ID, completeness and numeric validation.
            # None is safe here: no Core lifecycle or polling is started;
            # _async_update_data() has no HomeAssistant side effects.
            phase = "HA_COORDINATOR"
            coordinator = coordinator_module.GenvexRemoteCoordinator(
                None, device, reader,
            )
            phase = "HA_READER"
            readings = await coordinator._async_update_data()
            if set(readings) != {spec.key for spec in const.SENSORS}:
                raise ValueError("Incomplete real HA coordinator snapshot")
            phase = "HA_SENSORS"
            coordinator.data = readings
            entities = [
                sensor_module.GenvexRemoteSensor(coordinator, spec)
                for spec in const.SENSORS
            ]
            if len({item.unique_id for item in entities}) != 5:
                raise ValueError("Duplicate entity unique IDs")
            if any(
                type(item.native_value) not in (int, float)
                or item.native_value != readings[spec.key]
                for item, spec in zip(entities, const.SENSORS)
            ):
                raise ValueError("Invalid real sensor class projection")

    phase = "HA_ASYNC"
    asyncio.run(verify_actual_ha_classes())
except Exception:
    # The parent operator only accepts this fixed diagnostic category.
    print("CORE_PROBE_FAILED:" + phase, flush=True)
    raise SystemExit(2)
"""


def read_reviewed_sources() -> dict[str, str]:
    base.check_file(STAGING, 0o700, directory=True)
    base.check_file(COMPONENT, 0o700, directory=True)
    # python3 -m py_compile creates __pycache__ alongside the five
    # reviewed source files. Ignore only that inert directory; never load
    # bytecode and still reject all unexpected source files or symlinks.
    expected = {name + ".py" for name in MODULES}
    entries = {entry.name: entry for entry in COMPONENT.iterdir()}
    extra = set(entries) - expected
    if extra == {"__pycache__"}:
        cache = entries["__pycache__"]
        owner = COMPONENT.stat().st_uid
        info = cache.lstat()
        import stat
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != owner
            or info.st_mode & 0o022
        ):
            raise ValueError("Unsafe compiled-bytecode directory")
    elif extra:
        raise ValueError("Unexpected staged HA source names")
    if not expected.issubset(entries):
        raise ValueError("Missing reviewed HA module")
    result: dict[str, str] = {}
    total = 0
    for name in MODULES:
        path = COMPONENT / (name + ".py")
        base.check_file(path, 0o600)
        if not 0 < path.stat().st_size <= 24000:
            raise ValueError("Unsafe HA component source size")
        content = path.read_text(encoding="utf-8")
        total += len(content.encode("utf-8"))
        compile(content, "<reviewed-ha-module>", "exec")
        result[name] = content
    if total > 75000:
        raise ValueError("Unexpected staged HA source size")
    return result


def build_core_client(sources: dict[str, str]) -> str:
    """Append an in-memory HA class probe to the known-good Core HTTP client."""
    if set(sources) != set(MODULES):
        raise ValueError("Unexpected HA module set")
    if base.CORE_CLIENT.count(SUCCESS) != 1:
        raise ValueError("Unexpected original Core proof marker")
    # Only reviewed source code goes into -c argv. All credentials, including
    # the random bearer token, remain exclusively on docker exec stdin.
    injected = "SOURCES = " + repr(sources) + "\n" + HA_CLASSES_PROBE
    script = base.CORE_CLIENT.replace(SUCCESS, injected + "\n" + SUCCESS)
    compile(script, "<temporary-HA-Core-live-probe>", "exec")
    if len(script.encode("utf-8")) > 110000:
        raise ValueError("Unexpected Core probe size")
    return script


def main() -> int:
    if sys.argv[1:]:
        print("BLOCKED: unsupported options", flush=True)
        return 1
    try:
        sources = read_reviewed_sources()
        base.CORE_CLIENT = build_core_client(sources)
        base.CORE_FAILURE_PHASES = base.CORE_FAILURE_PHASES | {
            "HA_IMPORT", "HA_MODULES", "HA_ASYNC", "HA_CONNECTOR",
            "HA_COORDINATOR", "HA_READER", "HA_SENSORS",
        }
        result = base.main()
        if result == 0:
            print("PASS: real snapshot validated by actual HA reader, coordinator and five sensor classes", flush=True)
        return result
    except (KeyboardInterrupt, Exception):
        print("BLOCKED: HA_COMPONENT_STAGE_OR_PROBE_INVALID", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
