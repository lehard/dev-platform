from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"


def setUpModule() -> None:
    sys.path.insert(0, str(SCRIPTS))


def tearDownModule() -> None:
    sys.path.remove(str(SCRIPTS))


class QueueMergedFinishTests(unittest.TestCase):
    """A queue-merged PR head includes the coordinator's merge of main, so its
    content no longer matches the pre-merge evidence; finish must reconcile it."""

    def run_finish(self, queued: dict) -> tuple[int | None, mock.Mock, mock.Mock]:
        import finish_task
        import pr_review_gate
        import publication_queue

        work = Path("/nonexistent/work")
        evidence = mock.Mock(side_effect=SystemExit("evidence identity mismatch"))
        reconcile = mock.Mock()
        patches = [
            mock.patch.object(sys, "argv", ["finish_task.py"]),
            mock.patch.object(finish_task, "current_worktree_root", return_value=work),
            mock.patch.object(finish_task, "main_root", return_value=work),
            mock.patch.object(finish_task, "read_platform_config", return_value={"main_branch": "main"}),
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
            mock.patch.object(finish_task, "run_friction_route_pending_retry"),
            mock.patch.object(finish_task, "fetch_main"),
            mock.patch.object(finish_task, "task_pr_is_already_merged", return_value=True),
            mock.patch.object(finish_task, "reconcile_confirmed_remote_pr_merge", reconcile),
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

    def test_unmerged_candidate_still_gates_on_evidence(self) -> None:
        code, evidence, reconcile = self.run_finish({"state": "absent", "number": 7})
        self.assertIsNone(code)
        evidence.assert_called_once()
        reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
