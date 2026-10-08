"""Bounded #284-shaped examples for signal attribution, dispositions, gaps and the shared template."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import agent_friction as friction
import requirement_retrospective as retrospective

BRANCH = "task-branch"
REQUIREMENT = "acme/backlog#7"


def setUpModule() -> None:
    # Local-log scenarios: durable coordinator evidence (GitHub) is covered by the
    # coordinator-operations tests, so these scenarios never reach GitHub.
    for module in {friction}:
        patcher = mock.patch.object(module, "read_durable_events", return_value=[])
        patcher.start()
        unittest.addModuleCleanup(patcher.stop)


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = self.root / ".claude" / "agent-friction.jsonl"
        self.state = self.root / ".claude" / "agent-friction-state.json"
        self.log.parent.mkdir(parents=True)
        self.patches = [
            mock.patch.object(friction, "log_path", lambda: self.log),
            mock.patch.object(friction, "state_path", lambda: self.state),
            mock.patch.object(friction, "current_branch", lambda: BRANCH),
            mock.patch.object(friction, "current_worktree_root", lambda: self.root),
            mock.patch.object(friction, "current_head", lambda root: "a" * 40),
            mock.patch.object(friction, "current_task_content", lambda root: None),
            mock.patch.object(friction, "changed_paths", lambda root: ["src/browser/runner.py"]),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self) -> None:
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def write(self, *events: dict) -> None:
        self.log.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

    def args(self, **kw):
        base = {"result": None, "events": [], "lifecycle_dispositions": [], "accept_gaps": [], "review_note": "Reviewed actual path."}
        return type("Args", (), {**base, **kw})()

    def signal(self, event_id: str, **kw) -> dict:
        return {"id": event_id, "task": BRANCH, "category": "manual-archive-repair", "severity": "medium",
                "triggers": ["manual-workaround"], "at": "2026-10-01T00:00:00+00:00", **kw}


class AttributionTests(Fixture):
    # attribution
    def test_record_defaults_task_to_current_branch_and_marks_attribution(self) -> None:
        self.assertEqual(friction.default_attribution(None), (BRANCH, "branch"))
        self.assertEqual(friction.default_attribution("acme/backlog#7"), ("acme/backlog#7", "explicit"))
        with mock.patch.object(friction, "current_branch", lambda: "main"):
            self.assertEqual(friction.default_attribution(None), (None, "unattributed"))

    def test_lost_task_attribution_is_recovered_from_branch_and_source_issue(self) -> None:
        self.write(
            self.signal("by-branch", task=None, branch=BRANCH),
            self.signal("by-issue", task=None, branch="main", run={"source_issue": BRANCH}),
        )
        self.assertEqual({e["id"] for e in friction.current_retrospective_signals(BRANCH)}, {"by-branch", "by-issue"})
        with self.assertRaisesRegex(SystemExit, "not linked"):
            friction.cmd_checkpoint(self.args(result="none"))
        self.assertIn("task", json.loads(self.log.read_text().splitlines()[0]))  # history is not rewritten
        self.assertIsNone(json.loads(self.log.read_text().splitlines()[0])["task"])

    def test_source_issue_alias_of_the_managed_task_recovers_attribution(self) -> None:
        self.write(self.signal("by-alias", task=None, branch="main", run={"source_issue": "acme/project#9"}))
        self.assertEqual(friction.current_retrospective_signals(BRANCH), [])
        state = mock.Mock(return_value={"source_issue": "acme/project#9", "change": "x"})
        with mock.patch("managed_task.read_task_state", state):
            self.assertEqual([e["id"] for e in friction.current_retrospective_signals(BRANCH)], ["by-alias"])

    def test_old_malformed_line_outside_recent_window_is_not_a_gap(self) -> None:
        good = json.dumps(self.signal("ok")) + "\n"
        self.log.write_text("{bad\n" + good * friction.MAX_STATUS_LINES, encoding="utf-8")
        self.assertEqual(friction.evidence_source_status(), {"friction-log": "available"})

    def test_unattributable_event_is_reported_not_assigned_or_hidden(self) -> None:
        self.write(self.signal("orphan", task=None, branch="main", at=friction.utc_now()))
        self.assertEqual(friction.current_retrospective_signals(BRANCH), [])
        with redirect_stdout(StringIO()) as out:
            friction.cmd_review_path(type("A", (), {"task": BRANCH})())
        self.assertEqual(json.loads(out.getvalue())["ambiguous_attribution"], ["orphan"])
        with redirect_stdout(StringIO()) as out:
            friction.cmd_checkpoint(self.args(result="none"))
        self.assertEqual(json.loads(out.getvalue())["ambiguous_attribution_not_attributed"], ["orphan"])

    def test_other_tasks_events_are_not_attributed(self) -> None:
        self.write(self.signal("other", task="another-branch"), self.signal("other-legacy", task=None, branch="another-branch"))
        self.assertEqual(friction.current_retrospective_signals(BRANCH), [])
        friction.cmd_checkpoint(self.args(result="none"))

    # dispositions
    def test_omitted_mandatory_signal_blocks_and_each_disposition_explains_it(self) -> None:
        self.write(self.signal("wk"))
        with self.assertRaisesRegex(SystemExit, "wk"):
            friction.cmd_checkpoint(self.args(result="none"))
        for disposition in ("resolved-in-task", "already-recorded", "expected-behavior"):
            friction.cmd_checkpoint(self.args(result="none", lifecycle_dispositions=[f"wk={disposition}"]))
            friction.require_checkpoint(BRANCH)

    def test_expected_failure_signal_is_explained_without_new_finding(self) -> None:
        self.write(self.signal("red", category="lifecycle-verification", severity="high", triggers=["repeated-error"]))
        friction.cmd_checkpoint(self.args(result="none", lifecycle_dispositions=["red=expected-behavior"]))
        self.assertEqual(friction.read_state()["checkpoints"][BRANCH]["result"], "none")

    def test_known_recurrence_cannot_be_dismissed_only_linked(self) -> None:
        self.write(self.signal("rec", triggers=["known-recurrence"]))
        for disposition in ("already-recorded", "expected-behavior", "resolved-in-task"):
            with self.assertRaisesRegex(SystemExit, "cannot be dismissed"):
                friction.cmd_checkpoint(self.args(result="none", lifecycle_dispositions=[f"rec={disposition}"]))
        friction.cmd_checkpoint(self.args(events=["rec"]))

    def test_disposition_for_unrelated_event_is_rejected(self) -> None:
        self.write(self.signal("mine"), self.signal("theirs", task="another-branch"))
        with self.assertRaisesRegex(SystemExit, "not a current-task mandatory signal"):
            friction.cmd_checkpoint(self.args(result="none", lifecycle_dispositions=["theirs=expected-behavior", "mine=expected-behavior"]))

    def test_clean_path_is_short(self) -> None:
        friction.cmd_checkpoint(self.args(result="none"))
        friction.require_checkpoint(BRANCH)
        self.assertEqual(friction.read_state()["routes"], {})

    # evidence sources
    def test_partial_log_needs_explicit_gap_acceptance(self) -> None:
        self.log.write_text("{not json\n", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "friction-log \\(partial\\)"):
            friction.cmd_checkpoint(self.args(result="none"))
        friction.cmd_checkpoint(self.args(result="none", accept_gaps=["friction-log"]))
        self.assertEqual(friction.read_state()["checkpoints"][BRANCH]["accepted_gaps"], ["friction-log"])
        friction.require_checkpoint(BRANCH)

    def test_unreadable_log_is_not_clean(self) -> None:
        self.log.write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(friction.evidence_source_status(), {"friction-log": "unreadable"})
        with self.assertRaisesRegex(SystemExit, "not the absence of problems"):
            friction.cmd_checkpoint(self.args(result="none"))

    def test_missing_log_is_a_normal_clean_state(self) -> None:
        self.assertEqual(friction.evidence_source_status(), {"friction-log": "available"})

    # template and project questions
    def test_review_path_has_shared_template_and_no_project_section_by_default(self) -> None:
        with redirect_stdout(StringIO()) as out:
            friction.cmd_review_path(type("A", (), {"task": BRANCH})())
        result = json.loads(out.getvalue())
        self.assertEqual(len(result["template"]), 5)
        self.assertEqual(result["project_questions"], [])

    def test_project_questions_are_capped_and_path_scoped(self) -> None:
        (self.root / "dev-platform").mkdir()
        body = '[[question]]\ntext = "Did the browser runner attribute its events?"\npaths = ["src/browser/*"]\n'
        body += '[[question]]\ntext = "Unrelated area"\npaths = ["docs/*"]\n'
        body += '[[question]]\ntext = "Always ask"\n'
        body += "".join(f'[[question]]\ntext = "extra {i}"\n' for i in range(4))
        (self.root / friction.PROJECT_QUESTIONS_FILE).write_text(body, encoding="utf-8")
        result = friction.project_questions(self.root, ["src/browser/runner.py"])
        self.assertEqual(result["questions"], ["Did the browser runner attribute its events?", "Always ask", "extra 0", "extra 1"][:4])
        self.assertEqual(result["ignored"], 2)
        self.assertNotIn("Unrelated area", result["questions"])
        self.assertEqual(friction.project_questions(self.root, None)["questions"][0], "Always ask")

    def test_invalid_project_file_leaves_shared_path_working(self) -> None:
        (self.root / "dev-platform").mkdir()
        (self.root / friction.PROJECT_QUESTIONS_FILE).write_text("[[question", encoding="utf-8")
        result = friction.project_questions(self.root, [])
        self.assertEqual(result["questions"], [])
        self.assertIn("shared template only", result["problem"])


class RequirementAttributionTests(Fixture):
    """The Requirement review uses the same signal set, dispositions and gaps."""

    def parent(self) -> dict:
        return {"body": "## Outcome\n\nx\n\n## Target repository\n\n`acme/project`\n\n<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n<!-- requirement-children:end -->"}

    def run_checkpoint(self, **kw):
        with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=self.parent()):
            return retrospective.checkpoint(self.root, requirement=REQUIREMENT, review_note="Reviewed.", result=kw.pop("result", "none"),
                                            event_ids=kw.pop("event_ids", []), **kw)

    def test_requirement_signal_unexplained_then_explained(self) -> None:
        self.write(self.signal("pre", task=REQUIREMENT))
        with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "pre"):
            self.run_checkpoint()
        self.assertEqual(self.run_checkpoint(dispositions=["pre=expected-behavior"])["status"], "recorded")
        with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=self.parent()):
            receipt = retrospective.require_checkpoint(self.root, requirement=REQUIREMENT)
        self.assertEqual(receipt["dispositions"], [{"event_id": "pre", "disposition": "expected-behavior"}])

    def test_requirement_recovers_legacy_event_and_blocks_recurrence_dismissal(self) -> None:
        self.write(self.signal("lost", task=None, branch=REQUIREMENT, triggers=["known-recurrence"]))
        with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "cannot be dismissed"):
            self.run_checkpoint(dispositions=["lost=already-recorded"])
        self.assertEqual(self.run_checkpoint(result="findings", event_ids=["lost"])["event_ids"], ["lost"])

    def test_requirement_degraded_source_and_clean_path(self) -> None:
        self.assertEqual(self.run_checkpoint()["result"], "none")
        self.log.write_text("{bad\n", encoding="utf-8")
        with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "friction-log"):
            self.run_checkpoint()
        self.assertEqual(self.run_checkpoint(accepted_gaps=["friction-log"])["status"], "recorded")


if __name__ == "__main__":
    unittest.main()
