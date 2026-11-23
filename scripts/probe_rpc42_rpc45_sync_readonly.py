#!/usr/bin/env python3
"""Bracketed read-only RPC42 -> RPC45 -> RPC42 samples, one Nabto session."""
from __future__ import annotations

import ctypes as ct
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import quote
import xml.etree.ElementTree as ET

PROFILE = Path.home() / ".local/share/genvex-nabto-profile-1024-test"
LIB = Path.home() / "genvex-ca-check/libnabto_client_api.so"
ROOT = Path(__file__).resolve().parents[1]
XML42 = ROOT / "tests/fixtures/candidate_readonly_query42.xml"
XML45 = ROOT / "tests/fixtures/candidate_readonly_query45.xml"
REGISTERS = (18, 19, 35, 36)
QUERIES = {42: "candidate_read_setpoints.json", 45: "candidate_read_datapoints.json"}


def output(key, value):
    print(f"SYNC_{key}: {value}", flush=True)


def xml_interface():
    queries = [
        ET.parse(path).getroot().find("query") for path in (XML42, XML45)
    ]
    if any(q is None for q in queries) or [
        (int(q.attrib["id"]), q.attrib["name"]) for q in queries
    ] != [(42, QUERIES[42]), (45, QUERIES[45])]:
        raise ValueError("Unexpected read-only query definition")
    def fields(q, path):
        node = q.find(path)
        if node is None:
            raise ValueError("Missing field list")
        return [(p.get("name"), p.get("type")) for p in node.findall("parameter")]
    if (fields(queries[0], "request/list") !=
            [("obj", "uint8"), ("address", "uint16")]
            or fields(queries[1], "request/list") !=
            [("obj", "uint8"), ("address", "uint32")]
            or fields(queries[0], "response") !=
            [("prefix_unknown", "uint8")]
            or fields(queries[0], "response/list") !=
            [("value", "uint16")]
            or fields(queries[1], "response/list") !=
            [("value", "int16")]):
        raise ValueError("Unexpected read-only field layout")
    root = ET.Element("unabto_queries")
    for query in queries:
        root.append(query)
    return ET.tostring(root, encoding="utf-8")


def request_url(host, query):
    if query == 42:
        data = {"request": {
            "setpoints": [{"obj": 0, "address": 7}], "trailer": 1}}
    elif query == 45:
        data = {"request": {
            "datapoints": [{"obj": 0, "address": a} for a in REGISTERS],
            "trailer": 1}}
    else:
        raise ValueError("Read-only query ID required")
    return ("nabto://" + host + "/" + QUERIES[query] + "?json=" +
            quote(json.dumps(data, separators=(",", ":")), safe="")).encode()


def decode(query, raw):
    if type(raw) is not str or len(raw) > 4096:
        raise ValueError("Unexpected response size")
    data = json.loads(raw)["response"]
    items = data["values"]
    if type(items) is not list or len(items) != (1 if query == 42 else 4):
        raise ValueError("Unexpected result list length")
    values = []
    for item in items:
        if type(item) is not dict or type(item.get("value")) is not int:
            raise ValueError("Unexpected result data type")
        value = item["value"]
        a, b = (0, 65535) if query == 42 else (-32768, 32767)
        if not a <= value <= b:
            raise ValueError("Out-of-range result")
        values.append(value)
    if query == 42:
        prefix = data.get("prefix_unknown")
        if type(prefix) is not int or not 0 <= prefix <= 255:
            raise ValueError("Unexpected reply prefix")
        if not 0 <= values[0] <= 4:
            raise ValueError("Unexpected fan level")
        return values[0]
    return dict(zip(REGISTERS, values))


def error_event(raw):
    try:
        error = json.loads(raw).get("error", {})
        event = error.get("event")
        return event if type(event) is int and 0 <= event <= 10000000 else None
    except (ValueError, TypeError, AttributeError):
        return None


