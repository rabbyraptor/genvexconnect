"""Static contract: HA consumer endpoint must match Supervisor App slug.

This test needs no HA Core, Docker daemon, network or real credentials.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "genvex-nabto-remote/config.yaml"
HA_CLIENT = ROOT / "experimental/home_assistant/custom_components/genvex_remote/runtime_client.py"


def parse_app_slug() -> str:
    # The App config has a simple scalar slug line; no third-party YAML needed.
    matches = [
        line.split(":", 1)[1].strip().strip("'\"")
        for line in CONFIG.read_text().splitlines()
        if line.startswith("slug:")
    ]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous App slug")
    return matches[0]


def parse_expected_endpoint() -> str:
    tree = ast.parse(HA_CLIENT.read_text())
    values = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "EXPECTED_APP_ENDPOINT"
            for target in node.targets
        )
    ]
    if len(values) != 1:
        raise ValueError("Missing or ambiguous pinned endpoint")
    return values[0]


class AppDNSContractTests(unittest.TestCase):
    def test_supervisor_local_app_alias_matches_pinned_endpoint(self):
        slug = parse_app_slug()
        self.assertEqual(slug, "genvex_nabto_remote")
        expected = f"http://local-{slug.replace('_', '-')}:18275/v1/snapshot"
        self.assertEqual(parse_expected_endpoint(), expected)

    def test_no_host_network_or_published_ports(self):
        config = CONFIG.read_text()
        self.assertIn("host_network: false", config)
        self.assertNotIn("\nports:", config)
        self.assertNotIn("\nports_description:", config)
        self.assertNotIn("\nmap:", config)


if __name__ == "__main__":
    unittest.main()
