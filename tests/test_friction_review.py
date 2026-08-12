from __future__ import annotations

import importlib.util
import json
import subprocess
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
        self.original_gh = agent_friction.gh
        self.original_which = agent_friction.shutil.which
        self.original_destination = agent_friction.destination_for
        self.original_branch = agent_friction.current_branch
        self.original_worktree_root = agent_friction.current_worktree_root
        self.original_current_head = agent_friction.current_head
        agent_friction.destination_for = lambda event: "example/project" if event["scope"] == "project" else "lehard/dev-platform"
        agent_friction.current_branch = lambda: "test-branch"
        agent_friction.current_worktree_root = lambda: self.root
        self.head = "a" * 40
        agent_friction.current_head = lambda root: self.head

    def tearDown(self) -> None:
        agent_friction.gh = self.original_gh
        agent_friction.shutil.which = self.original_which
        agent_friction.destination_for = self.original_destination
        agent_friction.current_branch = self.original_branch
        agent_friction.current_worktree_root = self.original_worktree_root
        agent_friction.current_head = self.original_current_head
        self.tmp.cleanup()

    def checkpoint_args(self, *, result: str | None = None, events: list[str] | None = None) -> object:
        return type("Args", (), {"result": result, "events": events or []})()

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

    def event(self, *, scope: str = "platform") -> dict:
        return {
            "id": "route-me", "at": "2026-08-11T10:00:00+00:00", "scope": scope,
            "category": "repeated-error", "severity": "high", "observation": "token=very-secret-value",
            "evidence": "api_key=local-only-secret", "hypothesis": "missing guard", "proposal": "add guard",
        }

    def test_route_creates_sanitized_fingerprinted_issue_without_evidence(self) -> None:
        calls: list[list[str]] = []
        agent_friction.shutil.which = lambda _: "/usr/bin/gh"

        def fake_gh(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[:2] == ["auth", "status"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["api", "repos/lehard/dev-platform/issues?state=open&per_page=100"]:
                return subprocess.CompletedProcess(command, 0, "[]", "")
            return subprocess.CompletedProcess(command, 0, json.dumps({"number": 17}), "")

        agent_friction.gh = fake_gh
        result = agent_friction.route_event(self.event())
        self.assertEqual(result["status"], "routed")
        self.assertEqual(result["issue_number"], 17)
        request = calls[-1]
        body = next(item for item in request if item.startswith("body="))
        self.assertIn("dev-platform-friction:", body)
        self.assertIn("[REDACTED]", body)
        self.assertNotIn("local-only-secret", body)
        self.assertNotIn("Evidence", body)

    def test_open_fingerprint_is_updated_instead_of_creating_duplicate(self) -> None:
        event = self.event(scope="project")
        marker = agent_friction.marker_for(agent_friction.fingerprint_for(event, "example/project"))
        calls: list[list[str]] = []
        agent_friction.shutil.which = lambda _: "/usr/bin/gh"

        def fake_gh(command: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[:2] == ["auth", "status"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["api", "repos/example/project/issues?state=open&per_page=100"]:
                return subprocess.CompletedProcess(command, 0, json.dumps([{"number": 31, "body": marker}]), "")
            return subprocess.CompletedProcess(command, 0, "{}", "")

        agent_friction.gh = fake_gh
        result = agent_friction.route_event(event)
        self.assertEqual(result["issue_number"], 31)
        self.assertIn("repos/example/project/issues/31/comments", calls[-1])
        self.assertFalse(any(command[:3] == ["api", "--method", "POST"] and command[3] == "repos/example/project/issues" for command in calls))

    def test_unavailable_routing_stays_pending_then_retries(self) -> None:
        event = self.event()
        self.log.write_text(json.dumps(event) + "\n", encoding="utf-8")
        agent_friction.shutil.which = lambda _: None
        self.assertEqual(agent_friction.route_event(event)["status"], "pending")
        self.assertEqual(agent_friction.read_state()["routes"]["route-me"]["status"], "pending")
        agent_friction.shutil.which = lambda _: "/usr/bin/gh"

        def fake_gh(command: list[str]) -> subprocess.CompletedProcess[str]:
            if command[:2] == ["auth", "status"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:2] == ["api", "repos/lehard/dev-platform/issues?state=open&per_page=100"]:
                return subprocess.CompletedProcess(command, 0, "[]", "")
            return subprocess.CompletedProcess(command, 0, json.dumps({"number": 44}), "")

        agent_friction.gh = fake_gh
        retry = agent_friction.route_pending()
        self.assertEqual(retry, {"pending": 1, "routed": 1, "failures": 0})
        self.assertEqual(agent_friction.read_state()["routes"]["route-me"]["status"], "routed")

    def test_checkpoint_none_is_explicit_and_creates_no_route(self) -> None:
        agent_friction.cmd_checkpoint(self.checkpoint_args(result="none"))
        agent_friction.require_checkpoint("test-branch")
        self.assertEqual(agent_friction.read_state()["checkpoints"]["test-branch"]["result"], "none")
        self.assertEqual(agent_friction.read_state()["checkpoints"]["test-branch"]["head"], self.head)
        self.assertEqual(agent_friction.read_state()["routes"], {})

    def test_missing_checkpoint_blocks_non_trivial_completion(self) -> None:
        with self.assertRaisesRegex(SystemExit, "retrospective is required"):
            agent_friction.require_checkpoint("test-branch")

    def test_checkpoint_supports_multiple_findings_in_one_retrospective(self) -> None:
        self.write_events(2)
        agent_friction.cmd_checkpoint(self.checkpoint_args(events=["event-1", "event-2"]))
        checkpoint = agent_friction.read_state()["checkpoints"]["test-branch"]
        self.assertEqual(checkpoint["result"], "events")
        self.assertEqual(checkpoint["event_ids"], ["event-1", "event-2"])
        agent_friction.require_checkpoint("test-branch")

    def test_checkpoint_rejects_unknown_finding_id(self) -> None:
        with self.assertRaisesRegex(SystemExit, "Friction event not found: does-not-exist"):
            agent_friction.cmd_checkpoint(self.checkpoint_args(events=["does-not-exist"]))

    def test_checkpoint_rejects_none_combined_with_findings(self) -> None:
        self.write_events(1)
        with self.assertRaisesRegex(SystemExit, "cannot be combined"):
            agent_friction.cmd_checkpoint(self.checkpoint_args(result="none", events=["event-1"]))

    def test_checkpoint_requires_result_or_event(self) -> None:
        with self.assertRaisesRegex(SystemExit, "requires --result none"):
            agent_friction.cmd_checkpoint(self.checkpoint_args())

    def test_stale_checkpoint_head_blocks_completion(self) -> None:
        agent_friction.cmd_checkpoint(self.checkpoint_args(result="none"))
        agent_friction.current_head = lambda root: "b" * 40
        with self.assertRaisesRegex(SystemExit, "retrospective is stale"):
            agent_friction.require_checkpoint("test-branch")

    def test_fresh_checkpoint_after_new_commit_satisfies_completion(self) -> None:
        agent_friction.cmd_checkpoint(self.checkpoint_args(result="none"))
        agent_friction.current_head = lambda root: "b" * 40
        with self.assertRaisesRegex(SystemExit, "retrospective is stale"):
            agent_friction.require_checkpoint("test-branch")
        agent_friction.cmd_checkpoint(self.checkpoint_args(result="none"))
        agent_friction.require_checkpoint("test-branch")
        self.assertEqual(agent_friction.read_state()["checkpoints"]["test-branch"]["head"], "b" * 40)

    def test_checkpoint_referencing_already_recorded_event_creates_no_duplicate(self) -> None:
        self.write_events(1)
        before = len(agent_friction.read_events(None))
        agent_friction.cmd_checkpoint(self.checkpoint_args(events=["event-1"]))
        agent_friction.require_checkpoint("test-branch")
        self.assertEqual(len(agent_friction.read_events(None)), before)

    def test_positive_findings_satisfy_completion_despite_pending_routing_failure(self) -> None:
        # A finding whose GitHub routing is still pending remains a valid local
        # retrospective reference; routing failure must not block completion.
        self.write_events(1)
        with self.friction_lock_state() as state:
            state["routes"]["event-1"] = {"status": "pending", "detail": "GitHub CLI is not authenticated"}
        agent_friction.cmd_checkpoint(self.checkpoint_args(events=["event-1"]))
        agent_friction.require_checkpoint("test-branch")

    def friction_lock_state(self):
        class _StateWriter:
            def __enter__(inner):
                inner.state = agent_friction.read_state()
                return inner.state

            def __exit__(inner, *exc):
                agent_friction.atomic_write_json(agent_friction.state_path(), inner.state)

        return _StateWriter()

    def test_checkpoint_needs_no_managed_task_provenance(self) -> None:
        # Quick tasks without Development Backlog provenance reuse the same
        # branch/head identity; no managed-task state is required.
        self.assertFalse((self.root / "openspec").exists())
        agent_friction.cmd_checkpoint(self.checkpoint_args(result="none"))
        agent_friction.require_checkpoint("test-branch")


if __name__ == "__main__":
    unittest.main()
