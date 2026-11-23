"""Static safety checks for native ARM64 fake-profile container smoke script."""
import ast
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/test_remote_app_private_storage_container.sh"
WORKFLOW = ROOT / ".github/workflows/remote-app-image-build.yml"


class StorageContainerContractTests(unittest.TestCase):
    def test_shell_and_embedded_python_are_syntactically_valid(self):
        shell = subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True)
        self.assertEqual(shell.returncode, 0, shell.stderr.decode())
        source = SCRIPT.read_text()
        code = source.split(" -c '\n", 1)[1].split("\n'\necho", 1)[0]
        tree = ast.parse(code)
        byte_literals = [
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, bytes)
        ]
        certs = [v for v in byte_literals if v.startswith(b"-----BEGIN CERTIFICATE-----")]
        self.assertEqual(len(certs), 1)
        self.assertTrue(certs[0].endswith(b"-----END CERTIFICATE-----\n"))
        self.assertIn(b"\nFAKE-ONLY\n", certs[0])
        self.assertNotIn(b"\\n", certs[0])

    def test_no_network_mounts_or_real_profile(self):
        text = SCRIPT.read_text()
        workflow = WORKFLOW.read_text()
        self.assertIn("--network none", text)
        self.assertIn("--read-only", text)
        self.assertIn("--tmpfs /data:", text)
        self.assertIn("fake-only", text.lower())
        self.assertNotIn("/mnt/data", text)
        self.assertNotIn("/share/", text)
        self.assertNotIn("ha apps", text)
        self.assertNotIn("nabtoRpcInvoke", text)
        self.assertIn("sh scripts/test_remote_app_private_storage_container.sh", workflow)


if __name__ == "__main__":
    unittest.main()
