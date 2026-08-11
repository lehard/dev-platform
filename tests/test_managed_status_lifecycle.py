from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import finish_task  # noqa: E402
import managed_project_status  # noqa: E402
import project_publish  # noqa: E402


class ManagedStatusLifecycleTests(unittest.TestCase):
    def test_reviewable_pr_reconciles_in_review_before_manual_stop(self) -> None:
        root = Path("/tmp/managed-review")
        lookup = SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None)
        project = SimpleNamespace(changed=True, source_issue="lehard/development-backlog#8")
        with (
            mock.patch.object(project_publish, "_validate_feature_branch", return_value="agent/managed"),
            mock.patch.object(project_publish, "require_gh_environment", return_value={}),
            mock.patch.object(project_publish, "run_git", return_value=SimpleNamespace(stdout="a" * 40)),
            mock.patch.object(project_publish, "find_exact_head_pr", return_value=lookup),
            mock.patch.object(project_publish, "push_feature_branch"),
            mock.patch.object(project_publish, "ensure_pr", return_value=project_publish.PrRef(12, "https://example/pr/12")),
            mock.patch.object(project_publish, "reconcile_managed_project", return_value=project) as reconcile,
        ):
            self.assertEqual(project_publish.publish_pr(root, "origin", "main", None, None, "manual"), 0)
        reconcile.assert_called_once_with(root, "In review")

    def test_project_failure_after_pr_creation_is_explicit_and_resumable(self) -> None:
        root = Path("/tmp/managed-review")
        lookup = SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None)
        with (
            mock.patch.object(project_publish, "_validate_feature_branch", return_value="agent/managed"),
            mock.patch.object(project_publish, "require_gh_environment", return_value={}),
            mock.patch.object(project_publish, "run_git", return_value=SimpleNamespace(stdout="a" * 40)),
            mock.patch.object(project_publish, "find_exact_head_pr", return_value=lookup),
            mock.patch.object(project_publish, "push_feature_branch"),
            mock.patch.object(project_publish, "ensure_pr", return_value=project_publish.PrRef(12, "https://example/pr/12")),
            mock.patch.object(
                project_publish,
                "reconcile_managed_project",
                side_effect=managed_project_status.ManagedProjectStatusError("missing project scope"),
            ),
        ):
            with self.assertRaisesRegex(SystemExit, "PR exists.*reconciliation is pending"):
                project_publish.publish_pr(root, "origin", "main", None, None, "manual")

    def test_done_follows_remote_merge_and_local_sync_before_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events: list[str] = []
            project = SimpleNamespace(changed=False, source_issue="lehard/development-backlog#8")
            source = SimpleNamespace(reference="lehard/development-backlog#8")

            def record_done(*args, **kwargs):
                self.assertEqual(kwargs["source_issue"], source.reference)
                events.append("done")
                return project

            with (
                mock.patch.object(finish_task, "discover_managed_source", return_value=source),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge", side_effect=lambda *args: events.append("sync")),
                mock.patch.object(
                    finish_task,
                    "reconcile_managed_project",
                    side_effect=record_done,
                ),
                mock.patch.object(finish_task, "finish_board", side_effect=lambda *args: events.append("board")),
                mock.patch.object(finish_task, "cleanup_completed_task", side_effect=lambda *args, **kwargs: events.append("cleanup")),
            ):
                finish_task.reconcile_confirmed_remote_pr_merge(
                    root,
                    root,
                    {"paths": {"main_merge_lock": ".lock"}},
                    "agent/managed",
                    "main",
                    "multi-agent",
                    cleanup=True,
                    timeout_seconds=1,
                )
            self.assertEqual(events, ["sync", "done", "board", "cleanup"])
            self.assertEqual(root.stat().st_gid, (root / ".lock").stat().st_gid)

    def test_done_failure_preserves_merged_truth_and_blocks_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                mock.patch.object(
                    finish_task,
                    "discover_managed_source",
                    return_value=SimpleNamespace(reference="lehard/development-backlog#8"),
                ),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge") as sync,
                mock.patch.object(
                    finish_task,
                    "reconcile_managed_project",
                    side_effect=managed_project_status.ManagedProjectStatusError("API unavailable"),
                ),
                mock.patch.object(finish_task, "cleanup_completed_task") as cleanup,
            ):
                with self.assertRaisesRegex(SystemExit, "local main is synchronized.*pending"):
                    finish_task.reconcile_confirmed_remote_pr_merge(
                        root,
                        root,
                        {"paths": {"main_merge_lock": ".lock"}},
                        "agent/managed",
                        "main",
                        "standard",
                        cleanup=True,
                        timeout_seconds=1,
                    )
            sync.assert_called_once()
            cleanup.assert_not_called()

    def test_resume_derives_active_state_but_never_infers_done(self) -> None:
        root = Path("/tmp/managed-resume")
        config = {"main_branch": "main"}
        results = [
            (SimpleNamespace(available=True, exact_open=None, exact_merged=None), "In progress"),
            (SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None), "In review"),
        ]
        for lookup, expected in results:
            with self.subTest(expected=expected):
                with (
                    mock.patch.object(managed_project_status, "read_platform_config", return_value=config),
                    mock.patch.object(
                        managed_project_status,
                        "run_git",
                        side_effect=[SimpleNamespace(stdout="agent/managed\n"), SimpleNamespace(stdout="a" * 40 + "\n")],
                    ),
                    mock.patch.object(managed_project_status, "github_cli_env", return_value={}),
                    mock.patch("publication_state.find_exact_head_pr", return_value=lookup),
                ):
                    self.assertEqual(managed_project_status.derive_resume_status(root), expected)
        merged = SimpleNamespace(available=True, exact_open=None, exact_merged={"number": 12})
        with (
            mock.patch.object(managed_project_status, "read_platform_config", return_value=config),
            mock.patch.object(
                managed_project_status,
                "run_git",
                side_effect=[SimpleNamespace(stdout="agent/managed\n"), SimpleNamespace(stdout="a" * 40 + "\n")],
            ),
            mock.patch.object(managed_project_status, "github_cli_env", return_value={}),
            mock.patch("publication_state.find_exact_head_pr", return_value=merged),
        ):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "rerun finish_task"):
                managed_project_status.derive_resume_status(root)


if __name__ == "__main__":
    unittest.main()
