#!/usr/bin/env python3
"""Optima 270: isolated, opt-in READ-ONLY Micro Nabto RPC42 fan-level probe.

Runs against an existing authorized legacy Nabto profile on Linux x86_64.
One query ID 42, source read-object 0, read-address 7. Never registers
or sends RPC43. No credentials, hostnames, raw response or XML errors are logged.
This candidate is NOT vendor-confirmed or installed in the live HAOS app.
"""
from __future__ import annotations

import ctypes as ct
import getpass
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path.home()
PROFILE = ROOT / ".local/share/genvex-nabto-profile-1024-test"
LIB = ROOT / "genvex-ca-check/libnabto_client_api.so"
HERE = Path(__file__).resolve().parents[1]
XML = HERE / "tests/fixtures/candidate_readonly_query42.xml"
IDENTITY = os.environ.get("GENVEX_NABTO_IDENTITY", "")
HOST = os.environ.get("GENVEX_NABTO_HOST", "")
PREFIX = "RPC42_"

def report(key: str, value) -> None:
    print(f"{PREFIX}{key}: {value}", flush=True)

def numeric_error_event(raw: str) -> int | None:
    try:
        document = json.loads(raw)
        if type(document) is dict:
            error = document.get("error")
            if type(error) is dict:
                event = error.get("event")
                if type(event) is int and 0 <= event <= 10_000_000:
                    return event
    except (TypeError, ValueError):
        pass
    return None

def main() -> int:
    if not (re.fullmatch(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+", IDENTITY)
            and re.fullmatch(r"[0-9]{12}\.remote\.lscontrol\.dk", HOST)):
        report("PREFLIGHT", "MISSING_IDENTITY_OR_HOST_ENV")
        return 2
    cert, key = PROFILE / "client.crt", PROFILE / "client-encrypted.key"
    if not (cert.is_file() and key.is_file() and LIB.is_file() and XML.is_file()):
        report("PREFLIGHT", "SDK_PROFILE_OR_XML_NOT_FOUND")
        return 2

    from reconstruct_rpc42_readonly import candidate_query, request_bytes
    # Fail closed if the XML has been changed to a write query or wrong wire shape.
    candidate_query()
    expected = request_bytes((7,))
    if expected.hex() != "0000002a000100000701":
        report("PREFLIGHT", "OFFLINE_REQUEST_MISMATCH")
        return 2

    # A single query-model entry ID 42, NO write operation.
    rpc_xml = XML.read_bytes()
    if b'id="43"' in rpc_xml or b"setpoint_writelist" in rpc_xml.lower():
        report("PREFLIGHT", "UNEXPECTED_WRITER")
        return 2
    body = {"request": {"setpoints": [{"obj": 0, "address": 7}], "trailer": 1}}
    url = ("nabto://" + HOST + "/candidate_read_setpoints.json?json="
           + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()

    password = getpass.getpass("Existing encrypted Nabto key passphrase: ")
    if not password:
        report("PREFLIGHT", "EMPTY_PASSPHRASE")
        return 2

    P, C = ct.c_void_p, ct.c_char_p
    sdk = ct.CDLL(str(LIB))
    def api(name, arguments):
        fn = getattr(sdk, name)
        fn.argtypes = arguments
        fn.restype = ct.c_int
        return fn
    startup = api("nabtoStartup", [C])
    resources = api("nabtoInstallDefaultStaticResources", [C])
    open_session = api("nabtoOpenSession", [ct.POINTER(P), C, C])
    set_interface = api("nabtoRpcSetDefaultInterface", [P, C, ct.POINTER(P)])
    invoke = api("nabtoRpcInvoke", [P, C, ct.POINTER(P)])
    close_session = api("nabtoCloseSession", [P])
    shutdown = api("nabtoShutdown", [])
    sdk.nabtoFree.argtypes = [P]
    sdk.nabtoFree.restype = None

    def consume(ptr):
        if not ptr.value:
            return ""
        try:
            return ct.string_at(ptr).decode("utf-8", "replace")
        finally:
            sdk.nabtoFree(ptr)

    report("OPERATION", "READ_ONLY_RPC42_SETPOINT_ADDRESS_7")
    session = P()
    started = opened = False
    try:
        with tempfile.TemporaryDirectory(prefix="genvex-rpc42-read-") as folder:
            users = Path(folder) / "users"
            users.mkdir(mode=0o700)
            name = IDENTITY.replace("@", "_at_")
            for origin, suffix in ((cert, ".crt"), (key, ".key")):
                target = users / (name + suffix)
                shutil.copyfile(origin, target)
                target.chmod(0o600)

            status = startup(folder.encode())
            report("SDK_STARTUP", status)
            if status:
                return 2
            started = True
            status = resources(None)
            report("SDK_RESOURCES", status)
            if status:
                return 2
            status = open_session(ct.byref(session), IDENTITY.encode(), password.encode())
            report("SDK_SESSION", status)
            if status:
                return 2
            opened = True

            diagnostic = P()
            status = set_interface(session, rpc_xml, ct.byref(diagnostic))
            message = consume(diagnostic)
            report("XML_REGISTER_STATUS", status)
            if status:
                report("XML_EVENT", numeric_error_event(message))
                return 2

            response_ptr = P()
            status = invoke(session, url, ct.byref(response_ptr))
            response = consume(response_ptr)
            report("INVOKE_STATUS", status)
            if status:
                report("INVOKE_EVENT", numeric_error_event(response))
                report("REMOTE_READ_VERIFIED", "NO")
                return 2

            try:
                decoded = json.loads(response)
                values = decoded["response"]["values"]
                prefix = decoded["response"]["prefix_unknown"]
                if (type(prefix) is not int or not 0 <= prefix <= 255
                    or type(values) is not list or len(values) != 1
                    or type(values[0]) is not dict
                    or type(values[0].get("value")) is not int
                    or not 0 <= values[0]["value"] <= 65535):
                    raise ValueError("Unexpected response")
                fan_level = values[0]["value"]
                report("UNKNOWN_RESPONSE_PREFIX", prefix)
                if not 0 <= fan_level <= 4:
                    report("READ_VALUE", "OUT_OF_EXPECTED_LEVEL_RANGE")
                    return 2
                report("FAN_LEVEL", fan_level)
                report("REMOTE_READ_VERIFIED", "YES")
                return 0
            except (ValueError, KeyError, TypeError, AttributeError):
                report("RESPONSE", "SCHEMA_NOT_YET_CONFIRMED")
                return 2
    finally:
        if opened:
            report("SDK_CLOSE", close_session(session))
        if started:
            report("SDK_SHUTDOWN", shutdown())
        report("RPC43_WRITE_ATTEMPTED", "NO")

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, AttributeError, ValueError):
        report("FAILURE", "RUNTIME_PREFLIGHT_OR_SDK_ERROR")
        raise SystemExit(2)
