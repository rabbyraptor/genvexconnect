"""Fake-only IPC token initialization tests. No Core/App networking."""
from pathlib import Path
import stat
import tempfile
import unittest

from ipc_token_store import PrivateIPCTokenStore, TokenStoreError


class IPCTokenStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"
        self.root.mkdir(mode=0o700)
        self.store = PrivateIPCTokenStore(self.root)

    def test_first_start_and_restart_reuse_token(self):
        first = self.store.ensure()
        second = self.store.ensure()
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 40)
        self.assertEqual(first, self.store.read())
        self.assertEqual(
            stat.S_IMODE((self.root / "ipc-token").stat().st_mode), 0o600
        )

    def test_reject_unsafe_token_without_replacement(self):
        token_file = self.root / "ipc-token"
        token_file.write_text("not a token")
        token_file.chmod(0o600)
        with self.assertRaises(TokenStoreError):
            self.store.ensure()
        self.assertEqual(token_file.read_text(), "not a token")

    def test_reject_symlink_and_keep_target(self):
        target = self.root / "target"
        target.write_text("NOT_A_TOKEN")
        (self.root / "ipc-token").symlink_to(target)
        with self.assertRaises(TokenStoreError):
            self.store.ensure()
        self.assertEqual(target.read_text(), "NOT_A_TOKEN")

    def test_reject_shared_permissions(self):
        self.root.chmod(0o755)
        with self.assertRaises(TokenStoreError):
            self.store.ensure()

    def test_reject_token_readable_by_others(self):
        token = self.store.ensure()
        path = self.root / "ipc-token"
        path.chmod(0o644)
        with self.assertRaises(TokenStoreError):
            self.store.read()
        with self.assertRaises(TokenStoreError):
            self.store.ensure()
        self.assertEqual(path.read_text().strip(), token)


if __name__ == "__main__":
    unittest.main()
