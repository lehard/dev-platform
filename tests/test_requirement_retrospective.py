from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import requirement_retrospective as retrospective
import requirement_terminal

REQUIREMENT = "acme/backlog#7"


def parent(children: tuple[int, ...] = (8, 9), *, outcome: str = "Improve process") -> dict:
    lines = "\n".join(f"- [ ] acme/backlog#{number}" for number in children)
    return {"body": f"## Outcome\n\n{outcome}\n\n## Target repository\n\n`acme/project`\n\n<!-- requirement-children:start -->\n{lines}\n<!-- requirement-children:end -->"}


class RequirementRetrospectiveTests(unittest.TestCase):
    def test_early_and_cross_child_findings_survive_clean_child_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = [
                {"id": "early", "task": REQUIREMENT, "observation": "Repeated pre-authoring handoff"},
                {"id": "cross", "task": REQUIREMENT, "observation": "Duplicate work across children"},
            ]
            with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent()), mock.patch.object(
                retrospective.agent_friction, "read_events", return_value=events
            ):
                result = retrospective.checkpoint(root, requirement=REQUIREMENT, result="findings", event_ids=["early", "cross"], review_note="Reviewed intake, handoff, children and delivery.")
                receipt = retrospective.require_checkpoint(root, requirement=REQUIREMENT)
            self.assertEqual(result["status"], "recorded")
            self.assertEqual(receipt["event_ids"], ["early", "cross"])
            self.assertEqual(receipt["children"], ["acme/backlog#8", "acme/backlog#9"])

    def test_clean_result_is_short_and_stales_when_parent_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent()), mock.patch.object(
                retrospective.agent_friction, "read_events", return_value=[]
            ):
                retrospective.checkpoint(root, requirement=REQUIREMENT, result="none", event_ids=[], review_note="Reviewed intake, handoff, children and delivery.")
                self.assertEqual(retrospective.require_checkpoint(root, requirement=REQUIREMENT)["result"], "none")
            path = root / ".claude/requirement-retrospective/requirement-7.json"
            self.assertEqual(json.loads(path.read_text())["event_ids"], [])
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "stale"):
                retrospective.require_checkpoint(root, requirement=REQUIREMENT, parent=parent((8, 9, 10)))
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "stale"):
                retrospective.require_checkpoint(root, requirement=REQUIREMENT, parent=parent(outcome="Changed intent"))

    def test_parent_none_rejects_recorded_recurrence_even_when_child_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events = [{
                "id": "recurrence", "task": REQUIREMENT, "triggers": ["known-recurrence"],
                "category": "handoff-override", "observation": "Known workaround repeated",
            }]
            with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent()), mock.patch.object(
                retrospective.agent_friction, "read_events", return_value=events
            ):
                self.assertEqual(retrospective.agent_friction.current_retrospective_signals(REQUIREMENT)[0]["id"], "recurrence")
                with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "not linked"):
                    retrospective.checkpoint(root, requirement=REQUIREMENT, result="none", event_ids=[], review_note="Reviewed full path and the known override.")
                retrospective.checkpoint(root, requirement=REQUIREMENT, result="findings", event_ids=["recurrence"], review_note="Reviewed full path and the known override.")
                self.assertEqual(retrospective.require_checkpoint(root, requirement=REQUIREMENT)["event_ids"], ["recurrence"])

    def test_false_or_unrelated_event_cannot_complete_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "missing"):
                retrospective.require_checkpoint(root, requirement=REQUIREMENT, parent=parent())
            with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value=parent()), mock.patch.object(
                retrospective.agent_friction, "read_events", return_value=[{"id": "other", "task": "acme/backlog#99"}]
            ):
                with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "not attributed"):
                    retrospective.checkpoint(root, requirement=REQUIREMENT, result="findings", event_ids=["other"], review_note="Reviewed full Requirement path.")
                with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "requires no events"):
                    retrospective.checkpoint(root, requirement=REQUIREMENT, result="none", event_ids=["other"], review_note="Reviewed full Requirement path.")

    def test_terminal_reconciliation_checks_parent_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('platform_version = "1.0.0"\n', encoding="utf-8")
            with mock.patch.object(requirement_terminal.subprocess, "run", return_value=mock.Mock(stdout="main", returncode=0)), mock.patch.object(
                requirement_terminal.requirement_target_lifecycle, "require_local_target_support"
            ), mock.patch.object(
                requirement_terminal.requirement_intake, "fetch_issue", return_value={**parent(), "labels": [{"name": "type:requirement"}]}
            ), mock.patch.object(requirement_terminal.requirement_retrospective, "require_checkpoint", side_effect=retrospective.RequirementRetrospectiveError("missing")), mock.patch.object(
                requirement_terminal.managed_project_status, "reconcile"
            ) as project:
                with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "missing"):
                    requirement_terminal.reconcile_parent(root, requirement=REQUIREMENT)
                project.assert_not_called()

    def test_terminal_reconciliation_refuses_unsupported_target_before_parent_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('platform_version = "1.0.0"\n', encoding="utf-8")
            unsupported = requirement_terminal.requirement_target_lifecycle.RequirementTargetLifecycleError("missing terminal path")
            with mock.patch.object(requirement_terminal.subprocess, "run", return_value=mock.Mock(stdout="main", returncode=0)), mock.patch.object(
                requirement_terminal.requirement_intake, "fetch_issue", return_value={**parent(), "labels": [{"name": "type:requirement"}]}
            ), mock.patch.object(
                requirement_terminal.requirement_target_lifecycle, "require_local_target_support", side_effect=unsupported
            ), mock.patch.object(requirement_terminal.managed_project_status, "reconcile") as project:
                with self.assertRaisesRegex(requirement_terminal.RequirementTerminalError, "missing terminal path"):
                    requirement_terminal.reconcile_parent(root, requirement=REQUIREMENT)
                project.assert_not_called()


if __name__ == "__main__":
    unittest.main()
