"""Offline-only structural checks for one read-only five-item Nabto query."""
import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_remote_sensors_batch_phase1b.py"

class BatchPhase1BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf8")
        cls.tree = ast.parse(cls.source)
        cls.bindings = {}
        for node in cls.tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in ("SENSORS", "SCHEMA"):
                    cls.bindings[target.id] = ast.literal_eval(node.value)

    def test_only_five_source_defined_addresses(self):
        self.assertEqual([a for a, *_ in self.bindings["SENSORS"]], [20, 21, 22, 23, 26])

    def test_read_only_query_id_45_only(self):
        root = ET.fromstring(self.bindings["SCHEMA"])
        qs = root.findall("query")
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].get("id"), "45")

    def test_list_has_expected_fields_and_response_type(self):
        root = ET.fromstring(self.bindings["SCHEMA"])
        self.assertEqual([p.get("type") for p in root.findall("query/request/list/parameter")],
                         ["uint8", "uint32"])
        self.assertEqual(root.find("query/request/parameter").get("default"), "1")
        self.assertEqual(root.find("query/response/list/parameter").get("type"), "int16")

    def test_no_write_rpc(self):
        self.assertNotIn("nabtoRpcInvokeWrite", self.source)
        self.assertNotIn('id="43"', self.source)

    def test_one_call_site_to_invoke(self):
        nodes = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "invoke"]
        self.assertEqual(len(nodes), 1)

if __name__ == "__main__":
    unittest.main()
