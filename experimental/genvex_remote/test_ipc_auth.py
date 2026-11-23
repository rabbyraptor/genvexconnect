"""Offline tests; no HTTP service, real network or persistent secret."""
import unittest

from ipc_auth import IPCAuthError, authorize_read, new_ipc_token


class IPCAuthTests(unittest.TestCase):
    def test_matching_token(self):
        token = new_ipc_token()
        self.assertGreaterEqual(len(token), 40)
        authorize_read(token, token)

    def test_random_tokens_differ(self):
        self.assertNotEqual(new_ipc_token(), new_ipc_token())

    def test_wrong_token_rejected(self):
        token = new_ipc_token()
        with self.assertRaises(IPCAuthError):
            authorize_read(token, new_ipc_token())

    def test_missing_token_rejected(self):
        with self.assertRaises(IPCAuthError):
            authorize_read(new_ipc_token(), None)

    def test_malformed_token_rejected(self):
        for invalid in ("", "short", "å" * 44, "x" * 200, 123):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(IPCAuthError):
                    authorize_read(new_ipc_token(), invalid)

    def test_does_not_echo_secret_in_error(self):
        token = new_ipc_token()
        with self.assertRaises(IPCAuthError) as context:
            authorize_read(token, new_ipc_token())
        self.assertNotIn(token, str(context.exception))


if __name__ == "__main__":
    unittest.main()
