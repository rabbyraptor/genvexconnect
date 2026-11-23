#!/usr/bin/env python3
"""One-shot bridge client validation; expected identity comes from private file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from snapshot_contract import parse_snapshot


def call(url, token):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=6) as r:
            return r.status, r.read(4097)
    except HTTPError as e:
        return e.code, e.read(4097)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--device-file", type=Path, required=True)
    args = parser.parse_args()
    token = args.token_file.read_text(encoding="ascii").strip()
    device_id = args.device_file.read_text(encoding="ascii").strip()
    url = "http://genvex-live-server:18275/v1/snapshot"
    status, _ = call(url, None)
    assert status == 401, "Unauthenticated request was accepted"
    print("PASS: no-token HTTP request rejected", flush=True)
    status, _ = call(url, token[::-1])
    assert status == 401, "Wrong token was accepted"
    print("PASS: incorrect-token HTTP request rejected", flush=True)
    status, data = call(url, token)
    assert status == 200, "Authenticated response failed"
    snapshot = json.loads(data)
    values = parse_snapshot(snapshot, expected_device_id=device_id)
    assert len(values) == 5
    print("PASS: authenticated HTTP returned 5/5 REAL RPC45 sensor measurements", flush=True)
    print("PASS: timestamp, schema and device identity validated", flush=True)


if __name__ == "__main__":
    main()
