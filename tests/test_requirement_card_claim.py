"""A started Requirement must be claimed on its card before preparation continues."""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import requirement_board  # noqa: E402
import requirement_intake as ri  # noqa: E402

REQUIREMENT = "acme/backlog#7"


class FakeBoard:
    """Stateful stand-in for the Project card; records every write."""

    def __init__(self, status: str = "Ready") -> None:
        self.status = status
        self.writes: list[str] = []

    def observe(self, root, source_issue):
        return SimpleNamespace(current_status=self.status)

    def reconcile(self, root, desired, source_issue):
        changed = self.status != desired
        self.status = desired
        self.writes.append(desired)
        return SimpleNamespace(current_status=desired, changed=changed)

    def is_free_for_capture(self) -> bool:
        return self.status == "Ready"


def run_start(board: FakeBoard, *, prepare=None) -> tuple[int, str]:
    def start_pre_authoring(root, *, requirement, base_dir=None):
        if prepare:
            prepare()
        return {"requirement": requirement, "slug": "requirement-7", "state": {}}

    out = io.StringIO()
    with patch.object(sys, "argv", ["requirement_intake.py", "start", "--requirement", REQUIREMENT]), \
            patch.object(ri, "current_worktree_root", return_value=Path("/unused")), \
            patch.object(ri, "start_pre_authoring", side_effect=start_pre_authoring), \
            patch.object(ri, "aggregate", return_value={"requirement": REQUIREMENT, "progress": {"stage": "pre-authoring"}}), \
            patch.object(requirement_board.managed_project_status, "observe", side_effect=board.observe), \
            patch.object(requirement_board.managed_project_status, "reconcile", side_effect=board.reconcile), \
            redirect_stdout(out):
        code = ri.main()
    return code, out.getvalue()


class RequirementCardClaimTests(unittest.TestCase):
    def test_second_agent_does_not_see_started_requirement_as_free(self) -> None:
        board = FakeBoard("Ready")
        self.assertTrue(board.is_free_for_capture())
        code, _ = run_start(board)
        self.assertEqual(code, 0)
        # The first agent's slow preparation follows; a second agent polling now finds nothing free.
        self.assertEqual(board.status, "In progress")
        self.assertFalse(board.is_free_for_capture())

    def test_rerun_continues_without_parallel_ownership_or_ready_write(self) -> None:
        board = FakeBoard("Ready")
        run_start(board)
        code, _ = run_start(board)
        self.assertEqual(code, 0)
        self.assertEqual(board.writes, ["In progress"])
        self.assertNotIn("Ready", board.writes)

    def test_claim_failure_keeps_state_reports_rerun_and_never_writes_ready(self) -> None:
        board = FakeBoard("Ready")
        prepared: list[bool] = []
        with patch.object(requirement_board, "reconcile_nonterminal", side_effect=RuntimeError("github timeout")):
            code, output = run_start(board, prepare=lambda: prepared.append(True))
        self.assertEqual(code, 2)
        self.assertTrue(prepared)
        self.assertIn("pre-authoring state is kept", output)
        self.assertIn("rerun", output)
        self.assertNotIn("Ready", board.writes)

    def test_unreadable_card_after_start_is_blocked_not_free(self) -> None:
        board = FakeBoard("Blocked")
        code, _ = run_start(board)
        self.assertEqual(code, 0)
        self.assertFalse(board.is_free_for_capture())


if __name__ == "__main__":
    unittest.main()
