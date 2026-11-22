"""Offline fixture tests for proposed MCP development primitives."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from policy import (
    ALLOWED_FILES, DevMCPRejected,
    preview_runtime_patch, run_allowlisted_offline_test,
)


class DevMCPPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = self.root / "genvex-nabto-remote/runtime"
        self.runtime.mkdir(parents=True)
        self.path = self.runtime / "app_bootstrap.py"
        self.original = b"VALUE = 1\n"
        self.path.write_bytes(self.original)
        self.sha = hashlib.sha256(self.original).hexdigest()

    def preview(self, **changes):
        options = {
            "root": self.root,
            "filename": "app_bootstrap.py",
            "expected_sha256": self.sha,
            "replacement": "VALUE = 2\n",
        }
        options.update(changes)
        return preview_runtime_patch(**options)

    def test_preview_hashes_syntax_and_does_not_modify_file(self):
        result = self.preview()
        self.assertEqual(result.filename, "app_bootstrap.py")
        self.assertEqual(result.old_sha256, self.sha)
        self.assertEqual(result.new_sha256, hashlib.sha256(b"VALUE = 2\n").hexdigest())
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_every_runtime_name_is_explicit(self):
        self.assertEqual(len(ALLOWED_FILES), 13)
        self.assertNotIn("server.py", ALLOWED_FILES)
        self.assertNotIn("__init__.py", ALLOWED_FILES)

    def test_rejects_unknown_paths_and_bad_hash(self):
        for name in ("../server.py", "/srv/server.py", ".hidden.py", "unknown.py"):
            with self.subTest(name=name), self.assertRaises(DevMCPRejected):
                self.preview(filename=name)
        with self.assertRaises(DevMCPRejected):
            self.preview(expected_sha256="0" * 64)
        with self.assertRaises(DevMCPRejected):
            self.preview(expected_sha256="g" * 64)

    def test_rejects_bad_python_and_oversize(self):
        for replacement in ("def x(:\n", "", "x = 1\x00\n", "x = 1\n" * 40000):
            with self.subTest(length=len(replacement)), self.assertRaises(DevMCPRejected):
                self.preview(replacement=replacement)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_symlink_not_followed(self):
        self.path.unlink()
        target = self.root / "outside.py"
        target.write_bytes(self.original)
        self.path.symlink_to(target)
        with self.assertRaises(DevMCPRejected):
            self.preview()
        self.assertEqual(target.read_bytes(), self.original)

    def test_modified_source_must_be_reinspected(self):
        self.path.write_bytes(b"VALUE = 3\n")
        with self.assertRaises(DevMCPRejected):
            self.preview()

    def test_only_preapproved_test_selectors_run(self):
        for invalid in ("../tmp", "shell", "", None, 1):
            with self.subTest(selector=invalid), self.assertRaises(DevMCPRejected):
                run_allowlisted_offline_test(root=self.root, test_id=invalid)

    def test_offline_unittest_succeeds_without_log_output(self):
        tests = self.root / "genvex-nabto-remote/tests"
        tests.mkdir()
        (tests / "test_fixture.py").write_text(
            "import unittest\n"
            "class SafeTests(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertEqual(2 + 2, 4)\n"
        )
        result = run_allowlisted_offline_test(
            root=self.root, test_id="remote_app", timeout_seconds=10
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.test_count, 1)

    def test_failed_test_does_not_expose_fixture_secret(self):
        tests = self.root / "genvex-nabto-remote/tests"
        tests.mkdir()
        (tests / "test_fixture.py").write_text(
            "import unittest\n"
            "class SafeTests(unittest.TestCase):\n"
            "    def test_failure(self):\n"
            "        self.fail('FAKE_SECRET_NEVER_RETURN')\n"
        )
        result = run_allowlisted_offline_test(
            root=self.root, test_id="remote_app", timeout_seconds=10
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.test_count, 1)
        self.assertNotIn("FAKE_SECRET_NEVER_RETURN", repr(result))


if __name__ == "__main__":
    unittest.main()
