from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import requirement_board


class RequirementBoardTests(unittest.TestCase):
    def test_child_done_is_not_requirement_done(self) -> None:
        self.assertEqual(requirement_board.desired_nonterminal_status({"stage": "done"}), "In progress")

    def test_unknown_and_human_decision_fail_closed(self) -> None:
        for stage in ("unknown", "blocked", "human-decision"):
            self.assertEqual(requirement_board.desired_nonterminal_status({"stage": stage}), "Blocked")
        with self.assertRaises(requirement_board.RequirementBoardError):
            requirement_board.desired_nonterminal_status({"stage": "unrecognized"})

    def test_drift_repairs_only_parent_nonterminal_card(self) -> None:
        root = Path("/tmp/board-test")
        projection = {"requirement": "acme/backlog#7", "progress": {"stage": "implementation", "reason": "child active"}}
        with mock.patch.object(requirement_board.requirement_intake, "aggregate", return_value=projection), mock.patch.object(
            requirement_board.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Ready")
        ), mock.patch.object(requirement_board.managed_project_status, "reconcile", return_value=SimpleNamespace(current_status="In progress", changed=True)) as reconcile:
            result = requirement_board.reconcile_nonterminal(root, requirement="acme/backlog#7")
        self.assertTrue(result["changed"])
        reconcile.assert_called_once_with(root, "In progress", source_issue="acme/backlog#7")

    def test_matching_card_is_idempotent(self) -> None:
        root = Path("/tmp/board-test")
        projection = {"requirement": "acme/backlog#7", "progress": {"stage": "implementation", "reason": "child active"}}
        with mock.patch.object(requirement_board.requirement_intake, "aggregate", return_value=projection), mock.patch.object(
            requirement_board.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")
        ), mock.patch.object(requirement_board.managed_project_status, "reconcile") as reconcile:
            result = requirement_board.reconcile_nonterminal(root, requirement="acme/backlog#7")
        self.assertFalse(result["changed"])
        reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
