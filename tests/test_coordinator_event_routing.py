"""Routed coordinator events name their reason and candidate; faceless ones are withheld."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))
agent_friction = load_platform_module("agent_friction_coordinator_routing", SCRIPT_ROOT / "agent_friction.py")
finish_task = load_platform_module("finish_task_coordinator_routing", SCRIPT_ROOT / "finish_task.py")

HEAD = "b" * 40


class CoordinatorEventRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.log = root / ".claude" / "agent-friction.jsonl"
        self.state = root / ".claude" / "agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        self.calls: list[list[str]] = []
        for name, value in (
            ("log_path", lambda: self.log), ("state_path", lambda: self.state),
            ("destination_for", lambda event: "lehard/dev-platform"), ("current_branch", lambda: "agent/task"),
            ("gh", self.fake_gh),
        ):
            patcher = mock.patch.object(agent_friction, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch.object(agent_friction.shutil, "which", lambda _: "/usr/bin/gh")
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_gh(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        if command[:2] == ["auth", "status"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["api", "repos/lehard/dev-platform/issues?state=open&per_page=100"]:
            return subprocess.CompletedProcess(command, 0, "[]", "")
        if command[:2] == ["api", "repos/lehard/dev-platform/issues/44"]:
            return subprocess.CompletedProcess(command, 0, json.dumps({"number": 44, "labels": [{"name": "process"}]}), "")
        return subprocess.CompletedProcess(command, 0, json.dumps({"number": 44}), "")

    def event(self, event_id: str, **overrides) -> dict:
        event = {"id": event_id, "at": agent_friction.utc_now(), "branch": "agent/task", "task": "agent/task",
                 "attribution": "coordinator", "category": "coordinator-retry", "triggers": ["excessive-retry"],
                 "severity": "medium", "observation": "A lifecycle gate was unavailable", "evidence": "local only",
                 "hypothesis": "h", "proposal": "p", "scope": "platform", "classification": "process-friction",
                 "context": None, "reason": "review: provider-unavailable; quota exhausted",
                 "candidate": {"task": "agent/task", "number": 42, "head": HEAD}}
        event.update(overrides)
        return {key: value for key, value in event.items() if value is not None}

    def write(self, *events: dict) -> None:
        self.log.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

    def posted_bodies(self) -> list[str]:
        return [part[len("body="):] for command in self.calls for part in command if part.startswith("body=")]

    def test_routed_body_names_reason_and_candidate(self) -> None:
        event = self.event("named")
        self.write(event)
        self.assertEqual(agent_friction.route_event(event)["status"], "routed")
        [body] = self.posted_bodies()
        self.assertIn("- Candidate: `agent/task` / PR #42 / head `bbbbbbbbbbbb`", body)
        self.assertIn("### Reason\nreview: provider-unavailable; quota exhausted", body)
        self.assertNotIn("local only", body)

    def test_faceless_coordinator_events_are_withheld_and_not_retried(self) -> None:
        no_reason = self.event("no-reason", reason=None)
        no_candidate = self.event("no-candidate", candidate=None)
        validation = self.event("legacy-validation", attribution=None, category="lifecycle-validation-failure",
                                reason=None, candidate=None)
        ordinary = self.event("ordinary", attribution=None, category="manual-workaround", reason=None, candidate=None)
        self.write(no_reason, no_candidate, validation, ordinary)
        result = agent_friction.route_pending()
        self.assertEqual(result, {"pending": 4, "routed": 1, "failures": 0, "withheld": 3})
        routes = agent_friction.read_state()["routes"]
        self.assertEqual(routes["no-reason"], {**routes["no-reason"], "status": "withheld",
                                               "detail": "coordinator event lacks reason"})
        self.assertEqual(routes["no-candidate"]["detail"], "coordinator event lacks candidate")
        self.assertEqual(routes["legacy-validation"]["detail"], "coordinator event lacks reason and candidate")
        self.assertEqual(routes["ordinary"]["status"], "routed")
        self.assertEqual(len(self.posted_bodies()), 1)
        self.calls.clear()
        self.assertEqual(agent_friction.route_pending(), {"pending": 0, "routed": 0, "failures": 0, "withheld": 0})
        self.assertEqual(self.calls, [])

    def test_record_requires_reason_and_candidate_for_coordinator_categories(self) -> None:
        def run(argv: list[str]) -> int:
            with mock.patch.object(sys, "argv", ["agent_friction.py", *argv]):
                return agent_friction.main()

        base = ["record", "--category", "lifecycle-validation-failure", "--trigger", "repeated-error",
                "--severity", "high", "--observation", "o", "--evidence", "e", "--hypothesis", "h",
                "--scope", "platform", "--proposal", "p", "--task", "agent/task", "--no-route"]
        with self.assertRaisesRegex(SystemExit, "requires --reason and --candidate-task/--candidate-head"):
            run(base)
        with self.assertRaisesRegex(SystemExit, "candidate head must be a hexadecimal commit SHA"):
            run(base + ["--reason", "r", "--candidate-task", "agent/task", "--candidate-head", "HEAD"])
        self.assertFalse(self.log.exists() and self.log.read_text().strip())
        with redirect_stdout(StringIO()):
            run(base + ["--reason", "test-group-failure; exit 1", "--candidate-task", "agent/task", "--candidate-head", HEAD])
        [recorded] = agent_friction.read_events(None)
        self.assertEqual(recorded["reason"], "test-group-failure; exit 1")
        self.assertEqual(recorded["candidate"], {"task": "agent/task", "number": None, "head": HEAD})

    def test_validation_failure_reason_names_failure_class_and_checks(self) -> None:
        evidence = json.dumps({"failure_class": "test-group-failure", "failed_groups": ["friction", "queue"],
                               "selected_checks": ["platform-tests"], "command": "python3 x", "exit_code": 1})
        self.assertEqual(finish_task.validation_failure_reason(evidence),
                         "test-group-failure; failed groups friction, queue; checks platform-tests; exit 1")
        self.assertEqual(finish_task.validation_failure_reason(json.dumps({"failure_class": "selector-exit", "exit_code": 2})),
                         "selector-exit; exit 2")

    def test_finish_records_validation_failure_with_reason_and_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "agent_friction.py").write_text("", encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(finish_task, "current_branch", return_value="agent/task"), \
                    mock.patch.object(finish_task, "run_git", return_value=subprocess.CompletedProcess([], 0, HEAD + "\n", "")), \
                    mock.patch.object(finish_task.subprocess, "run", return_value=completed) as run:
                finish_task.record_lifecycle_friction(root, "lifecycle-validation-failure", "required platform validation failed",
                                                      "{}", reason="selector-exit; exit 2")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--reason") + 1], "selector-exit; exit 2")
        self.assertEqual(command[command.index("--candidate-task") + 1], "agent/task")
        self.assertEqual(command[command.index("--candidate-head") + 1], HEAD)


if __name__ == "__main__":
    unittest.main()
