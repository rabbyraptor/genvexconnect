#!/usr/bin/env python3
"""One read-only candidate Nabto 4 RPC test for authorized Optima 270 hardware.

Uses the existing local test certificate, does not send writes, suppresses raw JSON.
Query 45 is sourced from the public Genvex LAN protocol; remote support is UNVERIFIED.
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

# Single read-only query: one *known* sensor, object 0 address 20 (supply air).
body = {"request": {"datapoints": [{"obj": 0, "address": 20}], "trailer": 1}}
url = ("nabto://" + HOST + "/candidate_read_datapoints.json?json="
       + quote(json.dumps(body, separators=(",", ":")), safe="")).encode()

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

print("===== READ-ONLY RPC 45 CANDIDATE =====", flush=True)
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

        print("Invoking: read-only ID 45; object 0; address 20; count 1",
              flush=True)
        response_ptr = P()
        status = invoke(session, url, ct.byref(response_ptr))
        diagnostic = take(response_ptr)
        print("RPC status:", status, flush=True)
        if status:
            print("Diagnostic:", classify_error(diagnostic), flush=True)
            print("Remote support: NOT VERIFIED", flush=True)
        else:
            try:
                doc = json.loads(diagnostic)
                values = doc.get("response", {}).get("values", [])
                if not isinstance(values, list) or len(values) != 1:
                    raise ValueError("Unexpected response list length")
                raw = values[0].get("value")
                if type(raw) is not int or not -32768 <= raw <= 32767:
                    raise ValueError("Unexpected datapoint type")
                print("Raw supply temperature register:", raw, flush=True)
                print("Decoded temperature (candidate):",
                      (raw - 300) / 10, "C", flush=True)
                print("Result: RESPONSE_DECODED_UNVERIFIED", flush=True)
            except (ValueError, TypeError, AttributeError, KeyError):
                print("Result: RPC_OK_BUT_SCHEMA_UNCONFIRMED", flush=True)
except RuntimeError as exc:
    print("Stopped:", str(exc), flush=True)
finally:
    if opened:
        print("Session close:", close(session), flush=True)
    if started:
        print("SDK shutdown:", shutdown(), flush=True)
    print("Temporary profile: removed on normal exit", flush=True)
    print("===== COMPLETE =====", flush=True)
