from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import finish_task  # noqa: E402
import managed_project_status  # noqa: E402
import project_publish  # noqa: E402
import requirement_integration  # noqa: E402
import requirement_terminal  # noqa: E402


class ManagedStatusLifecycleTests(unittest.TestCase):
    def test_shared_manifest_is_exact_committed_candidate_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            slug = requirement_integration._candidate_slug("acme/backlog#7")
            path = Path("dev-platform/requirement-integrations") / (slug + ".json")
            (root / path).parent.mkdir(parents=True)
            payload = {"version": 1, "requirement": "acme/backlog#7", "base": "a" * 40,
                       "children": [{"source_issue": "acme/backlog#8"}, {"source_issue": "acme/backlog#9"}]}
            payload["digest"] = requirement_integration._digest(payload)
            (root / path).write_text(json.dumps(payload), encoding="utf-8")
            subprocess.run(["git", "add", path.as_posix()], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "candidate"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "switch", "-c", "agent/" + slug], cwd=root, check=True, capture_output=True)
            with mock.patch.object(project_publish, "main_root", return_value=root), \
                    mock.patch.object(requirement_integration, "_verify_parent_links") as links:
                self.assertEqual(project_publish.validate_shared_manifest(root, path), payload)
                links.assert_called_once()
                (root / path).write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(requirement_integration.RequirementIntegrationError, "differs"):
                    project_publish.validate_shared_manifest(root, path)

    def test_shared_pr_skips_only_single_child_project_reconciliation(self) -> None:
        root = Path("/tmp/shared-review")
        lookup = SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None, stale_open=None)
        manifest = Path("dev-platform/requirement-integrations/candidate.json")
        with (
            mock.patch.object(project_publish, "validate_shared_manifest", return_value={}) as validate,
            mock.patch.object(project_publish, "_validate_feature_branch", return_value="agent/shared"),
            mock.patch.object(project_publish, "require_gh_environment", return_value={}),
            mock.patch.object(project_publish, "run_git", return_value=SimpleNamespace(stdout="a" * 40)),
            mock.patch.object(project_publish, "find_exact_head_pr", return_value=lookup),
            mock.patch.object(project_publish, "push_feature_branch"),
            mock.patch.object(project_publish, "ensure_pr", return_value=project_publish.PrRef(12, "https://example/pr/12")),
            mock.patch.object(project_publish, "reconcile_managed_project") as reconcile,
        ):
            self.assertEqual(project_publish.publish_pr(root, "origin", "main", None, None, "manual", shared_manifest=manifest), 0)
        validate.assert_called_once_with(root, manifest)
        reconcile.assert_not_called()

    def shared_publish(self, *, complete: bool, lookup, ensure=None):
        root = Path("/tmp/shared-review")
        manifest = Path("dev-platform/requirement-integrations/candidate.json")
        payload = {"expected_changes": ["a", "b"], "children": [{"change": "a"}] + ([{"change": "b"}] if complete else [])}
        stack = ExitStack()
        mocks = {
            "push": stack.enter_context(mock.patch.object(project_publish, "push_feature_branch")),
            "ensure": stack.enter_context(mock.patch.object(project_publish, "ensure_pr", return_value=project_publish.PrRef(12, "https://example/pr/12"))),
            "ready": stack.enter_context(mock.patch.object(project_publish, "_set_pr_draft")),
            "merge": stack.enter_context(mock.patch.object(project_publish, "request_protected_merge", return_value="merged")),
        }
        stack.enter_context(mock.patch.object(project_publish, "validate_shared_manifest", return_value=payload))
        stack.enter_context(mock.patch.object(project_publish, "_validate_feature_branch", return_value="agent/shared"))
        stack.enter_context(mock.patch.object(project_publish, "require_gh_environment", return_value={}))
        stack.enter_context(mock.patch.object(project_publish, "run_git", return_value=SimpleNamespace(stdout="a" * 40)))
        stack.enter_context(mock.patch.object(project_publish, "find_exact_head_pr", return_value=lookup))
        stack.enter_context(mock.patch.object(project_publish, "main_root", return_value=root))
        with stack:
            result = project_publish.publish_pr(root, "origin", "main", None, None, "auto",
                                                config={"platform_version": "x"}, shared_manifest=manifest)
        return result, mocks

    def test_incomplete_shared_candidate_publishes_draft_without_ready_or_merge(self) -> None:
        lookup = SimpleNamespace(available=True, exact_open=None, exact_merged=None, stale_open=None)
        result, mocks = self.shared_publish(complete=False, lookup=lookup)
        self.assertEqual(result, 0)
        self.assertTrue(mocks["ensure"].call_args.kwargs["draft"])
        mocks["ready"].assert_not_called()
        mocks["merge"].assert_not_called()

    def test_incomplete_shared_candidate_puts_a_ready_pr_back_to_draft(self) -> None:
        lookup = SimpleNamespace(available=True, exact_open={"number": 12, "isDraft": False}, exact_merged=None, stale_open=None)
        _, mocks = self.shared_publish(complete=False, lookup=lookup)
        mocks["ready"].assert_called_once()
        self.assertTrue(mocks["ready"].call_args.kwargs["draft"])
        mocks["merge"].assert_not_called()

    def test_complete_shared_candidate_marks_the_same_draft_ready_before_merge(self) -> None:
        lookup = SimpleNamespace(available=True, exact_open={"number": 12, "isDraft": True}, exact_merged=None, stale_open=None)
        result, mocks = self.shared_publish(complete=True, lookup=lookup)
        self.assertEqual(result, 0)
        self.assertFalse(mocks["ensure"].call_args.kwargs["draft"])
        mocks["ready"].assert_called_once()
        self.assertFalse(mocks["ready"].call_args.kwargs["draft"])
        mocks["merge"].assert_called_once()

    def test_appended_head_reuses_the_existing_pr_without_fresh_base_or_duplicate(self) -> None:
        stale = SimpleNamespace(available=True, exact_open=None, exact_merged=None, stale_open={"number": 12})
        reobserved = SimpleNamespace(available=True, exact_open={"number": 12, "isDraft": True}, exact_merged=None, stale_open=None)
        result, mocks = self.shared_publish_with(stale, reobserved)
        self.assertEqual(result, 0)
        self.assertFalse(mocks["push"].call_args.kwargs["require_fresh_base"])

    def shared_publish_with(self, first, second):
        root = Path("/tmp/shared-review")
        manifest = Path("dev-platform/requirement-integrations/candidate.json")
        payload = {"expected_changes": ["a", "b"], "children": [{"change": "a"}]}
        with ExitStack() as stack:
            push = stack.enter_context(mock.patch.object(project_publish, "push_feature_branch"))
            stack.enter_context(mock.patch.object(project_publish, "ensure_pr", return_value=project_publish.PrRef(12, "https://example/pr/12")))
            stack.enter_context(mock.patch.object(project_publish, "validate_shared_manifest", return_value=payload))
            stack.enter_context(mock.patch.object(project_publish, "_validate_feature_branch", return_value="agent/shared"))
            stack.enter_context(mock.patch.object(project_publish, "require_gh_environment", return_value={}))
            stack.enter_context(mock.patch.object(project_publish, "run_git", return_value=SimpleNamespace(stdout="a" * 40)))
            stack.enter_context(mock.patch.object(project_publish, "find_exact_head_pr", side_effect=[first, second]))
            result = project_publish.publish_pr(root, "origin", "main", None, None, "auto", shared_manifest=manifest)
        return result, {"push": push}

    def test_invalid_shared_manifest_blocks_before_pr_mutation(self) -> None:
        root = Path("/tmp/shared-review")
        manifest = Path("dev-platform/requirement-integrations/candidate.json")
        with mock.patch.object(project_publish, "validate_shared_manifest",
                               side_effect=requirement_integration.RequirementIntegrationError("invalid")), \
                mock.patch.object(project_publish, "_validate_feature_branch") as feature, \
                mock.patch.object(project_publish, "push_feature_branch") as push:
            with self.assertRaisesRegex(SystemExit, "Shared Requirement publication blocked"):
                project_publish.publish_pr(root, "origin", "main", None, None, "manual", shared_manifest=manifest)
        feature.assert_not_called()
        push.assert_not_called()

    def test_validation_failure_evidence_uses_bounded_selector_descriptor(self) -> None:
        output = (
            'DEV_PLATFORM_CHECK_FAILURE: {"command":"python3 scripts/run_test_groups.py --all",'
            '"failure_class":"test-group-failure","failed_groups":["fast-b"]}\nraw test output'
        )
        evidence = json.loads(finish_task.validation_failure_evidence(output, 1))
        self.assertEqual(evidence["failure_class"], "test-group-failure")
        self.assertEqual(evidence["failed_groups"], ["fast-b"])
        self.assertNotIn("raw test output", json.dumps(evidence))

    def test_validation_failure_evidence_falls_back_without_selector_descriptor(self) -> None:
        self.assertEqual(
            json.loads(finish_task.validation_failure_evidence("unstructured failure", 7)),
            {"failure_class": "selector-exit", "exit_code": 7},
        )

    def test_reviewable_pr_reconciles_in_review_before_manual_stop(self) -> None:
        root = Path("/tmp/managed-review")
        lookup = SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None, stale_open=None)
        project = SimpleNamespace(changed=True, source_issue="example-org/development-backlog#8")
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
        lookup = SimpleNamespace(available=True, exact_open={"number": 12}, exact_merged=None, stale_open=None)
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
            project = SimpleNamespace(changed=False, source_issue="example-org/development-backlog#8")
            identity = SimpleNamespace(source_issue="example-org/development-backlog#8", change="managed")

            def record_done(*args, **kwargs):
                self.assertEqual(kwargs["source_issue"], identity.source_issue)
                events.append("done")
                return project

            with (
                mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge", side_effect=lambda *args: events.append("sync")),
                mock.patch.object(finish_task, "assert_integration_identity_cross_check"),
                mock.patch.object(requirement_terminal, "parent_for_child", return_value=None),
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
                    return_value=SimpleNamespace(source_issue="example-org/development-backlog#8", change="managed"),
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
                source_issue="example-org/development-backlog#8", change="managed", process_evidence=("lehard/dev-platform#17",)
            )
            with (
                mock.patch.object(finish_task, "delivery_identity", return_value=identity),
                mock.patch.object(finish_task, "sync_after_remote_pr_merge", side_effect=lambda *args: events.append("sync")),
                mock.patch.object(finish_task, "assert_integration_identity_cross_check"),
                mock.patch.object(requirement_terminal, "parent_for_child", return_value=None),
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
            identity = SimpleNamespace(source_issue="example-org/development-backlog#8", change="managed-a")
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

    def run_status(self, *, as_json: bool, drift, checkout_identity=None):
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
            mock.patch.object(finish_task, "require_managed_checkout_identity", return_value=checkout_identity),
            drift_patch,
            mock.patch("builtins.print") as printed,
        ):
            code = finish_task.run_status(root, root, config, as_json=as_json)
        self.assertEqual(code, 0)
        return [call.args[0] for call in printed.call_args_list]

    def test_status_json_includes_source_issue_drift_field(self) -> None:
        drift = {"source_issue": "example-org/development-backlog#8", "drifted": True, "recorded_body_sha256": "a" * 64, "current_body_sha256": "b" * 64}
        [output] = self.run_status(as_json=True, drift=drift)
        payload = json.loads(output)
        self.assertEqual(payload["source_issue_drift"], drift)

    def test_status_text_prints_drift_note_only_when_drifted(self) -> None:
        drifted = {"source_issue": "example-org/development-backlog#8", "drifted": True}
        outputs = self.run_status(as_json=False, drift=drifted)
        self.assertIn("status: in_review", outputs)
        self.assertTrue(any("source_issue_drift" in line and "example-org/development-backlog#8" in line for line in outputs))

        not_drifted = {"source_issue": "example-org/development-backlog#8", "drifted": False}
        outputs = self.run_status(as_json=False, drift=not_drifted)
        self.assertFalse(any("source_issue_drift" in line for line in outputs))

    def test_status_survives_github_unavailable_during_drift_check(self) -> None:
        outputs = self.run_status(as_json=True, drift=RuntimeError("gh unavailable"))
        [output] = outputs
        payload = json.loads(output)
        self.assertIsNone(payload["source_issue_drift"])

    def test_status_json_surfaces_exact_checkout_identity_without_mutation(self) -> None:
        identity = SimpleNamespace(evidence_payload=lambda: {"change": "managed", "branch": "agent/managed"})
        [output] = self.run_status(as_json=True, drift=None, checkout_identity=identity)
        payload = json.loads(output)
        self.assertEqual(payload["checkout_identity"], {"change": "managed", "branch": "agent/managed"})
        self.assertIsNone(payload["checkout_identity_error"])

    def test_status_json_surfaces_checkout_mismatch_without_blocking(self) -> None:
        root = Path("/tmp/managed-drift-status")
        config = {}
        with (
            mock.patch.object(finish_task, "current_branch", return_value="agent/managed"),
            mock.patch.object(finish_task, "require_managed_checkout_identity", side_effect=finish_task.ManagedTaskError("expected task checkout")),
            mock.patch.object(finish_task, "github_cli_env", return_value={}),
            mock.patch.object(finish_task.publication_state, "observe_publication", return_value=SimpleNamespace()),
            mock.patch.object(finish_task.publication_state, "merge_durability_capability", return_value="full"),
            mock.patch.object(finish_task.publication_state, "status_payload", return_value={"status": "in_review"}),
            mock.patch.object(finish_task, "observe_source_issue_drift", return_value=None),
            mock.patch("builtins.print") as printed,
        ):
            self.assertEqual(0, finish_task.run_status(root, root, config, as_json=True))
        payload = json.loads(printed.call_args.args[0])
        self.assertIsNone(payload["checkout_identity"])
        self.assertEqual(payload["checkout_identity_error"], "expected task checkout")

    def test_exact_merge_with_unresolved_evidence_is_terminal_pending(self) -> None:
        root = Path("/tmp/managed-status")
        identity = SimpleNamespace(source_issue="example-org/development-backlog#8", process_evidence=("lehard/dev-platform#17",))
        merged = SimpleNamespace(bucket="complete", remote_merged=True)
        with (
            mock.patch.object(finish_task, "current_branch", return_value="agent/managed"),
            mock.patch.object(finish_task, "github_cli_env", return_value={}),
            mock.patch.object(finish_task.publication_state, "observe_publication", return_value=merged),
            mock.patch.object(finish_task.publication_state, "merge_durability_capability", return_value="full"),
            mock.patch.object(finish_task.publication_state, "status_payload", return_value={"status": "complete", "remote_merged": True}),
            mock.patch.object(finish_task, "delivery_identity", return_value=identity),
            mock.patch.object(finish_task, "observe_managed_project", return_value=SimpleNamespace(current_status="Done")),
            mock.patch.object(finish_task, "observe_process_evidence_obligations", return_value=[{"reference": "lehard/dev-platform#17", "state": "unknown", "detail": "HTTP 404"}]),
            mock.patch.object(finish_task, "profile", return_value="standard"),
            mock.patch.object(finish_task, "require_managed_checkout_identity", return_value=None),
            mock.patch.object(finish_task, "observe_source_issue_drift", return_value=None),
            mock.patch("builtins.print") as printed,
        ):
            self.assertEqual(0, finish_task.run_status(root, root, {}, as_json=True))
        payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload["status"], "terminal_pending")
        self.assertTrue(payload["remote_merged"])
        self.assertEqual(payload["terminal_obligations"][0]["kind"], "process-evidence")

    def test_exact_merge_waits_for_cleanup_or_exact_deferred_record(self) -> None:
        root = Path("/tmp/managed-status")
        identity = SimpleNamespace(source_issue="example-org/development-backlog#8", process_evidence=())
        merged = SimpleNamespace(bucket="complete", remote_merged=True)
        common = (
            mock.patch.object(finish_task, "current_branch", return_value="agent/managed"),
            mock.patch.object(finish_task, "github_cli_env", return_value={}),
            mock.patch.object(finish_task.publication_state, "observe_publication", return_value=merged),
            mock.patch.object(finish_task.publication_state, "merge_durability_capability", return_value="full"),
            mock.patch.object(finish_task.publication_state, "status_payload", side_effect=lambda *_: {"status": "complete", "remote_merged": True, "local_head": "a" * 40}),
            mock.patch.object(finish_task, "delivery_identity", return_value=identity),
            mock.patch.object(finish_task, "observe_managed_project", return_value=SimpleNamespace(current_status="Done")),
            mock.patch.object(finish_task, "observe_process_evidence_obligations", return_value=[]),
            mock.patch.object(finish_task, "profile", return_value="multi-agent"),
            mock.patch.object(finish_task, "require_managed_checkout_identity", return_value=None),
            mock.patch.object(finish_task, "observe_source_issue_drift", return_value=None),
        )
        with ExitStack() as stack:
            for context in common:
                stack.enter_context(context)
            stack.enter_context(mock.patch.object(finish_task, "_read_deferred_cleanup", return_value=[]))
            printed = stack.enter_context(mock.patch("builtins.print"))
            finish_task.run_status(root, root, {}, as_json=True)
            self.assertEqual(json.loads(printed.call_args.args[0])["status"], "terminal_pending")
        record = {"path": str(root.resolve()), "branch": "agent/managed", "head": "a" * 40}
        with ExitStack() as stack:
            for context in common:
                stack.enter_context(context)
            stack.enter_context(mock.patch.object(finish_task, "_read_deferred_cleanup", return_value=[record]))
            printed = stack.enter_context(mock.patch("builtins.print"))
            finish_task.run_status(root, root, {}, as_json=True)
            payload = json.loads(printed.call_args.args[0])
        self.assertEqual(payload["status"], "complete")
        self.assertEqual(payload["terminal_obligations"][0]["state"], "warning")


class FinishTaskLegacyCleanupCompatibilityTests(unittest.TestCase):
    def test_legacy_worktree_cleanup_without_defer_helper_keeps_finish_importable(self) -> None:
        legacy_cleanup = types.ModuleType("worktree_cleanup")
        module_name = "finish_task_legacy_worktree_cleanup"
        spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / "finish_task.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"worktree_cleanup": legacy_cleanup, module_name: module}):
            spec.loader.exec_module(module)
        self.assertIsNone(module.defer_completed_task)


if __name__ == "__main__":
    unittest.main()
