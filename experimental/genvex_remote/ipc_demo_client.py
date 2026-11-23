#!/usr/bin/env python3
"""Read-only isolated network smoke-client; no Home Assistant imports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from snapshot_contract import parse_snapshot


def _fetch(url: str, token: str | None) -> tuple[int, bytes]:
    headers = {"Authorization": "Bearer " + token} if token is not None else {}
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=8) as response:
            return response.status, response.read(4097)
    except HTTPError as exc:
        return exc.code, exc.read(4097)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    if args.url != "http://genvex-ipc-server:18275/v1/snapshot":
        raise SystemExit("Only the disposable test container endpoint is accepted")
    token = args.token_file.read_text(encoding="ascii").strip()
    code, _ = _fetch(args.url, None)
    assert code == 401, "Missing token must return 401"
    print("PASS: request without token rejected", flush=True)
    code, _ = _fetch(args.url, token[::-1])
    assert code == 401, "Incorrect token must return 401"
    print("PASS: incorrect token rejected", flush=True)
    code, content = _fetch(args.url, token)
    assert code == 200, "Authorized GET did not return 200"
    result = json.loads(content)
    readings = parse_snapshot(result, expected_device_id="123456789012")
    assert len(readings) == 5 and readings["humidity"] == 65.0
    print("PASS: authenticated snapshot has 5/5 valid fake readings", flush=True)
    print("PASS: client rejected no credentials or raw SDK state (none was used)", flush=True)


if __name__ == "__main__":
    main()
