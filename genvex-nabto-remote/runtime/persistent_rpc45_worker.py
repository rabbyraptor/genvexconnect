#!/usr/bin/env python3
"""Opt-in read-only RPC45 worker: one Nabto SDK process and session.

Private stdin JSON credentials on the first line; then only POLL/CLOSE.
Output is one bounded JSON protocol frame per command. No import side effects.
"""
from __future__ import annotations

import ctypes as ct
from datetime import datetime, timezone
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from raw_registers_v3 import OPTIONAL_ADDRESSES, make_raw_v3

READY = "GENVEX_PERSISTENT_READY="
RESULT = "GENVEX_PERSISTENT_RESULT="
SENSORS = (
    (20, "supply_air", 10, -300),
    (21, "outdoor_air", 10, -300),
    (22, "exhaust_air", 10, -300),
    (23, "extract_air", 10, -300),
    (26, "humidity", 1, 0),
)
SCHEMA = b"""<unabto_queries>
<query name="candidate_read_datapoints.json" id="45">
  <request><list name="datapoints">
    <parameter name="obj" type="uint8"/>
    <parameter name="address" type="uint32"/></list>
    <parameter name="trailer" type="uint8" default="1"/>
  </request>
  <response format="json"><list name="values">
    <parameter name="value" type="int16"/></list>
  </response>
</query></unabto_queries>"""


def emit(prefix: str, obj: dict) -> None:
    print(prefix + json.dumps(obj, separators=(",", ":"), allow_nan=False), flush=True)


