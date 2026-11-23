#!/usr/bin/env python3
"""Offline-only reconstruction of Optima 270 legacy setpoint read (RPC42).

Source: superrob/genvexnabto's cmd_setpoint_readlist.py and
genvexnabto_modeladapter.py; not the vendor's original RPC XML.
No Nabto library, network, device host, credentials or RPC43 write code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
XML = HERE / "tests/fixtures/candidate_readonly_query42.xml"
CATALOG = HERE / "docs/references/optima270_micro_nabto_setpoint_catalog.json"
VALID = {1, 3, 6, 7, 21, 29, 30, 50, 57, 58, 70, 100}


def candidate_query() -> ET.Element:
    query = ET.parse(XML).getroot().find("query")
    if query is None or query.attrib.get("id") != "42":
        raise ValueError("Unexpected candidate XML")
    if query.attrib.get("name") != "candidate_read_setpoints.json":
        raise ValueError("Unexpected query name")
    request = query.find("request")
    response = query.find("response")
    if request is None or response is None:
        raise ValueError("Incomplete query")
    inp = request.find("list")
    out = response.find("list")
    if inp is None or out is None:
        raise ValueError("Missing list")
    if [(x.get("name"), x.get("type")) for x in inp.findall("parameter")] != [
        ("obj", "uint8"), ("address", "uint16")
    ]:
        raise ValueError("Unexpected request shape")
    if [(x.get("name"), x.get("type")) for x in out.findall("parameter")] != [
        ("value", "uint16")
    ]:
        raise ValueError("Unexpected response shape")
    return query


def read_addresses() -> tuple[int, ...]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    points = catalog["setpoints"]
    if len(points) != 12 or any(p["read_obj"] != 0 for p in points):
        raise ValueError("Unknown source catalog")
    found = tuple(p["read_address"] for p in points)
    if set(found) != VALID or len(found) != len(VALID):
        raise ValueError("Unexpected source addresses")
    return found


def request_bytes(addresses: tuple[int, ...]) -> bytes:
    """Matches the independent LAN source's byte representation.

    Not transmitted. A Nabto SDK could add different framing.
    """
    candidate_query()
    if not isinstance(addresses, tuple) or not 1 <= len(addresses) <= 12:
        raise ValueError("Read list needs 1..12 entries")
    if any(type(a) is not int or a not in VALID for a in addresses):
        raise ValueError("Unknown setpoint address")
    if len(set(addresses)) != len(addresses):
        raise ValueError("Duplicate read address")
    return b"\x00\x00\x00\x2a" + struct.pack(">H", len(addresses)) + b"".join(
        struct.pack(">BH", 0, address) for address in addresses
    ) + b"\x01"


def decode_community_response(frame: bytes, expected_count: int) -> tuple[int, tuple[int, ...]]:
    """Strictly parse the layout implied by the community LAN parser.

    Byte zero's meaning is *unknown*, so it is reported, not interpreted.
    A genuine Nabto RPC JSON response requires separate live verification.
    """
    if type(expected_count) is not int or not 1 <= expected_count <= 12:
        raise ValueError("Invalid read count")
    if type(frame) is not bytes or len(frame) != 3 + expected_count * 2:
        raise ValueError("Incorrect source-format response length")
    unknown_prefix = frame[0]
    count = struct.unpack(">H", frame[1:3])[0]
    if count != expected_count:
        raise ValueError("Response list count mismatch")
    return unknown_prefix, tuple(
        struct.unpack(">H", frame[3 + i * 2:5 + i * 2])[0]
        for i in range(expected_count)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address", type=int, default=7,
                        help="Offline read address to encode (default: fan level 7)")
    args = parser.parse_args()
    known = read_addresses()
    if args.address not in known:
        parser.error("Address not listed in Optima 270 source model")
    command = request_bytes((args.address,))
    print("RPC42_RECONSTRUCTION: CANDIDATE_OFFLINE_ONLY")
    print("QUERY_ID: 42")
    print("QUERY_NAME: candidate_read_setpoints.json")
    print("READ_OBJECT: 0")
    print("READ_ADDRESS:", args.address)
    print("LAN_SOURCE_PAYLOAD_HEX:", command.hex())
    print("REQUEST_MODEL: setpoints[{obj:uint8,address:uint16}],trailer:uint8")
    print("RESPONSE_MODEL: prefix_unknown:uint8,values[{value:uint16}]")
    print("REMOTE_SDK_XML_VERIFIED: NO")
    print("REMOTE_DEVICE_INVOKED: NO")
    print("RPC43_WRITE_IMPLEMENTED: NO")


if __name__ == "__main__":
    main()
