from __future__ import annotations

import builtins
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
assert spec and spec.loader
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class OpenSpecLifecycleTests(unittest.TestCase):
    def make_change(self, root: Path, name: str, tasks: str, verification: str | None = None) -> Path:
        change = root / "openspec" / "changes" / name
        change.mkdir(parents=True)
        (change / "tasks.md").write_text(tasks, encoding="utf-8")
        if verification is not None:
            (change / "verification.md").write_text(verification, encoding="utf-8")
        return change

    def test_incomplete_change_is_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "work", "- [x] done\n- [ ] pending\n")
            self.assertEqual([], lifecycle.completed_active_changes(root))
            self.assertEqual(0, lifecycle.check_hygiene(root))

    def test_completed_active_change_blocks_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] one\n- [x] two\n")
            self.assertEqual(["done"], lifecycle.completed_active_changes(root))
            self.assertEqual(1, lifecycle.check_hygiene(root))

    def test_archive_readiness_requires_verify_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(Path(tmp), "done", "- [x] one\n")
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_pass_without_method_is_not_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(Path(tmp), "done", "- [x] one\n", "OpenSpec-Verify: PASS\n")
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_embedded_pass_text_is_not_a_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "Do not write OpenSpec-Verify: PASS unless verification succeeds.\nVerification-Method: equivalent-review\n",
            )
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change)

    def test_archive_readiness_accepts_pass_and_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n- [x] two\n",
                "# Verification\n\nOpenSpec-Verify: PASS\nVerification-Method: opsx-verify\n",
            )
            lifecycle.require_ready(change)

    def test_archive_readiness_checks_enabled_independent_review_before_accepting_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n",
            )
            with mock.patch.object(lifecycle, "require_review_evidence") as require_review:
                lifecycle.require_ready(change)
            require_review.assert_called_once_with(Path(tmp), change)

    def test_enabled_independent_review_requires_a_receipt_evidence_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n",
            )
            with (
                mock.patch.object(lifecycle, "require_review_evidence"),
                mock.patch.object(lifecycle, "review_is_required", return_value=True),
            ):
                with self.assertRaisesRegex(SystemExit, "Independent-Review-Evidence: independent-review-request.json"):
                    lifecycle.require_ready(change)

    def test_missing_independent_review_helper_is_legacy_compatible_but_enabled_mode_fails_closed(self) -> None:
        original_import = builtins.__import__

        def import_without_helper(name, *args, **kwargs):
            if name == "independent_review":
                raise ModuleNotFoundError("No module named 'independent_review'", name="independent_review")
            return original_import(name, *args, **kwargs)

        spec = importlib.util.spec_from_file_location("openspec_lifecycle_without_review_helper", SCRIPTS / "openspec_lifecycle.py")
        assert spec and spec.loader
        compat = importlib.util.module_from_spec(spec)
        with mock.patch("builtins.__import__", side_effect=import_without_helper):
            spec.loader.exec_module(compat)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(root, "managed", "- [x] one\n", "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n")
            (change / ".managed-task.json").write_text(
                '{"source_issue":"example-org/development-backlog#7","change":"managed"}\n', encoding="utf-8"
            )
            (root / ".dev-platform.toml").write_text("[independent_review]\nenabled = false\n", encoding="utf-8")
            compat.require_review_evidence(root, change)
            (root / ".dev-platform.toml").write_text("[independent_review]\nenabled = true\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "scripts/independent_review.py is missing"):
                compat.require_review_evidence(root, change)

    def test_platform_archive_readiness_requires_generated_automated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n",
            )
            with self.assertRaises(SystemExit):
                lifecycle.require_ready(change, platform_owned=True)

    def test_platform_archive_readiness_accepts_executed_automated_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp),
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            (change / "automated-checks.json").write_text(
                '{"selection":{"state":"ready","command_count":1},"outcome":"success","executed_commands":[{"command":"pytest","outcome":"success"}]}\n',
                encoding="utf-8",
            )
            lifecycle.require_ready(change, platform_owned=True)

    def test_managed_automated_evidence_must_match_exact_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(
                root,
                "managed",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            (change / ".managed-task.json").write_text(
                '{"source_issue":"example-org/development-backlog#7","change":"managed"}\n', encoding="utf-8"
            )
            (change / "automated-checks.json").write_text(
                '{"selection":{"state":"ready","command_count":1},"outcome":"success","executed_commands":[{"command":"pytest","outcome":"success"}],"managed_checkout":{"change":"wrong"}}\n',
                encoding="utf-8",
            )
            identity = mock.Mock()
            identity.evidence_payload.return_value = {"change": "managed"}
            with mock.patch.object(lifecycle, "require_managed_checkout_identity", return_value=identity):
                with self.assertRaisesRegex(SystemExit, "checkout identity does not match"):
                    lifecycle.require_ready(change, platform_owned=True)

    def test_archived_managed_evidence_uses_provenance_change_not_dated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(
                root,
                "2026-09-20-managed",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            (change / ".managed-task.json").write_text(
                '{"source_issue":"example-org/development-backlog#7","change":"managed"}\n', encoding="utf-8"
            )
            (change / "automated-checks.json").write_text(
                '{"selection":{"state":"ready","command_count":1},"outcome":"success","executed_commands":[{"command":"pytest","outcome":"success"}],"managed_checkout":{"change":"managed"}}\n',
                encoding="utf-8",
            )
            identity = mock.Mock()
            identity.evidence_payload.return_value = {"change": "managed"}
            with mock.patch.object(lifecycle, "require_managed_checkout_identity", return_value=identity) as require_identity:
                lifecycle.require_ready(change, platform_owned=True)
            self.assertEqual(require_identity.call_args.kwargs["expected_change"], "managed")

    def test_evidence_allows_only_its_own_committed_archive_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(root, "archive/2026-09-20-managed", "- [x] one\n")
            (change / ".managed-task.json").write_text('{"change":"managed"}\n', encoding="utf-8")
            (change / "specs" / "worktree-coordination").mkdir(parents=True)
            (change / "specs" / "worktree-coordination" / "spec.md").write_text("delta\n", encoding="utf-8")
            identity = mock.Mock()
            identity.evidence_payload.return_value = {
                "source_issue": "owner/backlog#1", "change": "managed", "worktree": "/task", "branch": "agent/task", "head": "b" * 40
            }
            actual = {**identity.evidence_payload(), "head": "a" * 40}
            archive_path = "openspec/changes/archive/2026-09-20-managed/automated-checks.json\nopenspec/specs/worktree-coordination/spec.md\n"
            with mock.patch.object(
                lifecycle,
                "run_git",
                side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0, stdout=archive_path)],
            ):
                self.assertTrue(lifecycle.evidence_matches_checkout(change, root, identity, actual))

    def test_evidence_rejects_source_change_after_validated_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(root, "archive/2026-09-20-managed", "- [x] one\n")
            (change / ".managed-task.json").write_text('{"change":"managed"}\n', encoding="utf-8")
            identity = mock.Mock()
            identity.evidence_payload.return_value = {
                "source_issue": "owner/backlog#1", "change": "managed", "worktree": "/task", "branch": "agent/task", "head": "b" * 40
            }
            actual = {**identity.evidence_payload(), "head": "a" * 40}
            with mock.patch.object(
                lifecycle,
                "run_git",
                side_effect=[mock.Mock(returncode=0), mock.Mock(returncode=0, stdout="template/scripts/finish_task.py\n")],
            ):
                self.assertFalse(lifecycle.evidence_matches_checkout(change, root, identity, actual))

    def test_content_aware_evidence_accepts_same_task_content_after_head_moves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(root, "managed", "- [x] one\n")
            proof = {"version": 1, "digest": "c" * 64, "paths": {"feature.txt": "d" * 40}, "base": "e" * 40}
            identity = mock.Mock()
            identity.evidence_payload.return_value = {
                "source_issue": "owner/backlog#1", "change": "managed", "worktree": "/task", "branch": "agent/task",
                "head": "b" * 40, "task_content": proof,
            }
            actual = {**identity.evidence_payload(), "head": "a" * 40}
            self.assertTrue(lifecycle.evidence_matches_checkout(change, root, identity, actual))

    def test_content_aware_evidence_rejects_mutated_task_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(root, "managed", "- [x] one\n")
            identity = mock.Mock()
            identity.evidence_payload.return_value = {
                "source_issue": "owner/backlog#1", "change": "managed", "worktree": "/task", "branch": "agent/task",
                "head": "b" * 40, "task_content": {"version": 1, "digest": "c" * 64},
            }
            actual = {**identity.evidence_payload(), "head": "a" * 40, "task_content": {"version": 1, "digest": "e" * 64}}
            self.assertFalse(lifecycle.evidence_matches_checkout(change, root, identity, actual))

    def test_static_platform_readiness_rejects_missing_evidence_marker_before_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            change = self.make_change(
                Path(tmp), "done", "- [x] one\n", "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            )
            with self.assertRaisesRegex(
                SystemExit,
                "Automated-Checks-Evidence.*docs/engineering/openspec-workflow.md#verify-archive-then-publish",
            ):
                lifecycle.require_static_archive_readiness(change, platform_owned=True)

    def test_static_platform_readiness_blocks_managed_change_without_route_before_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(
                root,
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            (change / ".managed-task.json").write_text(
                '{"source_issue":"owner/backlog#1","change":"done"}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(SystemExit, "routing archive gate blocked.*routing evidence is missing"):
                lifecycle.require_static_archive_readiness(change, platform_owned=True)

    def test_uncommitted_only_state_is_not_an_applicable_archive_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            lifecycle, "run_git", return_value=mock.Mock(returncode=0)
        ):
            with self.assertRaisesRegex(SystemExit, "committed diff"):
                lifecycle.require_applicable_committed_diff(Path(tmp))

    def test_archive_rejects_static_receipt_before_running_checks_or_rewriting_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            change = self.make_change(
                root, "done", "- [x] one\n", "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n"
            )
            stale = change / "automated-checks.json"
            stale.write_text('{"outcome":"stale"}\n', encoding="utf-8")
            with (
                mock.patch.object(lifecycle, "read_platform_config", return_value={}),
                mock.patch.object(lifecycle, "harness_mode", return_value="platform"),
                mock.patch.object(lifecycle, "run_checked") as run_checked,
            ):
                with self.assertRaisesRegex(
                    SystemExit,
                    "Automated-Checks-Evidence.*docs/engineering/openspec-workflow.md#verify-archive-then-publish",
                ):
                    lifecycle.archive_change(root, "done")
            run_checked.assert_not_called()
            self.assertEqual(stale.read_text(encoding="utf-8"), '{"outcome":"stale"}\n')

    def test_archive_rejects_no_committed_diff_before_running_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(
                root,
                "done",
                "- [x] one\n",
                "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\nAutomated-Checks-Evidence: automated-checks.json\n",
            )
            with (
                mock.patch.object(lifecycle, "read_platform_config", return_value={}),
                mock.patch.object(lifecycle, "harness_mode", return_value="platform"),
                mock.patch.object(lifecycle, "run_git", return_value=mock.Mock(returncode=0)),
                mock.patch.object(lifecycle, "run_checked") as run_checked,
            ):
                with self.assertRaisesRegex(SystemExit, "committed diff"):
                    lifecycle.archive_change(root, "done")
            run_checked.assert_not_called()

    def test_archive_directory_is_not_scanned_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archived = root / "openspec" / "changes" / "archive" / "2026-08-09-done"
            archived.mkdir(parents=True)
            (archived / "tasks.md").write_text("- [x] done\n", encoding="utf-8")
            self.assertEqual([], lifecycle.completed_active_changes(root))


if __name__ == "__main__":
    unittest.main()
