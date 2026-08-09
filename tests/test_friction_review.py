from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

spec = importlib.util.spec_from_file_location("agent_friction_under_test", SCRIPT_ROOT / "agent_friction.py")
agent_friction = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = agent_friction
spec.loader.exec_module(agent_friction)


class FrictionReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude" / "agent-friction.jsonl"
        self.state = self.root / ".claude" / "agent-friction-state.json"
        self.reports = self.root / ".claude" / "reports" / "process-improvement"
        self.log.parent.mkdir(parents=True)
        agent_friction.main_root = lambda: self.root
        agent_friction.log_path = lambda: self.log
        agent_friction.state_path = lambda: self.state
        agent_friction.reports_dir = lambda: self.reports

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_events(self, count: int, *, severity: str = "medium") -> list[str]:
        ids: list[str] = []
        with self.log.open("w", encoding="utf-8") as fh:
            for index in range(count):
                event_id = f"event-{index + 1}"
                ids.append(event_id)
                fh.write(
                    json.dumps(
                        {
                            "id": event_id,
                            "at": f"2026-08-{index + 1:02d}T10:00:00+00:00",
                            "category": "repeated-error",
                            "triggers": ["repeated-error"],
                            "severity": severity,
                            "observation": "agent repeated a failed operation",
                            "evidence": "same command failed twice",
                            "hypothesis": "missing process guard",
                            "scope": "platform",
                            "proposal": "add a deterministic guard",
                        }
                    )
                    + "\n"
                )
        return ids

    def test_secret_like_values_are_rejected_before_recording(self) -> None:
        with self.assertRaisesRegex(SystemExit, "appears to contain a secret"):
            agent_friction.normalize_text("password=supersecret", "evidence")
        self.assertFalse(self.log.exists())

    def test_batch_becomes_ready_after_repeated_evidence(self) -> None:
        self.write_events(5)
        batch = agent_friction.pending_batch(5)
        self.assertTrue(batch["ready"])
        self.assertEqual(batch["reason"], "minimum-events")
        self.assertEqual(batch["pending_count"], 5)
        self.assertEqual(batch["through_id"], "event-5")

    def test_high_severity_event_is_ready_without_waiting_for_five(self) -> None:
        self.write_events(1, severity="high")
        batch = agent_friction.pending_batch(5)
        self.assertTrue(batch["ready"])
        self.assertEqual(batch["reason"], "urgent-event")

    def test_mark_reviewed_requires_real_report_and_advances_cursor(self) -> None:
        self.write_events(6)
        report = self.reports / "review.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Review\nRepeated pattern confirmed with evidence.\n", encoding="utf-8")
        state = agent_friction.mark_reviewed("event-5", str(report))
        self.assertEqual(state["reviewed_count"], 5)
        batch = agent_friction.pending_batch(5)
        self.assertEqual(batch["pending_count"], 1)
        self.assertFalse(batch["ready"])

    def test_review_cursor_never_moves_backwards(self) -> None:
        self.write_events(6)
        report = self.reports / "review.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Review\nEvidence reviewed.\n", encoding="utf-8")
        agent_friction.mark_reviewed("event-5", str(report))
        with self.assertRaisesRegex(SystemExit, "backwards"):
            agent_friction.mark_reviewed("event-3", str(report))

    def test_legacy_events_receive_safe_defaults(self) -> None:
        self.log.write_text(
            json.dumps(
                {
                    "id": "legacy-event",
                    "at": "2026-08-01T10:00:00+00:00",
                    "category": "old-category",
                    "observation": "old",
                    "evidence": "old",
                    "hypothesis": "old",
                    "scope": "project",
                    "proposal": "old",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        event = agent_friction.read_events(None)[0]
        self.assertEqual(event["severity"], "medium")
        self.assertEqual(event["triggers"], ["old-category"])


if __name__ == "__main__":
    unittest.main()
