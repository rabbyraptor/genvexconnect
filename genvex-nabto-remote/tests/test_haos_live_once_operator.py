"""No-network tests for the HAOS single-shot container launcher."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess

SCRIPT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT))
import haos_live_once_operator as launcher


class LauncherTests(unittest.TestCase):
    def test_container_args_do_not_contain_secrets(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(returncode=0)
        payload = b'{"device_id":"123456789012","identity":"hidden@example.com","unlock_secret":"private"}\n'
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, payload)
        self.assertEqual(len(calls), 2)
        cmd, kw = calls[0]
        self.assertEqual(kw["input"], payload)
        self.assertIn("--read-only", cmd)
        self.assertIn("--cap-drop", cmd)
        self.assertIn("--log-driver", cmd)
        self.assertEqual(cmd[cmd.index("--network") + 1], "bridge")
        self.assertEqual(cmd[cmd.index("--log-driver") + 1], "none")
        self.assertIn("readonly", " ".join(cmd))
        self.assertIn("sdk_snapshot_adapter.py", " ".join(cmd))
        for credential in (b"hidden@example.com", b"private", b"123456789012"):
            self.assertNotIn(credential, " ".join(cmd).encode())
        self.assertEqual(calls[1][0][1:3], ["rm", "-f"])

    def test_cleanup_even_on_timeout(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append(argv)
            if argv[1] == "run":
                raise subprocess.TimeoutExpired(argv, 110)
            return Mock(returncode=0)
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(subprocess.TimeoutExpired):
                launcher.run_once("sha256:" + "a" * 64, b"test\n")
        self.assertEqual(calls[-1][1:3], ["rm", "-f"])

    def test_resolves_image_without_stopped_container(self):
        image_id = "sha256:" + "a" * 64
        app = {"result":"ok", "data":{
            "version":"0.1.0-dev2", "state":"stopped", "boot":"manual",
            "options":{"diagnostic_only": True, "device_id":"",
                       "identity":"", "unlock_secret":"", "ipc_token":""}
        }}
        items = [
            '{"Repository":"local/aarch64-genvex_nabto_remote","Tag":"0.1.0-dev2","ID":"' + image_id + '"}',
            '{"Repository":"other/irrelevant","Tag":"0.1.0-dev2","ID":"sha256:other"}'
        ]
        def fake_run(argv, **kwargs):
            if argv[:3] == ["ha", "apps", "info"]:
                return Mock(returncode=0, stdout=json.dumps(app))
            if argv[:3] == ["docker", "inspect", "--type"]:
                return Mock(returncode=1, stdout="")
            if argv[:3] == ["docker", "image", "ls"]:
                return Mock(returncode=0, stdout="\n".join(items))
            if argv[:3] == ["docker", "image", "inspect"]:
                return Mock(returncode=0, stdout=json.dumps([{
                    "Id": image_id, "Architecture": "arm64",
                    "Config":{"Labels":{"io.hass.version":"0.1.0-dev2",
                                        "io.hass.type":"app"}}
                }]))
            raise AssertionError("Unexpected command")
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            self.assertEqual(launcher.checked_image(), image_id)

    def test_refuses_ambiguous_images(self):
        image1 = "sha256:" + "a" * 64
        image2 = "sha256:" + "b" * 64
        app = {"result":"ok", "data":{
            "version":"0.1.0-dev2", "state":"stopped", "boot":"manual",
            "options":{"diagnostic_only": True, "device_id":"",
                       "identity":"", "unlock_secret":"", "ipc_token":""}
        }}
        def fake_run(argv, **kwargs):
            if argv[0] == "ha":
                return Mock(returncode=0, stdout=json.dumps(app))
            if argv[:3] == ["docker", "inspect", "--type"]:
                return Mock(returncode=1, stdout="")
            if argv[:3] == ["docker", "image", "ls"]:
                lines = [json.dumps({
                    "Repository": "local/aarch64-genvex_nabto_remote",
                    "Tag":"0.1.0-dev2", "ID": value,
                }) for value in (image1, image2)]
                return Mock(returncode=0, stdout="\n".join(lines))
            raise AssertionError("Should not inspect an ambiguous image")
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                launcher.checked_image()


if __name__ == "__main__":
    unittest.main()
