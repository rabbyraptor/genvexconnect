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

    def test_show_values_flag_contains_no_credentials(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(returncode=0)
        payload = b'{"device_id":"123456789012","identity":"hidden@example.com","unlock_secret":"private"}\\n'
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, payload, show_values=True)
        cmd, kw = calls[0]
        self.assertEqual(cmd[-1], "--show-values")
        self.assertEqual(cmd.count("--show-values"), 1)
        self.assertNotIn("hidden@example.com", " ".join(cmd))
        self.assertNotIn("private", " ".join(cmd))
        self.assertEqual(kw["input"], payload)
        self.assertEqual(calls[1][0][1:3], ["rm", "-f"])

    def test_default_display_is_opt_in(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append(argv)
            return Mock(returncode=0)
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, b"fake\\n")
        self.assertNotIn("--show-values", calls[0])

    def test_bounded_trial_three_attempts_and_two_gaps(self):
        image = "sha256:" + "a" * 64
        sleeps = []
        with patch.object(launcher, "preflight", return_value=image) as preflight, \
             patch.object(launcher, "run_once") as run_once, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(launcher.bounded_trial(
                image, b"secret-only-via-stdin", sleep=sleeps.append
            ))
        self.assertEqual(preflight.call_count, 3)
        self.assertEqual(run_once.call_count, 3)
        self.assertEqual(sleeps, [60, 60])
        self.assertIn("TRIAL SUMMARY: 3/3 validated", output.getvalue())
        self.assertNotIn("secret-only-via-stdin", output.getvalue())

    def test_bounded_trial_reports_partial_success_without_retries(self):
        image = "sha256:" + "a" * 64
        sleeps = []
        with patch.object(launcher, "preflight", return_value=image), \
             patch.object(launcher, "run_once",
                          side_effect=[None, RuntimeError("no connection"), None]) as probe, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertFalse(launcher.bounded_trial(image, b"private", sleep=sleeps.append))
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(sleeps, [60, 60])
        self.assertIn("TRIAL 2/3: FAILED", output.getvalue())
        self.assertIn("TRIAL SUMMARY: 2/3 validated", output.getvalue())
        self.assertNotIn("no connection", output.getvalue())
        self.assertNotIn("private", output.getvalue())

    def test_bounded_trial_aborts_on_changed_app_state(self):
        image = "sha256:" + "a" * 64
        other = "sha256:" + "b" * 64
        with patch.object(launcher, "preflight", side_effect=[image, other]), \
             patch.object(launcher, "run_once") as probe:
            with self.assertRaises(RuntimeError):
                launcher.bounded_trial(image, b"private", sleep=lambda _: None)
        probe.assert_called_once()

    def test_manual_recovery_mounts_policy_and_increases_only_its_timeout(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(returncode=0)
        payload = b"credential-stays-on-stdin"
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, payload, recover_once=True)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd[-1], "--recover-once")
        self.assertIn("recovery_policy.py,readonly", " ".join(cmd))
        self.assertEqual(kwargs["timeout"], 260)
        self.assertEqual(kwargs["input"], payload)
        self.assertNotIn("credential-stays-on-stdin", " ".join(cmd))
        self.assertEqual(calls[1][0][1:3], ["rm", "-f"])

    def test_normal_timeout_and_flags_unchanged(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(returncode=0)
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, b"private")
        self.assertEqual(calls[0][1]["timeout"], 110)
        self.assertNotIn("--recover-once", calls[0][0])

    def test_diagnostic_flag_forwarded_without_credentials(self):
        calls = []
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return Mock(returncode=0)
        payload = b"private-input-only"
        with patch.object(launcher.subprocess, "run", side_effect=fake_run):
            launcher.run_once("sha256:" + "a" * 64, payload, diagnose=True)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd[-1], "--diagnose")
        self.assertNotIn("private-input-only", " ".join(cmd))
        self.assertEqual(kwargs["input"], payload)
        self.assertEqual(calls[1][0][1:3], ["rm", "-f"])

    def test_explicit_recovery_trial_is_three_bounded_invocations(self):
        image = "sha256:" + "a" * 64
        sleeps = []
        with patch.object(launcher, "preflight", return_value=image) as preflight, \
             patch.object(launcher, "run_once") as run_once, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(launcher.bounded_trial(
                image, b"private", sleep=sleeps.append, recover_once=True
            ))
        self.assertEqual(preflight.call_count, 3)
        self.assertEqual(run_once.call_count, 3)
        self.assertTrue(all(c.kwargs == {"recover_once": True}
                            for c in run_once.call_args_list))
        self.assertEqual(sleeps, [60, 60])
        self.assertIn("TRIAL SUMMARY: 3/3 validated", output.getvalue())
        self.assertNotIn("private", output.getvalue())

    def test_recovery_trial_failed_read_does_not_add_host_retry(self):
        image = "sha256:" + "a" * 64
        sleeps = []
        with patch.object(launcher, "preflight", return_value=image), \
             patch.object(launcher, "run_once",
                          side_effect=[RuntimeError("secret"), None, None]) as run_once, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertFalse(launcher.bounded_trial(
                image, b"private", sleep=sleeps.append, recover_once=True
            ))
        self.assertEqual(run_once.call_count, 3)
        self.assertEqual(sleeps, [60, 60])
        self.assertIn("TRIAL SUMMARY: 2/3 validated", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_diagnostic_trial_keeps_exact_three_attempts(self):
        image = "sha256:" + "a" * 64
        sleeps = []
        with patch.object(launcher, "preflight", return_value=image), \
             patch.object(launcher, "run_once") as run_once, \
             patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(launcher.bounded_trial(
                image, b"private", sleep=sleeps.append, diagnose=True
            ))
        self.assertEqual(run_once.call_count, 3)
        self.assertTrue(all(c.kwargs == {"diagnose": True} for c in run_once.call_args_list))
        self.assertEqual(sleeps, [60, 60])
        self.assertNotIn("private", output.getvalue())


if __name__ == "__main__":
    unittest.main()
