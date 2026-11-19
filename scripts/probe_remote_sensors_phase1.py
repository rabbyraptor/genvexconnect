#!/usr/bin/env python3
"""Phase 1: source-grounded read-only Nabto RPC 45, five individual Optima 270 sensors.

Uses an existing locally provisioned client profile. No write RPC, no batch requests,
no raw JSON, account, hostname, certificate, private key or passphrase in logs.
The same RPC was already verified for single supply temperature; others are OPEN.
"""
import ctypes as ct
import getpass
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path.home()
PROFILE = ROOT / ".local/share/genvex-nabto-profile-1024-test"
LIB = ROOT / "genvex-ca-check/libnabto_client_api.so"
IDENTITY = os.environ.get("GENVEX_NABTO_IDENTITY", "")
HOST = os.environ.get("GENVEX_NABTO_HOST", "")
if not IDENTITY or not HOST or any(x in HOST for x in "/?&# "):
    sys.exit("Set GENVEX_NABTO_IDENTITY and GENVEX_NABTO_HOST (existing authorized gateway).")

CERT, KEY = PROFILE / "client.crt", PROFILE / "client-encrypted.key"
if not all(p.is_file() for p in (CERT, KEY, LIB)):
    sys.exit("Existing Nabto 4 SDK / encrypted profile was not found.")

SCHEMA = b"""<unabto_queries>
<query name="candidate_read_datapoints.json" id="45">
  <request>
    <list name="datapoints"><parameter name="obj" type="uint8"/>
      <parameter name="address" type="uint32"/></list>
    <parameter name="trailer" type="uint8" default="1"/>
  </request>
  <response format="json">
    <list name="values"><parameter name="value" type="int16"/></list>
  </response>
</query>
</unabto_queries>"""

# Exact addresses from public genvexnabto/models/optima270.py, not a range scan.
# address, label, divisor, offset, unit
SENSORS = [
    (20, "Supply air", 10, -300, "C"),
    (21, "Outdoor air", 10, -300, "C"),
    (22, "Exhaust air", 10, -300, "C"),
    (23, "Extract air", 10, -300, "C"),
    (26, "Humidity", 1, 0, "%"),
]

def make_url(address):
    body = {"request": {"datapoints": [{"obj": 0, "address": address}], "trailer": 1}}
    return ("nabto://" + HOST + "/candidate_read_datapoints.json?json="
            + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()

def decode_one(raw_json):
    try:
        data = json.loads(raw_json)
        values = data["response"]["values"]
        if not isinstance(values, list) or len(values) != 1:
            return None
        value = values[0]["value"]
        return value if type(value) is int and -32768 <= value <= 32767 else None
    except (ValueError, TypeError, LookupError, AttributeError):
        return None

def classify_error(raw):
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        return "NO_JSON_DIAGNOSTIC", []
    events = set()
    def walk(v):
        if isinstance(v, dict):
            for k, sub in v.items():
                if k in ("event", "code", "error_code") and type(sub) is int and 0 <= sub <= 10000000:
                    events.add(sub)
                if isinstance(sub, (dict, list)):
                    walk(sub)
        elif isinstance(v, list):
            for sub in v:
                walk(sub)
    walk(doc)
    return "ERROR_JSON", sorted(events)[:8]

dll = ct.CDLL(str(LIB))
P = ct.c_void_p
C = ct.c_char_p
def api(name, argtypes):
    fn = getattr(dll, name)
    fn.argtypes = argtypes
    fn.restype = ct.c_int
    return fn
startup = api("nabtoStartup", [C])
resources = api("nabtoInstallDefaultStaticResources", [C])
open_session = api("nabtoOpenSession", [ct.POINTER(P), C, C])
set_interface = api("nabtoRpcSetDefaultInterface", [P, C, ct.POINTER(P)])
invoke = api("nabtoRpcInvoke", [P, C, ct.POINTER(P)])
close = api("nabtoCloseSession", [P])
shutdown = api("nabtoShutdown", [])
dll.nabtoFree.argtypes = [P]
dll.nabtoFree.restype = None

def take(ptr):
    if not ptr.value:
        return ""
    try:
        return ct.string_at(ptr).decode("utf-8", "replace")
    finally:
        dll.nabtoFree(ptr)

password = getpass.getpass("Existing encrypted test key passphrase: ")
if not password:
    sys.exit("Empty passphrase")

print("===== OPTIMA 270 REMOTE READ-ONLY PHASE 1 =====", flush=True)
session = P()
started = opened = False
try:
    with tempfile.TemporaryDirectory(prefix="genvex-readonly-45-") as tmp:
        users = Path(tmp) / "users"
        users.mkdir(mode=0o700)
        stem = IDENTITY.replace("@", "_at_")
        for src, ext in ((CERT, ".crt"), (KEY, ".key")):
            dst = users / (stem + ext)
            shutil.copyfile(src, dst)
            dst.chmod(0o600)

        status = startup(tmp.encode())
        print("SDK startup:", status, flush=True)
        if status: raise RuntimeError("SDK_STARTUP_FAILED")
        started = True
        status = resources(None)
        print("Resources:", status, flush=True)
        if status: raise RuntimeError("RESOURCES_FAILED")
        status = open_session(ct.byref(session), IDENTITY.encode(), password.encode())
        print("Profile session:", status, flush=True)
        if status: raise RuntimeError("SESSION_FAILED")
        opened = True

        error = P()
        status = set_interface(session, SCHEMA, ct.byref(error))
        diagnostic = take(error)
        print("Candidate XML registered:", status, flush=True)
        if status:
            print("XML diagnostic:", classify_error(diagnostic), flush=True)
            raise RuntimeError("CANDIDATE_XML_REJECTED")

        print("Invoking five source-defined read-only sensors, one at a time.",
              flush=True)
        completed = 0
        import time
        for address, label, divisor, offset, unit in SENSORS:
            response_ptr = P()
            started_at = time.monotonic()
            status = invoke(session, make_url(address), ct.byref(response_ptr))
            diagnostic = take(response_ptr)
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            if status:
                print(f"{label} (address {address}): FAILED status={status} "
                      f"events={classify_error(diagnostic)[1]} elapsed_ms={elapsed_ms}",
                      flush=True)
                print("Stopped on first RPC error; no further requests sent.",
                      flush=True)
                break
            raw = decode_one(diagnostic)
            if raw is None:
                print(f"{label} (address {address}): RPC OK but response schema invalid",
                      flush=True)
                print("Stopped on first decoding error; no further requests sent.",
                      flush=True)
                break
            value = (raw + offset) / divisor
            print(f"{label} (address {address}): raw={raw} "
                  f"value={value:.2f} {unit} elapsed_ms={elapsed_ms}",
                  flush=True)
            completed += 1
        print(f"Read-only sensors decoded: {completed}/{len(SENSORS)}", flush=True)
        if completed != len(SENSORS):
            sys.exit(6)
except RuntimeError as exc:
    print("Stopped:", str(exc), flush=True)
finally:
    if opened:
        print("Session close:", close(session), flush=True)
    if started:
        print("SDK shutdown:", shutdown(), flush=True)
    print("Temporary profile: removed on normal exit", flush=True)
    print("===== COMPLETE =====", flush=True)
