from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from _platform_modules import load_platform_module

execution = load_platform_module("execute_requirement", ROOT / "template/scripts/execute_requirement.py")
retrospective = execution.requirement_retrospective

REQUIREMENT = "acme/backlog#7"
MAIN = "a" * 40


def _state(root: Path, source: str = "acme/backlog#8", change: str = "first-child") -> Path:
    path = root / ".managed-task-state.json"
    path.write_text(json.dumps({"source_issue": source, "change": change}), encoding="utf-8")
    return path


class DeliveredStateArchiveTests(unittest.TestCase):
    def _archive(self, root: Path, *, status: str = "Done", local: str = MAIN, remote: str = MAIN):
        with mock.patch.object(execution.managed_project_status, "observe",
                               return_value=SimpleNamespace(current_status=status)), \
             mock.patch.object(execution, "_done_child_is_delivered") as delivered, \
             mock.patch.object(execution, "_git", return_value=local), \
             mock.patch.object(execution.managed_task, "target_main", return_value=remote):
            return execution._archive_delivered_task_state(root, "acme/backlog#9"), delivered

    def test_done_child_state_is_archived_when_local_main_equals_origin_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = _state(root)
            archived, delivered = self._archive(root)
            self.assertFalse(state.exists())
            self.assertTrue(Path(archived).is_file())
            self.assertEqual(Path(archived).parent, root / ".claude" / "delivered-task-state")
            self.assertTrue(Path(archived).name.startswith("first-child-"))
            delivered.assert_called_once_with(root, "acme/backlog#8", "first-child")

    def test_state_of_a_child_that_is_not_done_is_left_for_the_import_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = _state(root)
            archived, delivered = self._archive(root, status="In review")
            self.assertIsNone(archived)
            self.assertTrue(state.exists())
            delivered.assert_not_called()

    def test_diverged_local_main_keeps_the_state_and_fails_naming_both_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = _state(root)
            with self.assertRaisesRegex(execution.RequirementExecutionError, f"{'b' * 40}.*{MAIN}"):
                self._archive(root, local="b" * 40)
            self.assertTrue(state.exists())

    def test_state_of_the_child_being_started_or_no_state_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(execution._archive_delivered_task_state(root, "acme/backlog#9"))
            state = _state(root, source="acme/backlog#9")
            self.assertIsNone(execution._archive_delivered_task_state(root, "acme/backlog#9"))
            self.assertTrue(state.exists())


class PendingRetrospectiveTests(unittest.TestCase):
    def _pending(self, root: Path, receipt: str | None = None, identity: dict | None = None):
        path = root / "retrospective.json"
        if receipt is not None:
            path.write_text(receipt, encoding="utf-8")
        identity = identity or {"requirement": REQUIREMENT, "number": 7}
        with mock.patch.object(retrospective.requirement_intake, "fetch_issue", return_value={}), \
             mock.patch.object(retrospective, "_identity", return_value=identity), \
             mock.patch.object(retrospective, "_receipt_path", return_value=path):
            return execution._retrospective_pending(root, REQUIREMENT, ["acme/backlog#8"])

    def test_missing_receipt_is_an_explicit_next_step_with_the_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._pending(Path(tmp))
        self.assertEqual(result["status"], "await-requirement-retrospective")
        self.assertIn(f"requirement_retrospective.py checkpoint --requirement {REQUIREMENT}", result["command"])
        self.assertEqual(result["children"], ["acme/backlog#8"])

    def test_stale_receipt_is_an_explicit_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stale = json.dumps({"version": 1, "requirement": REQUIREMENT, "number": 6})
            self.assertEqual(self._pending(Path(tmp), stale)["status"], "await-requirement-retrospective")

    def test_malformed_or_unsupported_receipt_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for receipt in ("{not json", json.dumps({"version": 2})):
                with self.subTest(receipt=receipt), self.assertRaises(retrospective.RequirementRetrospectiveError) as caught:
                    self._pending(root, receipt)
                self.assertNotIsInstance(caught.exception, retrospective.RetrospectivePending)
            malformed = json.dumps({"version": 1, "requirement": REQUIREMENT, "number": 7, "result": "maybe", "event_ids": []})
            with self.assertRaisesRegex(retrospective.RequirementRetrospectiveError, "malformed") as caught:
                self._pending(root, malformed)
            self.assertNotIsInstance(caught.exception, retrospective.RetrospectivePending)

    def test_advance_returns_the_pending_status_instead_of_reconciling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = {"body": "## Outcome\n\nShip it\n\n## Target repository\n\n`acme/project`\n",
                      "labels": [{"name": "type:requirement"}], "state": "OPEN"}
            pending = {"status": "await-requirement-retrospective", "command": "cmd"}
            import _platform_common
            with mock.patch.object(_platform_common, "read_platform_config", return_value={"platform_version": "1.0"}), \
                 mock.patch.object(execution, "current_worktree_root", return_value=root), \
                 mock.patch.object(execution, "_git", return_value="main"), \
                 mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), \
                 mock.patch.object(execution.requirement_intake, "fetch_issue", return_value=parent), \
                 mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}), \
                 mock.patch.object(execution.requirement_board, "claim_started"), \
                 mock.patch.object(execution, "_ordered_handoffs", return_value=[("first", root / "first.json")]), \
                 mock.patch.object(execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8"}), \
                 mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Done")), \
                 mock.patch.object(execution, "_done_child_is_delivered"), \
                 mock.patch.object(execution, "_retrospective_pending", return_value=pending), \
                 mock.patch("requirement_terminal.reconcile_parent") as reconcile:
                self.assertEqual(execution.advance(root, requirement=REQUIREMENT, base_dir=root), pending)
            reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
