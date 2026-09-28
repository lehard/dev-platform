from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repository_goal_scan", ROOT / "template" / "scripts" / "repository_goal_scan.py")
assert SPEC and SPEC.loader
scan = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scan
SPEC.loader.exec_module(scan)


class RepositoryGoalScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        (self.root / "src").mkdir()
        (self.root / "src" / "one.py").write_text("legacy_call()\nhealthy()\n", encoding="utf-8")
        (self.root / "src" / "two.py").write_text("legacy_call()\n", encoding="utf-8")
        (self.root / "skip.py").write_text("legacy_call()\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.root, check=True)
        self.profile = {"goal": "Find legacy calls", "question": "Which selected paths still call the old API?", "selection_confidence": "medium", "include": ["**/*.py"], "exclude": ["skip.py"], "limitations": ["No call graph"], "shard": {"max_candidates": 1}, "selectors": [{"id": "legacy", "type": "fixed", "pattern": "legacy_call"}]}
        self.run = self.root / ".dev-platform" / "repository-goal-scan" / "run"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_revision_bound_selection_is_deterministic_and_excludes_paths(self) -> None:
        first = scan.plan(self.root, self.profile, None, self.run)
        (self.root / "src" / "uncommitted.py").write_text("legacy_call()\n", encoding="utf-8")
        second = scan.plan(self.root, self.profile, None, self.run / "again")
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual([x["id"] for x in first["candidates"]], [x["id"] for x in second["candidates"]])
        self.assertEqual([x["path"] for x in first["candidates"]], ["src/one.py", "src/two.py"])
        self.assertEqual(len(first["batches"]), 2)
        self.assertEqual(first["selected_tracked_paths"], ["src/one.py", "src/two.py"])

    def test_result_accounting_blocks_incomplete_and_accepts_no_findings(self) -> None:
        manifest = scan.plan(self.root, self.profile, None, self.run)
        path = self.run / "manifest.json"
        pending = scan.finalize(path, self.run / "coverage.json")
        self.assertEqual(pending["status"], "incomplete")
        batch = manifest["batches"][0]
        bad = self.root / "bad.json"
        bad.write_text(json.dumps({"batch_id": batch["id"], "candidates": []}), encoding="utf-8")
        with self.assertRaisesRegex(scan.ScanError, "exactly once"):
            scan.record(path, batch["id"], bad)
        for batch in manifest["batches"]:
            result = self.root / f"{batch['id']}.json"
            result.write_text(json.dumps({"batch_id": batch["id"], "candidates": [{"id": candidate, "verdict": "no-finding"} for candidate in batch["candidate_ids"]]}), encoding="utf-8")
            scan.record(path, batch["id"], result)
        complete = scan.finalize(path, self.run / "coverage.json")
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(complete["selected_scope"]["coverage"], "100%")
        self.assertEqual(complete["selector_limitations"], ["No call graph"])
        self.assertEqual(complete["selection_confidence"], "medium")
        self.assertEqual(complete["exclusions"]["profile"], ["skip.py"])

    def test_tampered_manifest_and_result_cannot_claim_complete(self) -> None:
        manifest = scan.plan(self.root, self.profile, None, self.run)
        path = self.run / "manifest.json"
        batch = manifest["batches"][0]
        result = self.root / "result.json"
        result.write_text(json.dumps({"batch_id": batch["id"], "candidates": [{"id": batch["candidate_ids"][0], "verdict": "finding"}]}), encoding="utf-8")
        with self.assertRaisesRegex(scan.ScanError, "finding requires"):
            scan.record(path, batch["id"], result)
        result.write_text(json.dumps({"batch_id": batch["id"], "candidates": [{"id": batch["candidate_ids"][0], "verdict": "finding", "finding": {"description": "Old API", "evidence": "src/one.py:1", "priority": "P2", "confidence": "high"}}]}), encoding="utf-8")
        scan.record(path, batch["id"], result)
        stored = self.run / "results" / f"{batch['id']}.json"
        value = json.loads(stored.read_text(encoding="utf-8"))
        value["candidates"] = []
        stored.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(scan.ScanError, "exactly once"):
            scan.finalize(path, self.run / "coverage.json")
        stored.unlink()
        modified = json.loads(path.read_text(encoding="utf-8"))
        modified["batches"][0]["candidate_ids"] = []
        path.write_text(json.dumps(modified), encoding="utf-8")
        with self.assertRaisesRegex(scan.ScanError, "omitted"):
            scan.status(path)

    def test_failed_batch_blocks_completion(self) -> None:
        manifest = scan.plan(self.root, self.profile, None, self.run)
        failure = self.root / "failure.json"
        failure.write_text('{"error":"worker timeout"}', encoding="utf-8")
        scan.record(self.run / "manifest.json", manifest["batches"][0]["id"], failure, failed=True)
        self.assertFalse(scan.status(self.run / "manifest.json")["complete"])

    def test_selected_path_without_match_is_still_sharded(self) -> None:
        (self.root / "src" / "one.py").write_text("healthy()\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "no match"], cwd=self.root, check=True)
        manifest = scan.plan(self.root, self.profile, None, self.run)
        self.assertEqual(manifest["selected_tracked_paths"], ["src/one.py", "src/two.py"])
        self.assertEqual({item["path"] for item in manifest["candidates"]}, set(manifest["selected_tracked_paths"]))
        self.assertIn("no-text-match", {item["provenance"] for item in manifest["candidates"]})

    def test_mixed_finding_and_no_finding_complete_receipt(self) -> None:
        manifest = scan.plan(self.root, self.profile, None, self.run)
        path = self.run / "manifest.json"
        for index, batch in enumerate(manifest["batches"]):
            candidate = batch["candidate_ids"][0]
            verdict = {"id": candidate, "verdict": "no-finding"}
            if index == 0:
                verdict = {"id": candidate, "verdict": "finding", "finding": {"description": "Old API", "evidence": "src/one.py:1", "priority": "P2", "confidence": "high"}}
            result = self.root / f"result-{index}.json"
            result.write_text(json.dumps({"batch_id": batch["id"], "candidates": [verdict]}), encoding="utf-8")
            scan.record(path, batch["id"], result)
        receipt = scan.finalize(path, self.run / "coverage.json")
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["selected_scope"]["processed"], 2)
        self.assertEqual(receipt["selected_scope"]["coverage"], "100%")

    def test_plan_rejects_writes_outside_ignored_run_area(self) -> None:
        with self.assertRaisesRegex(scan.ScanError, "must be under"):
            scan.plan(self.root, self.profile, None, self.root / "source")


if __name__ == "__main__":
    unittest.main()
