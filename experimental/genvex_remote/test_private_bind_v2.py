"""Offline opt-in private bind policy regressions: no Nabto or HAOS SDK."""
import unittest

from private_bind_v2 import INTERNAL_PORT, validate_v2_bind
from runtime_v2_draft import ExperimentalV2Runtime
from v2_polling_state import ReadOnlyV2Poller
from ipc_auth import new_ipc_token


class PrivateBindPolicyTests(unittest.TestCase):
    def test_loopback_default(self):
        for port in (0, 1024, INTERNAL_PORT, 65535):
            validate_v2_bind("127.0.0.1", port)
        for port in (-1, 1, 65536, True, "18275"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                validate_v2_bind("127.0.0.1", port)

    def test_explicit_private_ip_and_fixed_port_only(self):
        for host in ("10.0.0.42", "172.16.0.1", "172.30.33.5", "192.168.1.21"):
            with self.subTest(host=host):
                validate_v2_bind(host, INTERNAL_PORT, private_opt_in=True)
                for port, enabled in ((0, True), (18276, True),
                                      (INTERNAL_PORT, False)):
                    with self.assertRaises(ValueError):
                        validate_v2_bind(host, port, private_opt_in=enabled)

    def test_reject_wildcard_public_hostname_ipv6_and_tricks(self):
        for host in ("0.0.0.0", "::", "::1", "localhost",
                     "local-genvex-nabto-remote", "8.8.8.8",
                     "169.254.1.1", "127.0.0.2", "10.0.0.1/8",
                     "172.32.1.1", "192.169.1.1", "", None,
                     " 172.30.1.1", "172.30.1.1\n"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_v2_bind(host, INTERNAL_PORT, private_opt_in=True)

    def test_runtime_explicit_opt_in_constructor_is_inert(self):
        async def read(_host, _addresses):
            return (368, 308, 322, 380, 66, 6000, 5800)
        device = "123456789012"
        adapter = ReadOnlyV2Poller(device_id=device, reader=read)
        token = new_ipc_token()
        with self.assertRaises(ValueError):
            ExperimentalV2Runtime(device_id=device, adapter=adapter, token=token,
                                  bind_host="172.30.1.2", port=INTERNAL_PORT)
        runtime = ExperimentalV2Runtime(
            device_id=device, adapter=adapter, token=token,
            bind_host="172.30.1.2", port=INTERNAL_PORT,
            private_opt_in=True,
        )
        self.assertFalse(runtime.running)
        self.assertIsNone(runtime.local_port)
        self.assertIsNone(runtime.state.current())


if __name__ == "__main__":
    unittest.main()
