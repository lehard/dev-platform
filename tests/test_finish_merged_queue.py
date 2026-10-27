from __future__ import annotations

import contextlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from _platform_config import write_platform_config  # noqa: E402
SCRIPTS = ROOT / "template" / "scripts"


def setUpModule() -> None:
    sys.path.insert(0, str(SCRIPTS))


def tearDownModule() -> None:
    sys.path.remove(str(SCRIPTS))


class QueueMergedFinishTests(unittest.TestCase):
    """A queue-merged PR head includes the coordinator's merge of main, so its
    content no longer matches the pre-merge evidence; finish must reconcile it."""

    def run_finish(self, queued: dict, *, work: Path = Path("/nonexistent/work"), config: dict | None = None,
                   extra: list | None = None) -> tuple[int | None, mock.Mock, mock.Mock]:
        """Drive finish for a queue state; ``extra`` replaces the reconciliation mock with patches of its own."""
        import finish_task
        import pr_review_gate
        import publication_queue

        evidence = mock.Mock(side_effect=SystemExit("evidence identity mismatch"))
        reconcile = mock.Mock()
        patches = [
            mock.patch.object(sys, "argv", ["finish_task.py"]),
            mock.patch.object(finish_task, "current_worktree_root", return_value=work),
            mock.patch.object(finish_task, "main_root", return_value=work),
            mock.patch.object(finish_task, "read_platform_config", return_value=config or {"main_branch": "main"}),
            mock.patch.object(finish_task, "lifecycle_mode", return_value="coordinator"),
            mock.patch.object(finish_task, "scm_provider", return_value="github"),
            mock.patch.object(finish_task, "harness_mode", return_value="platform"),
            mock.patch.object(finish_task, "profile", return_value="multi-agent"),
            mock.patch.object(finish_task, "preflight"),
            mock.patch.object(finish_task, "publish_mode", return_value="pr"),
            mock.patch.object(finish_task, "current_branch", return_value="agent/task"),
            mock.patch.object(finish_task, "require_managed_checkout_identity"),
            mock.patch.object(finish_task, "validate_publication_config"),
            mock.patch.object(pr_review_gate, "managed_candidate", return_value=False),
            mock.patch.object(finish_task, "require_no_orphan_active_openspec"),
            mock.patch.object(finish_task, "require_delivery_provenance", return_value=types.SimpleNamespace(path=work / "archived")),
            mock.patch.object(publication_queue, "enabled", return_value=True),
            mock.patch.object(publication_queue, "local_status", return_value=queued),
            mock.patch.object(publication_queue, "sync_merged_task"),
            mock.patch.object(finish_task, "pr_merge_mode", return_value="queue"),
            mock.patch.object(finish_task, "require_automated_evidence", evidence),
            mock.patch.object(finish_task, "require_publication_review_evidence", evidence),
            mock.patch.object(finish_task, "require_independent_publication_exception", return_value=None),
            mock.patch.object(finish_task, "observe_source_issue_drift", return_value=None),
            mock.patch.object(finish_task, "fetch_main"),
            mock.patch.object(finish_task, "task_pr_is_already_merged", return_value=True),
            *(extra if extra is not None else [mock.patch.object(finish_task, "reconcile_confirmed_remote_pr_merge", reconcile)]),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        try:
            code = finish_task.main()
        except SystemExit as exc:
            if not str(exc.code).startswith("evidence"):
                raise
            code = None
        return code, evidence, reconcile

    def test_queue_merged_head_reconciles_without_regating_pre_merge_evidence(self) -> None:
        code, evidence, reconcile = self.run_finish({"state": "merged", "number": 7})
        self.assertEqual(code, 0)
        evidence.assert_not_called()
        reconcile.assert_called_once()

    def test_post_merge_finish_completes_without_a_board_claim(self) -> None:
        # Regression: the developer claim is released at handoff, so post-merge finish
        # must reconcile a queue-merged task without `agent_board start` or any claim.
        import agent_board
        import finish_task

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp).resolve()
            write_platform_config(work)
            board = work / ".claude" / "agents-board.json"
            board.parent.mkdir()
            other = {"id": "other", "worktree": str(work / "sibling"), "branch": "agent/sibling", "task": "Sibling"}
            board.write_text(json.dumps({"items": [other]}), encoding="utf-8")
            before = board.read_bytes()
            config = {"main_branch": "main", "capabilities": {"agent_board": True},
                      "paths": {"agent_board": ".claude/agents-board.json"}}
            with mock.patch.object(agent_board, "board_path", return_value=board):
                # The same board would stop the scope gate: there is no claim for this worktree.
                with self.assertRaisesRegex(SystemExit, "no claim for worktree"):
                    finish_task.enforce_scope_gate(work, work, "agent/task")
                identity = types.SimpleNamespace(source_issue="acme/backlog#8", process_evidence=())
                spawned = mock.Mock()
                parent = mock.Mock()
                extra = [
                    mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                    mock.patch.object(finish_task, "serialized_integration", side_effect=lambda *_a, **_k: contextlib.nullcontext()),
                    mock.patch.object(finish_task, "sync_after_remote_pr_merge"),
                    mock.patch.object(finish_task, "assert_integration_identity_cross_check"),
                    mock.patch.object(finish_task, "reconcile_managed_project", return_value=None),
                    mock.patch.object(finish_task, "reconcile_linked_parent", parent),
                    mock.patch.object(finish_task.subprocess, "run", spawned),
                ]
                code, evidence, _ = self.run_finish({"state": "merged", "number": 7}, work=work, config=config, extra=extra)
            self.assertEqual(code, 0)
            evidence.assert_not_called()
            parent.assert_called_once_with(work, identity)
            spawned.assert_not_called()  # no `agent_board.py finish` for a claim that does not exist
            self.assertEqual(board.read_bytes(), before)

    def test_unmerged_candidate_still_gates_on_evidence(self) -> None:
        code, evidence, reconcile = self.run_finish({"state": "absent", "number": 7})
        self.assertIsNone(code)
        evidence.assert_called_once()
        reconcile.assert_not_called()

    def test_reconcile_pushed_head_awaiting_readmission_proceeds_to_admission(self) -> None:
        # Regression: a waiting exit here left a reconcile-pushed descendant unadmittable.
        code, evidence, reconcile = self.run_finish({"state": "readmission", "number": 7, "owner": "developer re-admission"})
        self.assertIsNone(code)
        evidence.assert_called_once()
        reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
