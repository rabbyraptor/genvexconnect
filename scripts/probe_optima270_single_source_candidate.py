#!/usr/bin/env python3
"""Optima270 2B: ONE authorized read-only candidate RPC45 probe on Steam Deck.

Default: OFFLINE preview with no SDK, network, profile, credentials or prompts.
Live execution requires TWO explicit CLI flags and a separate operator approval.
Only one address from optima270_source_only.py can be requested per run.
Do not copy this probe into an installed HAOS App.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "experimental" / "genvex_remote"))

from optima270_source_only import list_source_only_candidates  # noqa: E402

RPC_ID = 45
QUERY_NAME = "candidate_read_datapoints.json"
# This XML is the same *read-only RPC45* request/response shape as the five
# individually verified remote requests. Not an enumeration/read range.
READ_ONLY_XML = b"""<unabto_queries>
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


def select_candidate(key: str):
    for candidate in list_source_only_candidates():
        if candidate.key == key:
            return candidate
    raise ValueError("Unknown or not source-defined candidate")


def request_body(candidate) -> dict:
    # No arbitrary address input; only validated single source-only objects.
    if candidate is not select_candidate(candidate.key):
        raise ValueError("Source-only candidate object was replaced")
    return {
        "request": {
            "datapoints": [{"obj": 0, "address": candidate.address}],
            "trailer": 1,
        }
    }


def decode_single_response(payload: str) -> int:
    """Bounded, fail-closed legacy SDK JSON response decoder."""
    if not isinstance(payload, str) or len(payload) > 8192:
        raise ValueError("Response length invalid")
    try:
        root = json.loads(payload)
        values = root["response"]["values"]
        if type(values) is not list or len(values) != 1:
            raise ValueError("Response count invalid")
        value = values[0]["value"]
        if type(value) is not int or not -32768 <= value <= 32767:
            raise ValueError("Reading not a signed int16")
        return value
    except (TypeError, KeyError, IndexError, AttributeError) as exc:
        raise ValueError("Response schema invalid") from exc


def _status_events(raw_json: str) -> tuple[int, ...]:
    """Return numeric error codes only; do not log sensitive JSON."""
    if not isinstance(raw_json, str) or len(raw_json) > 8192:
        return ()
    try:
        data = json.loads(raw_json)
    except ValueError:
        return ()
    seen = set()

    def scan(item, depth=0):
        if depth > 5:
            return
        if isinstance(item, dict):
            for key, value in item.items():
                if key in ("event", "code", "error_code") and type(value) is int and 0 <= value <= 10000000:
                    seen.add(value)
                elif isinstance(value, (dict, list)):
                    scan(value, depth + 1)
        elif isinstance(item, list):
            for value in item[:12]:
                if isinstance(value, (dict, list)):
                    scan(value, depth + 1)

    scan(data)
    return tuple(sorted(seen)[:8])


