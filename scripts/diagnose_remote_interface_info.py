#!/usr/bin/env python3
"""Read-only Nabto 4 metadata error probe. Outputs whitelisted diagnostics only.

Requires existing, user-provisioned RSA-1024 test profile and Nabto 4 SDK on
Linux x86_64 Steam Deck. No credentials, certificate, raw JSON or hostname
are logged. Does not modify the existing HA integration.
"""
import ctypes as ct
import getpass
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
PROFILE = HOME / ".local/share/genvex-nabto-profile-1024-test"
LIBRARY = HOME / "genvex-ca-check/libnabto_client_api.so"

# Supply private values at runtime, never commit them.
identity = os.environ.get("GENVEX_NABTO_IDENTITY", "")
hostname = os.environ.get("GENVEX_NABTO_HOST", "")
if not identity or not hostname or "/" in hostname:
    sys.exit("Set GENVEX_NABTO_IDENTITY and GENVEX_NABTO_HOST first.")

cert = PROFILE / "client.crt"
key = PROFILE / "client-encrypted.key"
if not all(p.is_file() for p in (cert, key, LIBRARY)):
    sys.exit("Missing locally provisioned test profile or SDK.")
password = getpass.getpass("Existing test key passphrase: ")
if not password:
    sys.exit("Empty passphrase.")

# The ONLY registered query is the already-known ping ID 17. This is
# intentional: it permits distinguishing a local name lookup failure.
XML = b"""<unabto_queries><query name="ping.json" id="17"><request>
<parameter name="ping" type="uint32"/></request><response format="json">
<parameter name="Pong" type="uint32"/></response></query></unabto_queries>"""

def diagnose(raw):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return "NON_JSON_OR_EMPTY", [], False
    if not isinstance(data, (dict, list)):
        return "UNEXPECTED_JSON_TYPE", [], True
    codes, messages = [], []
    def walk(value):
        if isinstance(value, dict):
            for key, sub in value.items():
                k = str(key).lower()
                if k in ("event", "code", "error_code", "errorcode", "status"):
                    if type(sub) is int and 0 <= sub < 10_000_000:
                        codes.append(sub)
                elif k in ("body", "header", "detail", "message", "description", "error") and isinstance(sub, str):
                    # Never display messages, URLs, personal data, or raw JSON.
                    messages.append(sub.lower())
                if isinstance(sub, (dict, list)):
                    walk(sub)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(data)
    joined = " ".join(messages)
    if any("no such request" in x or "not found" in x or "not in interface" in x or "unknown query" in x for x in messages) or 3227 in codes or 4007 in codes:
        category = "QUERY_LOOKUP_OR_NOT_FOUND"
    elif 3223 in codes or "invalid interface" in joined:
        category = "INTERFACE_INVALID"
    elif 3267 in codes or "interface not set" in joined:
        category = "INTERFACE_NOT_SET"
    elif 4004 in codes or "access denied" in joined:
        category = "ACCESS_DENIED"
    elif "parameter" in joined and "missing" in joined:
        category = "PARAMETER_MISSING"
    else:
        category = "OTHER_JSON_ERROR"
    return category, sorted(set(codes))[:8], True

sdk = ct.CDLL(str(LIBRARY))
P, C = ct.c_void_p, ct.c_char_p
def api(name, args):
    f = getattr(sdk, name)
    f.argtypes, f.restype = args, ct.c_int
    return f
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

print("===== NABTO METADATA ERROR V2 =====", flush=True)
started, opened = False, False
session = P()
try:
    with tempfile.TemporaryDirectory(prefix="genvex-metadata-v2-") as temporary:
        temp = Path(temporary)
        directory = temp / "users"
        directory.mkdir(mode=0o700)
        stem = identity.replace("@", "_at_")
        for src, suffix in ((cert, ".crt"), (key, ".key")):
            dst = directory / (stem + suffix)
            shutil.copyfile(src, dst)
            dst.chmod(0o600)
        st = startup(str(temp).encode())
        print("Startup:", st, flush=True)
        if st:
            sys.exit(2)
        started = True
        st = resources(None)
        print("Resources:", st, flush=True)
        if st:
            sys.exit(3)
        st = open_session(ct.byref(session), identity.encode(), password.encode())
        print("Session:", st, flush=True)
        if st:
            sys.exit(4)
        opened = True
        err = P()
        st = set_interface(session, XML, ct.byref(err))
        diagnostic = consume(err)
        print("Interface:", st, flush=True)
        if st:
            print("Interface diagnostic:", diagnose(diagnostic), flush=True)
            sys.exit(5)
        result = P()
        st = invoke(session, ("nabto://" + hostname + "/get_interface_info.json").encode(), ct.byref(result))
        detail = consume(result)
        category, codes, valid_json = diagnose(detail)
        print("RPC status:", st, flush=True)
        print("Diagnostic category:", "SUCCESS" if st == 0 else category, flush=True)
        print("Nabto diagnostic events/codes:", codes, flush=True)
        print("JSON valid:", valid_json, flush=True)
        if st == 0:
            try:
                obj = json.loads(detail)
                response = obj.get("response", {})
                if isinstance(response, dict):
                    for field in ("interface_version_major", "interface_version_minor"):
                        value = response.get(field)
                        if type(value) is int:
                            print(field + ":", value, flush=True)
                    print("Interface ID present:", isinstance(response.get("interface_id"), str), flush=True)
            except (ValueError, AttributeError):
                pass
finally:
    if opened:
        print("Session close:", close_session(session), flush=True)
    if started:
        print("SDK shutdown:", shutdown(), flush=True)
    print("Temporary profile: cleaned up if execution completed", flush=True)
    print("===== COMPLETE =====", flush=True)
