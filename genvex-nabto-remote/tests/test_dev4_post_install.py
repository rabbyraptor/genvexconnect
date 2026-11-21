"""Pure offline tests for DEV4 post-install P.5 metadata checks."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("dev4_p5", SCRIPTS / "dev4_post_install_verify.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def row(slug: str, date: str) -> dict:
    return {"slug": slug, "date": date}


class P5Tests(unittest.TestCase):
    def test_find_new_partial_backup_with_previous_dev3_app(self):
        rows = [
            row("oldbackup1", "2026-11-20T23:14:57Z"),
            row("newbackup1", "2026-11-22T00:18:00Z"),
        ]
        seen = []
        def detail(slug):
            seen.append(slug)
            return {"type": "partial", "apps": [
                {"slug": "local_genvex_nabto_remote", "version": "0.1.0-dev3"}
            ]}
        found = gate.find_backup(rows, detail)
        self.assertEqual(found[0], "newbackup1")
        self.assertEqual(seen, ["newbackup1"])

    def test_reject_previous_backup_or_unrelated_app(self):
        rows = [
            row("oldbackup1", "2026-11-20T23:14:57Z"),
            row("unrelated1", "2026-11-22T00:18:00Z"),
        ]
        self.assertIsNone(gate.find_backup(
            rows, lambda _: {"type": "partial", "apps": [{"slug": "other_app"}]}
        ))

    def test_addons_alias_supported(self):
        self.assertTrue(gate.included_app({
            "addons": ["local_genvex_nabto_remote"]
        }))
        self.assertFalse(gate.included_app({"addons": None}))

    def test_older_or_unparseable_dates_excluded(self):
        seen = []
        result = gate.find_backup(
            [row("bogus", "not-a-date"), row("older01", "2026-11-19T00:00:00Z")],
            lambda slug: seen.append(slug),
        )
        self.assertIsNone(result)
        self.assertEqual(seen, [])

    def test_verifier_is_readonly(self):
        source = (SCRIPTS / "dev4_post_install_verify.py").read_text()
        for excluded in ('"ha", "apps", "start"', '"ha", "apps", "stop"',
                         '"ha", "apps", "update"', '"ha", "store", "reload"'):
            self.assertNotIn(excluded, source)
        self.assertIn('verify_source_tree(BACKUP_SOURCE)', source)


if __name__ == "__main__":
    unittest.main()