def main():
    identity = os.environ.get("GENVEX_NABTO_IDENTITY", "")
    host = os.environ.get("GENVEX_NABTO_HOST", "")
    if (not re.fullmatch(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+", identity)
            or not re.fullmatch(
                r"[A-Za-z0-9-]{1,64}\.remote\.lscontrol\.dk", host,
                re.IGNORECASE)):
        output("PREFLIGHT", "IDENTITY_OR_HOST_INVALID")
        return 2
    cert, key = PROFILE / "client.crt", PROFILE / "client-encrypted.key"
    if not all(x.is_file() for x in (cert, key, XML42, XML45, LIB)):
        output("PREFLIGHT", "PROFILE_SDK_OR_XML_MISSING")
        return 2
    schema = xml_interface()
    password = getpass.getpass("Existing Nabto key passphrase: ")
    if not password:
        output("PREFLIGHT", "EMPTY_PASSPHRASE")
        return 2
    P, C = ct.c_void_p, ct.c_char_p
    sdk = ct.CDLL(str(LIB))
    def api(name, args):
        fn = getattr(sdk, name)
        fn.argtypes = args
        fn.restype = ct.c_int
        return fn
    startup = api("nabtoStartup", [C])
    resources = api("nabtoInstallDefaultStaticResources", [C])
    open_session = api("nabtoOpenSession", [ct.POINTER(P), C, C])
    set_interface = api("nabtoRpcSetDefaultInterface", [P, C, ct.POINTER(P)])
    invoke = api("nabtoRpcInvoke", [P, C, ct.POINTER(P)])
    close = api("nabtoCloseSession", [P])
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

    urls = {i: request_url(host, i) for i in (42, 45)}
    session = P()
    started = opened = False
    output("MODE", "BRACKETED_RPC42_RPC45_RPC42_READ_ONLY")
    try:
        with tempfile.TemporaryDirectory(prefix="genvex-sync-probe-") as folder:
            users = Path(folder) / "users"
            users.mkdir(mode=0o700)
            stem = identity.replace("@", "_at_")
            for source, suffix in ((cert, ".crt"), (key, ".key")):
                dest = users / (stem + suffix)
                shutil.copyfile(source, dest)
                dest.chmod(0o600)
            status = startup(folder.encode())
            output("SDK_STARTUP", status)
            if status:
                return 2
            started = True
            status = resources(None)
            output("SDK_RESOURCES", status)
            if status:
                return 2
            status = open_session(ct.byref(session), identity.encode(),
                                  password.encode())
            output("SDK_SESSION", status)
            if status:
                return 2
            opened = True
            ptr = P()
            status = set_interface(session, schema, ct.byref(ptr))
            response = consume(ptr)
            output("XML_REGISTER_STATUS", status)
            if status:
                output("XML_ERROR_EVENT", error_event(response))
                return 2
            all_ok = True
            for index in range(1, 4):
                started_at = datetime.now(timezone.utc).isoformat()
                t0 = time.monotonic()
                observed = []
                for query in (42, 45, 42):
                    ptr = P()
                    status = invoke(session, urls[query], ct.byref(ptr))
                    response = consume(ptr)
                    if status:
                        output(f"SAMPLE_{index}_RPC{query}_STATUS", status)
                        output(f"SAMPLE_{index}_RPC{query}_EVENT",
                               error_event(response))
                        break
                    try:
                        observed.append(decode(query, response))
                    except (ValueError, KeyError, AttributeError, TypeError):
                        output(f"SAMPLE_{index}_RPC{query}_DECODE",
                               "INVALID")
                        break
                output(f"SAMPLE_{index}_UTC_START", started_at)
                output(f"SAMPLE_{index}_WINDOW_MS",
                       round((time.monotonic() - t0) * 1000))
                if len(observed) != 3:
                    output(f"SAMPLE_{index}_RESULT", "INCOMPLETE")
                    all_ok = False
                else:
                    before, readings, after = observed
                    output(f"SAMPLE_{index}_LEVEL_BEFORE", before)
                    output(f"SAMPLE_{index}_LEVEL_AFTER", after)
                    for addr in REGISTERS:
                        output(f"SAMPLE_{index}_RPC45_{addr}", readings[addr])
                    output(f"SAMPLE_{index}_SUPPLY_DISPLAY_PERCENT",
                           round(readings[18] / 100, 2))
                    output(f"SAMPLE_{index}_EXTRACT_DISPLAY_PERCENT",
                           round(readings[19] / 100, 2))
                    stable = before == after
                    output(f"SAMPLE_{index}_LEVEL_BRACKET_STABLE",
                           "YES" if stable else "NO")
                    all_ok &= stable
                if index != 3:
                    time.sleep(2)
            output("OVERALL", "PASS" if all_ok else "INCONCLUSIVE")
            return 0 if all_ok else 2
    finally:
        if opened:
            output("SDK_CLOSE", close(session))
        if started:
            output("SDK_SHUTDOWN", shutdown())
        output("RPC43_WRITE_ATTEMPTED", "NO")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, AttributeError, ValueError, ET.ParseError):
        output("FAILURE", "PREFLIGHT_OR_SDK_RUNTIME")
        raise SystemExit(2)