def config_from_stdin() -> tuple[str, str, str, Path]:
    raw = sys.stdin.buffer.readline(4097)
    if not raw.endswith(b"\n") or len(raw) > 4096:
        raise ValueError("Invalid config length")
    data = json.loads(raw)
    if type(data) is not dict or set(data) != {"identity", "host", "passphrase"}:
        raise ValueError("Invalid config fields")
    identity, host, secret = (data[k] for k in ("identity", "host", "passphrase"))
    if (type(identity) is not str or len(identity) > 256
            or re.fullmatch(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+", identity) is None
            or type(host) is not str
            or re.fullmatch(r"[0-9]{12}\.remote\.lscontrol\.dk", host) is None
            or type(secret) is not str or not 1 <= len(secret) <= 1024
            or any(c in secret for c in "\r\n\x00")):
        raise ValueError("Invalid config values")
    profile = Path(os.environ["GENVEX_NABTO_PROFILE"])
    if not (profile / "client.crt").is_file() or not (profile / "client-encrypted.key").is_file():
        raise ValueError("Missing profile")
    return identity, host, secret, profile


def rpc_url(host: str) -> bytes:
    body = {"request": {"datapoints": [
        {"obj": 0, "address": spec[0]} for spec in SENSORS
    ], "trailer": 1}}
    return ("nabto://" + host + "/candidate_read_datapoints.json?json="
            + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()


def raw_rpc_url(host: str) -> bytes:
    """Read only the twelve previously observed candidate addresses."""
    if OPTIONAL_ADDRESSES != (
        24, 18, 19, 35, 36, 41, 42, 53, 40, 114, 115, 50
    ):
        raise ValueError("Unexpected raw register list")
    body = {"request": {"datapoints": [
        {"obj": 0, "address": address} for address in OPTIONAL_ADDRESSES
    ], "trailer": 1}}
    return ("nabto://" + host + "/candidate_read_datapoints.json?json="
            + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()


def decode_raw_rpc(raw: str, count: int) -> tuple[int, ...] | None:
    """Reject partial, reordered-count or malformed signed int16 responses."""
    try:
        if type(raw) is not str or len(raw) > 4096:
            return None
        values = json.loads(raw)["response"]["values"]
        if type(values) is not list or len(values) != count:
            return None
        decoded = []
        for item in values:
            if type(item) is not dict or set(item) != {"value"}:
                return None
            value = item["value"]
            if type(value) is not int or not -32768 <= value <= 32767:
                return None
            decoded.append(value)
        return tuple(decoded)
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def decode_batch(raw: str) -> dict[str, float] | None:
    values = decode_raw_rpc(raw, len(SENSORS))
    if values is None:
        return None
    return {
        key: (value + offset) / divisor
        for value, (_, key, divisor, offset) in zip(values, SENSORS)
    }


def numeric_error_event(raw: str) -> int | None:
    """Extract only the numeric Nabto error event; discard all raw strings."""
    if type(raw) is not str or len(raw) > 4096:
        return None
    try:
        parsed = json.loads(raw)
        if type(parsed) is not dict:
            return None
        error = parsed.get("error")
        if type(error) is not dict:
            return None
        event = error.get("event")
        if type(event) is int and 0 <= event <= 10000000:
            return event
    except (ValueError, TypeError):
        pass
    return None


def record_error_event(status: int, raw: str) -> None:
    """Record bounded non-secret event metadata outside the worker protocol."""
    if status != 26:
        return
    event = numeric_error_event(raw)
    if event is None:
        return
    record = json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sdk_status": status,
        "event": event,
    }, separators=(",", ":")) + "\n"
    try:
        fd = os.open(
            "/data/rpc45_json_diagnostic.log",
            os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "a", encoding="ascii") as output:
            if os.fstat(output.fileno()).st_size <= 1048576:
                output.write(record)
    except OSError:
        pass


def main() -> int:
    if sys.argv[1:] != ["--serve-stdio"]:
        return 2
    try:
        identity, host, secret, profile = config_from_stdin()
        dll = ct.CDLL("/opt/nabto/libnabto_client_api.so")
    except Exception:
        emit(READY, {"ok": False, "stage": "SDK_STARTUP_FAILED"})
        return 2

    P, C = ct.c_void_p, ct.c_char_p

    def api(name, arguments):
        function = getattr(dll, name)
        function.argtypes = arguments
        function.restype = ct.c_int
        return function

    try:
        startup = api("nabtoStartup", [C])
        resources = api("nabtoInstallDefaultStaticResources", [C])
        open_session = api("nabtoOpenSession", [ct.POINTER(P), C, C])
        set_interface = api("nabtoRpcSetDefaultInterface", [P, C, ct.POINTER(P)])
        invoke = api("nabtoRpcInvoke", [P, C, ct.POINTER(P)])
        close_session = api("nabtoCloseSession", [P])
        shutdown = api("nabtoShutdown", [])
        dll.nabtoFree.argtypes = [P]
        dll.nabtoFree.restype = None
    except Exception:
        emit(READY, {"ok": False, "stage": "SDK_STARTUP_FAILED"})
        return 2

    def take(pointer):
        if not pointer.value:
            return ""
        try:
            return ct.string_at(pointer).decode("utf-8", "replace")
        finally:
            dll.nabtoFree(pointer)

    session = P()
    started = opened = ready = False
    stage = "SDK_STARTUP_FAILED"
    try:
        with tempfile.TemporaryDirectory(prefix="genvex-persistent-worker-") as folder:
            users = Path(folder) / "users"
            users.mkdir(mode=0o700)
            stem = identity.replace("@", "_at_")
            for source, suffix in (
                (profile / "client.crt", ".crt"),
                (profile / "client-encrypted.key", ".key"),
            ):
                dest = users / (stem + suffix)
                shutil.copyfile(source, dest)
                dest.chmod(0o600)
            if startup(folder.encode()) != 0:
                raise RuntimeError()
            started = True
            stage = "SDK_RESOURCES_FAILED"
            if resources(None) != 0:
                raise RuntimeError()
            stage = "SDK_SESSION_FAILED"
            if open_session(ct.byref(session), identity.encode(), secret.encode()) != 0:
                raise RuntimeError()
            opened = True
            stage = "SDK_XML_FAILED"
            error = P()
            xml_status = set_interface(session, SCHEMA, ct.byref(error))
            take(error)
            if xml_status != 0:
                raise RuntimeError()
            emit(READY, {"ok": True})
            ready = True
            url = rpc_url(host)
            optional_url = raw_rpc_url(host)
            while True:
                command = sys.stdin.buffer.readline(16)
                if not command or command == b"CLOSE\n":
                    break
                if command != b"POLL\n":
                    break
                response = P()
                start = time.monotonic()
                status = invoke(session, url, ct.byref(response))
                elapsed = round((time.monotonic() - start) * 1000)
                raw = take(response)
                if type(status) is not int or not 0 <= status <= 100000:
                    break
                if status:
                    record_error_event(status, raw)
                    emit(RESULT, {"ok": False, "status": status, "elapsed_ms": elapsed})
                    continue
                values = decode_batch(raw)
                if values is None:
                    emit(RESULT, {"ok": False, "status": 0, "elapsed_ms": elapsed})
                    continue
                measured_at = datetime.now(timezone.utc)
                if command == b"POLL3\\n":
                    baseline_raw = decode_raw_rpc(raw, len(SENSORS))
                    extra_raw = None
                    response2 = P()
                    try:
                        # Optional RPC is serial. Its failure must not lose
                        # the already validated mandatory five measurements.
                        extra_status = invoke(session, optional_url, ct.byref(response2))
                        extra_body = take(response2)
                        if extra_status == 0:
                            extra_raw = decode_raw_rpc(
                                extra_body, len(OPTIONAL_ADDRESSES),
                            )
                        else:
                            record_error_event(extra_status, extra_body)
                    except Exception:
                        extra_raw = None
                    try:
                        document = make_raw_v3(
                            device_id=host.split(".")[0],
                            measured_at=measured_at,
                            baseline_raw=baseline_raw,
                            additional_raw=extra_raw,
                        )
                    except Exception:
                        emit(RESULT, {
                            "ok": False, "status": 0, "elapsed_ms": elapsed,
                        })
                        continue
                else:
                    document = {
                        "schema_version": 1,
                        "device_id": host.split(".")[0],
                        "timestamp_utc": measured_at.isoformat(),
                        "health": "ok",
                        "values": values,
                    }
                emit(RESULT, {"ok": True, "snapshot": document})
        return 0
    except Exception:
        if not ready:
            emit(READY, {"ok": False, "stage": stage})
        return 3
    finally:
        if opened:
            try:
                close_session(session)
            except Exception:
                pass
        if started:
            try:
                shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
