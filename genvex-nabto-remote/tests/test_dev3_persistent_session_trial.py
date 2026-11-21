"""Offline contract checks for the opt-in persistent Micro Nabto session trial."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "runtime/probe_persistent_session_trial.py"

class PersistentSessionTrialContracts(unittest.TestCase):
    def test_compiles(self):
        compile(SOURCE.read_bytes(), str(SOURCE), "exec")

    def test_single_sdk_lifecycle_per_trial(self):
        tree = ast.parse(SOURCE.read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)]
        for function in ("startup", "open_session", "set_interface", "close_session", "shutdown"):
            matches = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == function]
            self.assertEqual(len(matches), 1, function)
        invocations = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "invoke"]
        self.assertEqual(len(invocations), 1)
        loop = next(n for n in ast.walk(main) if isinstance(n, ast.For) and
                    isinstance(n.iter, ast.Call) and isinstance(n.iter.func, ast.Name)
                    and n.iter.func.id == "range")
        self.assertEqual(loop.iter.args[0].value, 5)
        self.assertTrue(any(n in ast.walk(loop) for n in invocations))

    def test_only_five_allowed_addresses(self):
        tree = ast.parse(SOURCE.read_text())
        sensors = next(n for n in tree.body if isinstance(n, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == "SENSORS" for t in n.targets))
        self.assertEqual(ast.literal_eval(sensors.value), (20, 21, 22, 23, 26))

if __name__ == "__main__":
    unittest.main()
