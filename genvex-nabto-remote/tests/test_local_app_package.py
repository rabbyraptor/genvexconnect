"""Safe local App source-only release package tests (no HAOS)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tarfile
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts" / "package_remote_diagnostic_app.py"
spec = importlib.util.spec_from_file_location("remote_source_package", SRC)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class LocalAppPackageTests(unittest.TestCase):
    def test_staging_script_safe_explicit_opt_in(self):
        script = ROOT / "scripts" / "stage_remote_diagnostic_app_source.sh"
        syntax = subprocess.run(["bash", "-n", str(script)], capture_output=True)
        self.assertEqual(syntax.returncode, 0, syntax.stderr.decode())
        content = script.read_text()
        self.assertIn('MODE=$1', content)
        self.assertIn('if [ "$MODE" = "--preflight" ]; then', content)
        self.assertIn('case "$MODE" in --preflight|--stage)', content)
        self.assertIn("genvex-nabto-remote-local-app-source.tar.gz", content)
        self.assertIn("sha256sum --check", content)
        self.assertIn("test ! -e", content)
        self.assertIn("test ! -L", content)
        self.assertIn("Supervisor not reloaded", content)
        self.assertIn("trap cleanup EXIT", content)
        self.assertIn("cleanup() { rm -rf --", content)
        self.assertNotIn("ha apps install", content)
        self.assertNotIn("ha apps start", content)
        self.assertNotIn("docker run", content)

    def test_read_only_stage_preflight_with_fake_ssh(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            out = temp / "artifact"
            out.mkdir()
            with (
                patch.object(packager, "DEST", out),
                patch.object(packager, "ARCHIVE", out / "genvex-nabto-remote-local-app-source.tar.gz"),
            ):
                archive = packager.create_archive()
            home = temp / "home"
            keydir = home / ".ssh"
            keydir.mkdir(parents=True)
            (keydir / "id_ed25519").write_text("FAKE-KEY-FOR-OFFLINE-TEST")
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            shim = bin_dir / "ssh"
            calls = temp / "ssh-calls"
            shim.write_text(chr(10).join((
                "#!/bin/sh",
                'echo "$*" >> "$FAKE_SSH_CALLS"',
                "exit 0",
            )) + chr(10))
            shim.chmod(0o755)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["FAKE_SSH_CALLS"] = str(calls)
            proc = subprocess.run(
                [
                    "bash", str(ROOT / "scripts/stage_remote_diagnostic_app_source.sh"),
                    "--preflight", str(archive), str(out / "APP_SOURCE_SHA256SUMS"),
                ],
                capture_output=True, text=True, env=env, timeout=15,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("preflight only; no remote files changed", proc.stdout)
            self.assertEqual(len(calls.read_text().splitlines()), 1)
            self.assertIn("test ! -e", calls.read_text())

    def test_allowlist_excludes_credentials_and_unknown_files(self):
        paths = packager.archive_sources()
        rels = {p.relative_to(packager.SOURCE).as_posix() for p in paths}
        self.assertTrue({"config.yaml", "Dockerfile", "run.sh"}.issubset(rels))
        self.assertIn("runtime/app_bootstrap.py", rels)
        self.assertIn("runtime/diagnostic_http_server.py", rels)
        self.assertIn("runtime/offline_ipc_network_smoke.py", rels)
        self.assertFalse(any(
            name.endswith((".crt", ".key", ".json", ".pem"))
            for name in rels
        ))
        self.assertTrue(all(name.startswith("runtime/") or name in (
            "config.yaml", "Dockerfile", "run.sh"
        ) for name in rels))

    def test_archive_is_single_app_folder_regular_files_and_private_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory)
            with (
                patch.object(packager, "DEST", dest),
                patch.object(packager, "ARCHIVE", dest / "source.tar.gz"),
            ):
                archive = packager.create_archive()
                self.assertTrue(archive.exists())
                self.assertTrue((dest / "APP_SOURCE_SHA256SUMS").exists())
                with tarfile.open(archive, "r:gz") as stream:
                    members = stream.getmembers()
                    self.assertTrue(members)
                    self.assertTrue(all(m.isfile() and not m.issym() and not m.islnk() for m in members))
                    self.assertTrue(all(m.name.startswith("genvex_nabto_remote/") for m in members))
                    self.assertTrue(all(".." not in Path(m.name).parts for m in members))
                    self.assertEqual(len({m.name for m in members}), len(members))
                    self.assertEqual(next(m.mode for m in members if m.name.endswith("/run.sh")), 0o755)
                    yaml = stream.extractfile("genvex_nabto_remote/config.yaml").read()
                    self.assertIn(b"diagnostic_only: false", yaml)
                    self.assertIn(b"host_network: false", yaml)
                    self.assertIn(b"boot: manual_only", yaml)


if __name__ == "__main__":
    unittest.main()