def _check_existing_profile(root: Path, identity: str) -> tuple[Path, Path, Path, str]:
    """No profile creation, no writes to sources, no symlinks."""
    if (
        not isinstance(identity, str)
        or len(identity) > 254
        or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+=?^_`{|}~-]+@[A-Za-z0-9.-]+", identity)
        or ".." in identity
    ):
        raise ValueError("Authorized identity is invalid")

    profile = root / ".local/share/genvex-nabto-profile-1024-test"
    lib = root / "genvex-ca-check/libnabto_client_api.so"
    cert = profile / "client.crt"
    key = profile / "client-encrypted.key"
    for path in (cert, key, lib):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing SDK or private profile files unavailable")
    return cert, key, lib, identity.replace("@", "_at_")


def execute_one_read(candidate, *, use_passphrase_stdin: bool = False):
    # Late import ensures OFFLINE preview cannot accidentally import the SDK.
    import ctypes as ct
    import shutil
    import tempfile
    import time

    host = os.environ.get("GENVEX_NABTO_HOST", "")
    identity = os.environ.get("GENVEX_NABTO_IDENTITY", "")
    if not re.fullmatch(r"[0-9]{12}\.remote\.lscontrol\.dk", host):
        raise ValueError("Authorized gateway hostname is not valid")

    cert, key, lib, profile_stem = _check_existing_profile(Path.home(), identity)
    print("PASS: existing SDK, encrypted test profile and target format verified", flush=True)
    # The Steam Deck wrapper collects the passphrase with an explicit visible
    # shell prompt and writes it through a pipe. Reading stdin avoids
    # getpass.getpass() stalling on /dev/tty under nested timeout sessions.
    # Never print, log or export the passphrase.
    if not use_passphrase_stdin:
        raise ValueError("Live runs require the approved passphrase-stdin wrapper")
    password = sys.stdin.readline(1024).rstrip("\\r\\n")
    if not password or len(password) > 1022:
        raise ValueError("Empty or oversized encrypted-key passphrase")
    print("PASS: encrypted-key input received; preparing SDK", flush=True)

    dll = ct.CDLL(str(lib))
    p = ct.c_void_p
    charptr = ct.c_char_p

    def api(name, args):
        fn = getattr(dll, name)
        fn.argtypes = args
        fn.restype = ct.c_int
        return fn

    startup = api("nabtoStartup", [charptr])
    resources = api("nabtoInstallDefaultStaticResources", [charptr])
    open_session = api("nabtoOpenSession", [ct.POINTER(p), charptr, charptr])
    set_interface = api("nabtoRpcSetDefaultInterface", [p, charptr, ct.POINTER(p)])
    invoke = api("nabtoRpcInvoke", [p, charptr, ct.POINTER(p)])
    close = api("nabtoCloseSession", [p])
    shutdown = api("nabtoShutdown", [])
    dll.nabtoFree.argtypes = [p]
    dll.nabtoFree.restype = None

    def take(response):
        if not response.value:
            return ""
        try:
            return ct.string_at(response).decode("utf-8", "replace")
        finally:
            dll.nabtoFree(response)

    started = opened = False
    session = p()
    print("===== ONE SOURCE-DEFINED RPC45 READ ONLY =====", flush=True)
    print("Candidate key:", candidate.key, "address:", candidate.address, flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix="genvex-single-candidate-") as tmp:
            users = Path(tmp) / "users"
            users.mkdir(mode=0o700)
            for source, suffix in ((cert, ".crt"), (key, ".key")):
                target = users / (profile_stem + suffix)
                shutil.copyfile(source, target)
                target.chmod(0o600)

            status = startup(tmp.encode("utf-8"))
            if status:
                raise RuntimeError("SDK startup failed")
            started = True
            status = resources(None)
            if status:
                raise RuntimeError("SDK resources failed")
            status = open_session(
                ct.byref(session), identity.encode("utf-8"), password.encode("utf-8")
            )
            if status:
                raise RuntimeError("SDK authenticated session failed")
            opened = True

            error = p()
            status = set_interface(session, READ_ONLY_XML, ct.byref(error))
            diagnostic = take(error)
            if status:
                print("XML status:", status, "events:", _status_events(diagnostic))
                raise RuntimeError("RPC45 XML registration failed")

            body = json.dumps(request_body(candidate), separators=(",", ":"))
            url = "nabto://" + host + "/" + QUERY_NAME + "?json=" + quote(body, safe="")
            response = p()
            started_at = time.monotonic()
            # Exactly ONE network RPC invocation. This is read-only ID 45.
            status = invoke(session, url.encode("utf-8"), ct.byref(response))
            diagnostic = take(response)
            elapsed = round((time.monotonic() - started_at) * 1000)
            if status:
                print("RPC status:", status, "events:", _status_events(diagnostic), flush=True)
                raise RuntimeError("Read-only request failed")
            raw = decode_single_response(diagnostic)
            print("RPC status: 0", flush=True)
            print("Raw int16:", raw, "elapsed_ms:", elapsed, flush=True)
            print("Source-scaled (NOT yet physically verified):",
                  (raw + candidate.scale_offset) / candidate.scale_divisor, flush=True)
            print("Result: ONE_CANDIDATE_DECODED", flush=True)
    finally:
        if opened:
            print("Session close status:", close(session), flush=True)
        if started:
            print("SDK shutdown status:", shutdown(), flush=True)
        print("Temporary test profile cleanup attempted", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, help="Exact key from 2B source-only inventory")
    parser.add_argument("--execute-live", action="store_true", help="Execute one live RPC45 read")
    parser.add_argument("--approved-read-only", action="store_true",
                        help="Confirm separate operator authorization for the single test")
    parser.add_argument("--passphrase-stdin", action="store_true",
                        help="Read key passphrase from piped stdin; required for live mode")
    args = parser.parse_args(argv)

    try:
        candidate = select_candidate(args.key)
    except ValueError:
        parser.error("Unknown source-only candidate key")
    if not args.execute_live:
        if args.approved_read_only or args.passphrase_stdin:
            parser.error("Live-only flags cannot be used in offline preview")
        print("OFFLINE preview: no Nabto SDK or connection was opened")
        print("Candidate:", candidate.key, "address:", candidate.address,
              "obj=0, rpc_id=45, remote_status:", candidate.remote_status)
        print("Only one item would be requested; source scale:",
              candidate.scale_offset, candidate.scale_divisor)
        return 0

    if not args.approved_read_only or not args.passphrase_stdin:
        parser.error("Live RPC requires separate approval and the Steam Deck stdin-passphrase wrapper")

    try:
        execute_one_read(candidate, use_passphrase_stdin=True)
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        # Fixed category only: no raw SDK response or any sensitive identity.
        print("FAILED:", type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
