"""Static guardrail checks: no SDK, no network, no credentials needed."""
import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_remote_sensors_phase1.py"

class Phase1SchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        cls.constants = {}
        for node in cls.module.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("SENSORS", "SCHEMA"):
                    cls.constants[node.targets[0].id] = ast.literal_eval(node.value)

    def test_only_known_five_addresses(self):
        sensors = self.constants["SENSORS"]
        self.assertEqual([item[0] for item in sensors], [20, 21, 22, 23, 26])
        self.assertTrue(all(len(item) == 5 for item in sensors))
        self.assertTrue(all(item[2] > 0 for item in sensors))

    def test_only_readonly_rpc_query_id(self):
        xml = ET.fromstring(self.constants["SCHEMA"])
        queries = xml.findall("query")
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].attrib["id"], "45")
        req = queries[0].find("request")
        self.assertEqual(req.find("list/parameter").get("type"), "uint8")
        self.assertEqual(req.findall("list/parameter")[1].get("type"), "uint32")
        self.assertEqual(req.find("parameter").get("default"), "1")

    def test_one_signed_int16_response(self):
        xml = ET.fromstring(self.constants["SCHEMA"])
        self.assertEqual(xml.find("query/response/list/parameter").get("type"), "int16")

    def test_no_write_opcode_in_script(self):
        body = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("nabtoRpcInvokeWrite", body)
        self.assertNotIn("id=\"43\"", body)
        self.assertNotIn("setpoint_writelist", body.lower())

if __name__ == "__main__":
    unittest.main()
