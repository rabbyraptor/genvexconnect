"""No-credential HAOS network preflight contracts."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import haos_app_network_preflight as probe


class NetworkPreflightTests(unittest.TestCase):
    def output(self, action):
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = action()
        return result, stream.getvalue()

    def test_expected_app_is_stopped_and_manual(self):
        with patch.object(probe, "command", return_value=(
            0, '{"result":"ok","data":{"slug":"local_genvex_nabto_remote","boot":"manual",'
               '"host_network":false,"state":"stopped"}}'
        )):
            result, output = self.output(probe.check_app_metadata)
        self.assertEqual(result, (True, True))
        self.assertIn("PASS: APP_METADATA_MANUAL_ONLY_PRIVATE_NETWORK", output)

    def test_rejects_auto_boot_and_host_network(self):
        for boot, host in (("auto", False), ("manual", True)):
            with self.subTest(boot=boot, host=host), patch.object(
                probe, "command", return_value=(0, (
                    '{"result":"ok","data":{"slug":"local_genvex_nabto_remote","boot":"%s",'
                    '"host_network":%s,"state":"stopped"}}'
                    % (boot, str(host).lower())
                )),
            ):
                result, output = self.output(probe.check_app_metadata)
                self.assertEqual(result, (False, False))
                self.assertIn("BLOCKED: APP_SAFETY_SETTINGS_MISMATCH", output)

    def test_never_prints_raw_untrusted_output(self):
        with patch.object(probe, "command", return_value=(
            0, '{"result":"ok","data":{"slug":"unknown","unlock_secret":"SENSITIVE_MARKER"}}'
        )):
            _, output = self.output(probe.check_app_metadata)
        self.assertNotIn("SENSITIVE_MARKER", output)

    def test_core_must_be_running_in_host_mode(self):
        with patch.object(probe, "inspect", return_value={
            "State": {"Running": True},
            "HostConfig": {"NetworkMode": "host"},
        }):
            result, output = self.output(probe.check_core)
        self.assertTrue(result)
        self.assertIn("PASS: CORE_RUNNING_HOST_NETWORK", output)

    def test_stopped_app_must_not_publish_ports(self):
        with patch.object(probe, "inspect", return_value={
            "State": {"Running": False},
            "HostConfig": {
                "NetworkMode": "hassio",
                "PortBindings": {"18275/tcp": [{"HostPort": "18275"}]},
            },
            "NetworkSettings": {"Networks": {"hassio": {}}},
        }):
            _, output = self.output(probe.check_app_container)
        self.assertIn("BLOCKED: APP_HOST_PORT_BINDING", output)

    def test_dns_reports_only_fixed_markers(self):
        with patch.object(probe, "command", return_value=(
            1, "SENSITIVE_MARKER"
        )):
            _, output = self.output(probe.check_dns)
        self.assertEqual(output.strip(), "INFO: APP_DNS_UNRESOLVED_OR_UNAVAILABLE")

    def test_main_fails_closed_on_metadata(self):
        with patch.object(probe.os, "geteuid", return_value=0), \
             patch.object(sys, "argv", ["preflight"]), \
             patch.object(probe, "check_app_metadata", return_value=(False, False)), \
             patch.object(probe, "check_core", return_value=True), \
             patch.object(probe, "check_dns") as dns:
            result, output = self.output(probe.main)
        self.assertEqual(result, 1)
        dns.assert_not_called()
        self.assertIn("BLOCKED: PREFLIGHT_INCOMPLETE", output)


if __name__ == "__main__":
    unittest.main()
