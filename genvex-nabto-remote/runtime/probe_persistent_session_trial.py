#!/usr/bin/env python3
"""Opt-in read-only RPC45 bounded post-failure recovery trial in ONE legacy SDK session.

Run only as a separate x86_64/QEMU process with --settings-stdin.
Accepts one JSON line containing identity/host/passphrase. No credentials or
raw SDK output printed. One startup/open/interface/close/shutdown sequence; continue after RPC failures.
"""
from __future__ import annotations
import ctypes as ct
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

SENSORS = (20, 21, 22, 23, 26)
SCHEMA = b"""<unabto_queries>
<query name="candidate_read_datapoints.json" id="45">
<request>
<list name="datapoints"><parameter name="obj" type="uint8"/>
<parameter name="address" type="uint32"/></list>
<parameter name="trailer" type="uint8" default="1"/>
</request>
<response format="json"><list name="values">
<parameter name="value" type="int16"/></list></response>
</query></unabto_queries>"""

def valid_batch(raw: str) -> bool:
    try:
        values = json.loads(raw)["response"]["values"]
        return (
            type(values) is list and len(values) == 5
            and all(
                type(x) is dict
                and type(x.get("value")) is int
                and -32768 <= x["value"] <= 32767
                for x in values
            )
        )
    except (ValueError, TypeError, LookupError):
        return False

def rpc_url(host: str) -> bytes:
    request = {"request": {"datapoints": [
        {"obj": 0, "address": address} for address in SENSORS
    ], "trailer": 1}}
    return ("nabto://" + host +
        "/candidate_read_datapoints.json?json=" +
        quote(json.dumps(request, separators=(",", ":")), safe="")).encode()

def main() -> int:
    if sys.argv[1:] != ["--settings-stdin"]:
        return 2
    try:
        settings = json.loads(sys.stdin.readline())
        identity = settings["identity"]
        host = settings["host"]
        secret = settings["passphrase"]
        if not all(type(v) is str and v and len(v) <= 1024
                   and not any(c in v for c in "\r\n\x00")
                   for v in (identity, host, secret)):
            return 2
        if not (host.endswith(".remote.lscontrol.dk")
                and len(host.split(".")[0]) == 12
                and host.split(".")[0].isascii()
                and host.split(".")[0].isdecimal()):
            return 2
        profile = Path(os.environ["GENVEX_NABTO_PROFILE"])
        cert = profile / "client.crt"
        key = profile / "client-encrypted.key"
        if not cert.is_file() or not key.is_file():
            return 2
        dll = ct.CDLL("/opt/nabto/libnabto_client_api.so")
    except (KeyError, OSError, ValueError, TypeError):
        return 2

    P, C = ct.c_void_p, ct.c_char_p
    def bind(name, args):
        fn = getattr(dll, name)
        fn.argtypes = args
        fn.restype = ct.c_int
        return fn
    startup = bind("nabtoStartup", [C])
    resources = bind("nabtoInstallDefaultStaticResources", [C])
    open_session = bind("nabtoOpenSession", [ct.POINTER(P), C, C])
    set_interface = bind("nabtoRpcSetDefaultInterface", [P, C, ct.POINTER(P)])
    invoke = bind("nabtoRpcInvoke", [P, C, ct.POINTER(P)])
    close_session = bind("nabtoCloseSession", [P])
    shutdown = bind("nabtoShutdown", [])
    dll.nabtoFree.argtypes = [P]
    dll.nabtoFree.restype = None

    def take(pointer):
        if not pointer.value:
            return ""
        try:
            return ct.string_at(pointer).decode("utf-8", "replace")
        finally:
            dll.nabtoFree(pointer)

    session = P()
    started = opened = False
    successful = 0
    status_summary = []
    recovery_after_failure = False
    first_failure_at = None
    try:
        with tempfile.TemporaryDirectory(prefix="genvex-persistent-ab-") as folder:
            users = Path(folder) / "users"
            users.mkdir(mode=0o700)
            stem = identity.replace("@", "_at_")
            for src, suffix in ((cert, ".crt"), (key, ".key")):
                dest = users / (stem + suffix)
                shutil.copyfile(src, dest)
                dest.chmod(0o600)
            status = startup(folder.encode())
            print("SDK_STARTUP_STATUS:", status, flush=True)
            if status:
                return 3
            started = True
            status = resources(None)
            print("SDK_RESOURCES_STATUS:", status, flush=True)
            if status:
                return 3
            status = open_session(ct.byref(session), identity.encode(), secret.encode())
            print("SESSION_OPEN_STATUS:", status, flush=True)
            if status:
                return 3
            opened = True
            err = P()
            status = set_interface(session, SCHEMA, ct.byref(err))
            take(err)
            print("RPC_INTERFACE_STATUS:", status, flush=True)
            if status:
                return 3
            url = rpc_url(host)
            print("PROCESS_REUSE: ONE", flush=True)
            print("SESSION_OPEN_COUNT: 1", flush=True)
            print("SESSION_HANDLE_REUSED: YES", flush=True)
            # Up to six scheduled attempts. Upon the first failure, always
            # issue two additional attempts in this SAME session, bounded to
            # eight total calls; no SDK/session restart occurs.
            for index in range(8):
                if index:
                    time.sleep(60)
                response = P()
                begin = time.monotonic()
                status = invoke(session, url, ct.byref(response))
                duration = round((time.monotonic() - begin) * 1000)
                raw = take(response)
                valid = status == 0 and valid_batch(raw)
                successful += int(valid)
                if not valid and first_failure_at is None:
                    first_failure_at = index
                elif valid and first_failure_at is not None:
                    recovery_after_failure = True
                status_summary.append(status)
                print(
                    f"RPC45_{index+1}: status={status} "
                    f"values={5 if valid else 0} elapsed_ms={duration} "
                    f"session_reused={'first' if index == 0 else 'yes'}",
                    flush=True,
                )
                if (first_failure_at is not None and index >= first_failure_at + 2
                        or first_failure_at is None and index == 5):
                    break
            attempts = len(status_summary)
            print(f"RPC45_SUCCESS_COUNT: {successful}/{attempts}", flush=True)
            print(f"RPC45_FAILURE_COUNT: {attempts - successful}", flush=True)
            print(f"RPC45_FAILURE_OBSERVED: {first_failure_at is not None}", flush=True)
            print(f"RPC45_POST_FAILURE_ATTEMPTS: {attempts - first_failure_at - 1 if first_failure_at is not None else 0}", flush=True)
            print(f"RPC45_RECOVERED_IN_SAME_SESSION: {recovery_after_failure}", flush=True)
            print("SESSION_OPEN_COUNT_FINAL: 1", flush=True)
            return 0 if recovery_after_failure else 1
    except Exception:
        print("TRIAL_EXCEPTION: SANITIZED", flush=True)
        return 4
    finally:
        if opened:
            try:
                print("SESSION_CLOSE_STATUS:", close_session(session), flush=True)
            except Exception:
                print("SESSION_CLOSE_STATUS: ERROR", flush=True)
        if started:
            try:
                print("SDK_SHUTDOWN_STATUS:", shutdown(), flush=True)
            except Exception:
                print("SDK_SHUTDOWN_STATUS: ERROR", flush=True)

if __name__ == "__main__":
    raise SystemExit(main())
