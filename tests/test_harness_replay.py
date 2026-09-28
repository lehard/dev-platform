from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import harness_replay  # noqa: E402


SUITE = ROOT / "dev-platform" / "harness-replay" / "cases.json"
FIXTURES = SUITE.parent / "fixtures"


class HarnessReplayTests(unittest.TestCase):
    def test_frozen_suite_has_five_reconstructable_cases(self) -> None:
        suite = harness_replay.load_suite(SUITE)
        report = harness_replay.validate_suite(ROOT, suite)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(len(report["cases"]), 5)

    def test_capability_failure_cannot_promote_its_resource_reduction(self) -> None:
        suite = harness_replay.load_suite(SUITE)
        report = harness_replay.evaluate(ROOT, suite, FIXTURES / "capability-breaking-candidate.json")
        self.assertEqual(report["capability_gate"], "failed")
        self.assertFalse(report["positive_efficiency_conclusion"])
        broken = report["cases"][0]
        self.assertEqual(broken["efficiency"]["status"], "not-evaluated")
        self.assertNotIn("payload_bytes", broken["efficiency"])

    def test_capability_equivalent_candidate_keeps_missing_metrics_unknown(self) -> None:
        suite = harness_replay.load_suite(SUITE)
        report = harness_replay.evaluate(ROOT, suite, FIXTURES / "capability-equivalent-candidate.json")
        self.assertEqual(report["capability_gate"], "passed")
        self.assertEqual(report["cases"][0]["efficiency"]["payload_bytes"]["status"], "unknown")
        self.assertEqual(report["cases"][0]["efficiency"]["wall_time_seconds"]["status"], "comparable")
        self.assertEqual(report["cases"][0]["efficiency"]["wall_time_seconds"]["delta"], 0)
        self.assertFalse(report["positive_efficiency_conclusion"])
        self.assertEqual(report["efficiency_evidence"], "available")
        self.assertEqual(report["candidate_evidence"], "pinned-historical-control")
        self.assertTrue(report["advisory"])
        self.assertIn("routing", report["non_effects"])

    def test_unreviewed_candidate_saving_remains_advisory(self) -> None:
        suite = harness_replay.load_suite(SUITE)
        candidate = json.loads((FIXTURES / "capability-equivalent-candidate.json").read_text(encoding="utf-8"))
        candidate["harness_changes"] = ["lazy-capability-definitions", "reduced-delegation-guidance", "cache-friendly-boundaries"]
        candidate["results"][0]["metrics"]["wall_time_seconds"] = 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            report = harness_replay.evaluate(ROOT, suite, path)
        self.assertEqual(report["capability_gate"], "passed")
        self.assertEqual(report["candidate_evidence"], "supplied-external-observation")
        self.assertLess(report["cases"][0]["efficiency"]["wall_time_seconds"]["delta"], 0)
        self.assertFalse(report["positive_efficiency_conclusion"])

    def test_suite_drift_is_rejected(self) -> None:
        changed = json.loads(SUITE.read_text(encoding="utf-8"))
        changed["cases"][0]["work_shape"] = "rewritten held-out case"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drift.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(harness_replay.ReplayError, "frozen-case drift"):
                harness_replay.load_suite(path)

    def test_isolated_clone_does_not_change_source_checkout(self) -> None:
        suite = harness_replay.load_suite(SUITE)
        before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        with harness_replay.isolated_workspace(ROOT, suite["cases"][0]["source_revision"]) as clone:
            self.assertEqual(
                subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone, text=True, capture_output=True, check=True).stdout.strip(),
                suite["cases"][0]["source_revision"],
            )
        after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
