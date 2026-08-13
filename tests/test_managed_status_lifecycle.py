from __future__ import annotations

import json
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
            identity = SimpleNamespace(source_issue="lehard/development-backlog#8", change="managed")

            def record_done(*args, **kwargs):
                self.assertEqual(kwargs["source_issue"], identity.source_issue)
                events.append("done")
                return project

            with (
                mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge", side_effect=lambda *args: events.append("sync")),
                mock.patch.object(finish_task, "assert_integration_identity_cross_check"),
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
                    "delivery_identity",
                    return_value=SimpleNamespace(source_issue="lehard/development-backlog#8", change="managed"),
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

    def test_linked_evidence_resolves_only_after_project_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events: list[str] = []
            identity = SimpleNamespace(
                source_issue="lehard/development-backlog#8", change="managed", process_evidence=("lehard/dev-platform#17",)
            )
            with (
                mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge", side_effect=lambda *args: events.append("sync")),
                mock.patch.object(finish_task, "assert_integration_identity_cross_check"),
                mock.patch.object(finish_task, "reconcile_managed_project", side_effect=lambda *args, **kwargs: events.append("done")),
                mock.patch.object(finish_task, "run_git", return_value=SimpleNamespace(stdout="a" * 40)),
                mock.patch.object(finish_task, "resolve_process_evidence_after_delivery", side_effect=lambda *args: events.append("resolve")),
            ):
                finish_task.reconcile_confirmed_remote_pr_merge(
                    root, root, {"paths": {"main_merge_lock": ".lock"}}, "agent/managed", "main", "standard", cleanup=False, timeout_seconds=1
                )
            self.assertEqual(events, ["sync", "done", "resolve"])

    def test_terminal_identity_mismatch_blocks_project_mutation_after_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = SimpleNamespace(source_issue="lehard/development-backlog#8", change="managed-a")
            with (
                mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge") as sync,
                mock.patch.object(
                    finish_task,
                    "assert_integration_identity_cross_check",
                    side_effect=finish_task.ManagedTaskError("exact task=#8; integration state=#9"),
                ),
                mock.patch.object(finish_task, "reconcile_managed_project") as reconcile,
                mock.patch.object(finish_task, "cleanup_completed_task") as cleanup,
            ):
                with self.assertRaisesRegex(SystemExit, "merged.*pending.*integration state=#9"):
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
            reconcile.assert_not_called()
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


class SourceIssueDriftStatusTests(unittest.TestCase):
    """--status surfaces bounded source-Issue drift evidence without ever blocking."""

    def run_status(self, *, as_json: bool, drift):
        root = Path("/tmp/managed-drift-status")
        config = {}
        drift_patch = (
            mock.patch.object(finish_task, "observe_source_issue_drift", side_effect=drift)
            if isinstance(drift, Exception)
            else mock.patch.object(finish_task, "observe_source_issue_drift", return_value=drift)
        )
        with (
            mock.patch.object(finish_task, "current_branch", return_value="agent/managed"),
            mock.patch.object(finish_task, "github_cli_env", return_value={}),
            mock.patch.object(finish_task.publication_state, "observe_publication", return_value=SimpleNamespace()),
            mock.patch.object(finish_task.publication_state, "merge_durability_capability", return_value="full"),
            mock.patch.object(finish_task.publication_state, "status_payload", return_value={"status": "in_review"}),
            mock.patch.object(finish_task.publication_state, "status_text", return_value="status: in_review"),
            drift_patch,
            mock.patch("builtins.print") as printed,
        ):
            code = finish_task.run_status(root, root, config, as_json=as_json)
        self.assertEqual(code, 0)
        return [call.args[0] for call in printed.call_args_list]

    def test_status_json_includes_source_issue_drift_field(self) -> None:
        drift = {"source_issue": "lehard/development-backlog#8", "drifted": True, "recorded_body_sha256": "a" * 64, "current_body_sha256": "b" * 64}
        [output] = self.run_status(as_json=True, drift=drift)
        payload = json.loads(output)
        self.assertEqual(payload["source_issue_drift"], drift)

    def test_status_text_prints_drift_note_only_when_drifted(self) -> None:
        drifted = {"source_issue": "lehard/development-backlog#8", "drifted": True}
        outputs = self.run_status(as_json=False, drift=drifted)
        self.assertIn("status: in_review", outputs)
        self.assertTrue(any("source_issue_drift" in line and "lehard/development-backlog#8" in line for line in outputs))

        not_drifted = {"source_issue": "lehard/development-backlog#8", "drifted": False}
        outputs = self.run_status(as_json=False, drift=not_drifted)
        self.assertFalse(any("source_issue_drift" in line for line in outputs))

    def test_status_survives_github_unavailable_during_drift_check(self) -> None:
        outputs = self.run_status(as_json=True, drift=RuntimeError("gh unavailable"))
        [output] = outputs
        payload = json.loads(output)
        self.assertIsNone(payload["source_issue_drift"])


if __name__ == "__main__":
    unittest.main()
