from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "template" / "scripts" / "dev.py"
SPEC = importlib.util.spec_from_file_location("template_dev", MODULE_PATH)
assert SPEC and SPEC.loader
dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dev)


class DevEntrypointTests(unittest.TestCase):
    def test_ready_profile_contains_verify_and_full_workflow(self) -> None:
        config = dev.openspec_profile()
        self.assertEqual(config["profile"], "custom")
        self.assertEqual(config["delivery"], "both")
        workflows = config["workflows"]
        self.assertIn("verify", workflows)
        self.assertIn("new", workflows)
        self.assertIn("continue", workflows)
        self.assertIn("onboard", workflows)


if __name__ == "__main__":
    unittest.main()
