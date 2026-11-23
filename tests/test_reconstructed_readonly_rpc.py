"""Offline structural comparison only; does not contact a device or load an SDK."""
import struct
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

XML = Path(__file__).parent / "fixtures" / "candidate_readonly_query45.xml"

def encode_candidate(query, data, trailer=1):
    """Simplified encoder following public uNabto integer/list encoding rules."""
    result = struct.pack(">I", int(query.attrib["id"]))
    result += struct.pack(">H", len(data))
    for item in data:
        result += struct.pack(">BI", item["obj"], item["address"])
    return result + struct.pack(">B", trailer)

def encode_known_local(data):
    """Reimplements GenvexCommandDatapointReadList.buildCommand from public LAN source."""
    elements = b"".join(bytes([obj]) + address.to_bytes(4, "big") for obj, address in data)
    return bytes([0, 0, 0, 45]) + len(data).to_bytes(2, "big") + elements + bytes([1])

class ReadonlyCandidateTests(unittest.TestCase):
    def setUp(self):
        root = ET.parse(XML).getroot()
        self.query, = root.findall("query")

    def test_candidate_only_has_known_read_opcode(self):
        self.assertEqual(self.query.attrib["id"], "45")
        self.assertIsNotNone(self.query.find("request/list"))
        self.assertEqual(self.query.find("response/list/parameter").attrib["type"], "int16")

    def test_known_temperature_example_matches_local_bytes(self):
        records = [(0, 20)]
        result = encode_candidate(self.query, [{"obj": 0, "address": 20}])
        self.assertEqual(result.hex(), "0000002d0001000000001401")
        self.assertEqual(result, encode_known_local(records))

    def test_three_local_addresses_match(self):
        records = [(0, 20), (0, 21), (0, 26)]
        model = [{"obj": obj, "address": address} for obj, address in records]
        self.assertEqual(encode_candidate(self.query, model), encode_known_local(records))

    def test_zero_length_would_not_be_sent(self):
        self.assertEqual(encode_candidate(self.query, []).hex(), "0000002d000001")

if __name__ == "__main__":
    unittest.main()
