from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_dispatch_gate  # noqa: E402


class RolloutDispatchEnabledTests(unittest.TestCase):
    def test_disabled_for_absent_or_negative_values(self) -> None:
        for value in (None, "", "false", "False", "1", "yes", "  ", "0"):
            with self.subTest(value=value):
                self.assertFalse(rollout_dispatch_gate.rollout_dispatch_enabled(value))

    def test_enabled_for_true_case_insensitive_and_trimmed(self) -> None:
        for value in ("true", "True", "TRUE", " true ", "\ttrue\n"):
            with self.subTest(value=value):
                self.assertTrue(rollout_dispatch_gate.rollout_dispatch_enabled(value))

    def test_cli_prints_dispatch_false_by_default(self) -> None:
        env = {key: value for key, value in os.environ.items() if key != "DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED"}
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "rollout_dispatch_gate.py")],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("dispatch=false", result.stdout)
        self.assertIn("disabled/not configured", result.stderr)

    def test_cli_prints_dispatch_true_when_enabled(self) -> None:
        env = {**os.environ, "DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED": "true"}
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "rollout_dispatch_gate.py")],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("dispatch=true", result.stdout)
        self.assertIn("enabled", result.stderr)


if __name__ == "__main__":
    unittest.main()
