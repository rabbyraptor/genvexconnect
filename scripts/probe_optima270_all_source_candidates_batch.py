#!/usr/bin/env python3
"""Optima270 2B: one opt-in read-only RPC45 batch of 12 fixed source candidates.

Default is inert offline preview. A live batch requires explicit approval.
Not an address scan; no write RPCs; no installed HAOS App changes.
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


def selected_candidates():
    candidates = tuple(list_source_only_candidates())
    if len(candidates) != 12 or len({c.address for c in candidates}) != 12:
        raise ValueError("Expected exactly 12 distinct source-defined candidates")
    return candidates


def request_body(candidates) -> dict:
    if tuple(candidates) != selected_candidates():
        raise ValueError("Batch must contain exactly the fixed source-only inventory")
    return {"request": {"datapoints": [
        {"obj": 0, "address": c.address} for c in candidates
    ], "trailer": 1}}


def decode_batch_response(payload: str) -> tuple[int, ...]:
    """Bounded, fail-closed JSON response; no partial or reordered results."""

    if not isinstance(payload, str) or len(payload) > 16384:
        raise ValueError("Response length invalid")
    try:
        root = json.loads(payload)
        values = root["response"]["values"]
        if type(values) is not list or len(values) != 12:
            raise ValueError("Response count invalid")
        readings = []
        for item in values:
            if type(item) is not dict:
                raise ValueError("Response item invalid")
            value = item["value"]
            if type(value) is not int or not -32768 <= value <= 32767:
                raise ValueError("Reading not a signed int16")
            readings.append(value)
        return tuple(readings)
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


def classify_rpc_error(status: int, events: tuple[int, ...]) -> str:
    """Return non-sensitive, source-grounded SDK failure category.

    Nabto 4 client API: 26 is FAILED_WITH_JSON_MESSAGE.
    Nabto legacy client events: 1000015 is MICROSERVER_NOT_KNOWN.
    Neither status proves a given RPC45 sensor is unsupported.
    """
    if status == 26 and 1000015 in events:
        return "GATEWAY_NOT_KNOWN_OR_UNAVAILABLE"
    if status == 26 and 2000027 in events:
        return "CLIENT_QUERY_MODEL_NO_SUCH_REQUEST"
    if status == 26:
        return "SDK_REPORTED_JSON_ERROR"
    return "SDK_OTHER_ERROR"


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


def execute_one_batch(candidates, *, use_passphrase_stdin: bool = False):
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
    password = sys.stdin.readline(1024).rstrip("\r\n")
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
    print("===== ONE FIXED 12-CANDIDATE RPC45 READ-ONLY BATCH =====", flush=True)
    print("Addresses:", ",".join(str(c.address) for c in candidates), flush=True)
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

            body = json.dumps(request_body(candidates), separators=(",", ":"))
            url = "nabto://" + host + "/" + QUERY_NAME + "?json=" + quote(body, safe="")
            response = p()
            started_at = time.monotonic()
            # Exactly ONE network RPC invocation. Read-only ID 45, 12 fixed items.
            status = invoke(session, url.encode("utf-8"), ct.byref(response))
            diagnostic = take(response)
            elapsed = round((time.monotonic() - started_at) * 1000)
            if status:
                events = _status_events(diagnostic)
                print("RPC status:", status, "events:", events,
                      "category:", classify_rpc_error(status, events), flush=True)
                raise RuntimeError("Read-only request failed")
            raws = decode_batch_response(diagnostic)
            print("RPC status: 0 elapsed_ms:", elapsed, flush=True)
            for candidate, raw in zip(candidates, raws):
                scaled = (raw + candidate.scale_offset) / candidate.scale_divisor
                print("Candidate:", candidate.key, "address:", candidate.address,
                      "raw:", raw, "source_scaled:", scaled, flush=True)
            print("Result: TWELVE_CANDIDATES_DECODED_SOURCE_ONLY", flush=True)
    finally:
        if opened:
            print("Session close status:", close(session), flush=True)
        if started:
            print("SDK shutdown status:", shutdown(), flush=True)
        print("Temporary test profile cleanup attempted", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-live", action="store_true",
                        help="Execute one 12-item live RPC45 batch")
    parser.add_argument("--approved-read-only", action="store_true",
                        help="Confirm operator approval of this exact one-batch test")
    parser.add_argument("--passphrase-stdin", action="store_true",
                        help="Read existing key passphrase from stdin; live only")
    args = parser.parse_args(argv)
    candidates = selected_candidates()
    if not args.execute_live:
        if args.approved_read_only or args.passphrase_stdin:
            parser.error("Live-only flags cannot be used in offline preview")
        print("OFFLINE preview: no Nabto SDK or connection was opened")
        print("One read-only RPC45 batch, exactly 12 source-only addresses:")
        for candidate in candidates:
            print("Candidate:", candidate.key, "address:", candidate.address,
                  "obj=0 scale:", candidate.scale_offset, candidate.scale_divisor)
        return 0
    if not args.approved_read_only or not args.passphrase_stdin:
        parser.error("Live batch requires explicit approval and stdin-passphrase wrapper")
    try:
        execute_one_batch(candidates, use_passphrase_stdin=True)
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print("FAILED:", type(exc).__name__, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
