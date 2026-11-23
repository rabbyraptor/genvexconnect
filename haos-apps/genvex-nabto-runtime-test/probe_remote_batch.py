#!/usr/bin/env python3
"""Phase 2: single read-only RPC 45 batch from HAOS QEMU x86_64 Python.

Uses an existing locally provisioned client profile. No write RPC, exactly one batch request,
no raw JSON, account, hostname, certificate, private key or passphrase in logs.
Five separate sensor reads are already verified; batch ordering is NOT yet verified.
"""
import ctypes as ct
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path.home()
# The test wrapper provides a random temporary profile folder, populated
# only with the user's pre-existing encrypted .key and public .crt.
PROFILE = Path(os.environ.get("GENVEX_NABTO_PROFILE", "/tmp/missing-remote-profile"))
LIB = Path("/opt/nabto/libnabto_client_api.so")
IDENTITY = ""
HOST = ""
password = None
if "--settings-stdin" in sys.argv:
    try:
        settings = json.loads(sys.stdin.readline())
        IDENTITY = settings["identity"]
        HOST = settings["host"]
        password = settings["passphrase"]
    except (ValueError, KeyError, TypeError):
        sys.exit("Invalid settings input")
    if not all(isinstance(v, str) and v for v in (IDENTITY, HOST, password)):
        sys.exit("Missing required settings")
else:
    sys.exit("This isolated HAOS QEMU test requires --settings-stdin")
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

def make_url():
    body = {"request": {"datapoints": [{"obj": 0, "address": item[0]} for item in SENSORS], "trailer": 1}}
    return ("nabto://" + HOST + "/candidate_read_datapoints.json?json="
            + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()

def decode_batch(raw_json):
    try:
        data = json.loads(raw_json)
        values = data["response"]["values"]
        if not isinstance(values, list) or len(values) != len(SENSORS):
            return None
        result = []
        for item in values:
            if not isinstance(item, dict):
                return None
            value = item.get("value")
            if type(value) is not int or not -32768 <= value <= 32767:
                return None
            result.append(value)
        return result
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

# Optional stdin mode avoids getpass(/dev/tty) terminal/paste handling quirks.
# The wrapper collects the passphrase silently and pipes it to stdin.
# No passphrase in environment variables or argv.
if not password:
    sys.exit("Empty passphrase")

print("===== OPTIMA 270 HAOS/QEMU REMOTE READ-ONLY BATCH =====", flush=True)
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

        print("Invoking ONE read-only RPC ID 45 with five ordered known addresses",
              flush=True)
        import time
        response_ptr = P()
        started_at = time.monotonic()
        status = invoke(session, make_url(), ct.byref(response_ptr))
        diagnostic = take(response_ptr)
        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        print("Batch RPC status:", status, flush=True)
        print("RPC elapsed_ms:", elapsed_ms, flush=True)
        if status:
            print("Diagnostic:", classify_error(diagnostic), flush=True)
            raise RuntimeError("BATCH_RPC_FAILED")
        readings = decode_batch(diagnostic)
        if readings is None:
            raise RuntimeError("BATCH_RESPONSE_COUNT_OR_SCHEMA_MISMATCH")
        for (address, label, divisor, offset, unit), raw in zip(SENSORS, readings):
            value = (raw + offset) / divisor
            print(f"{label} (address {address}): raw={raw} "
                  f"value={value:.2f} {unit}", flush=True)
        print(f"Read-only batch decoded: {len(readings)}/{len(SENSORS)}",
              flush=True)
        print("Result: BATCH_DECODED; live reference comparison still needed",
              flush=True)
except RuntimeError as exc:
    print("Stopped:", str(exc), flush=True)
    raise SystemExit(6)
finally:
    if opened:
        print("Session close:", close(session), flush=True)
    if started:
        print("SDK shutdown:", shutdown(), flush=True)
    print("SDK temporary session profile: removed on normal exit", flush=True)
    print("===== COMPLETE =====", flush=True)
