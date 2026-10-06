from __future__ import annotations

import builtins
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

lifecycle = load_platform_module("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")


class OpenSpecLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        # Tests that assert exact context handling start from a clean slate; tests of an
        # inherited context for another checkout set it explicitly.
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (lifecycle.ARCHIVE_TARGET_ENV, lifecycle.ARCHIVE_ROOT_ENV):
            os.environ.pop(name, None)

    def make_change(self, root: Path, name: str, tasks: str, verification: str | None = None) -> Path:
        change = root / "openspec" / "changes" / name
        change.mkdir(parents=True)
        (change / "tasks.md").write_text(tasks, encoding="utf-8")
        if verification is not None:
            (change / "verification.md").write_text(verification, encoding="utf-8")
        return change

    def test_normal_archive_launches_review_before_expensive_validation(self):
        gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "work", "- [x] done\n")
            with mock.patch.object(lifecycle, "read_platform_config", return_value={"harness_mode": "platform"}), \
                    mock.patch.object(lifecycle, "require_static_archive_readiness"), \
                    mock.patch.object(lifecycle, "require_applicable_committed_diff"), \
                    mock.patch.object(gate, "managed_candidate", return_value=False), \
                    mock.patch.object(lifecycle, "ensure_review_evidence", side_effect=SystemExit("review blocked")) as review, \
                    mock.patch.object(lifecycle, "run_checked") as validate:
                with self.assertRaisesRegex(SystemExit, "review blocked"):
                    lifecycle.archive_change(root, "work")
                review.assert_called_once_with(root, root / "openspec/changes/work")
                validate.assert_not_called()

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

    def test_alternative_markers_and_unknown_content_keep_change_incomplete(self) -> None:
        for open_task in ("+ [ ] task", "* [ ] task", "1. [ ] task", "1) [ ] task", "- [~] partial", "- [-] skipped", "-[ ] tight"):
            with self.subTest(open_task=open_task), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                change = self.make_change(root, "work", f"- [x] done\n{open_task}\n", "OpenSpec-Verify: PASS\nVerification-Method: test\n")
                self.assertEqual((2, 1), lifecycle.task_state(change))
                self.assertEqual([], lifecycle.completed_active_changes(root))
                with self.assertRaisesRegex(SystemExit, "1 of 2 task"):
                    lifecycle.require_ready(change)

    def test_task_counting_matches_upstream_markers(self) -> None:
        text = "\n".join(
            [
                "- [ ] open",
                "- [x] done",
                "- [X] done upper",
                "+ [x] plus done",
                "  3. [ x ] padded done",
                "10) [] empty",
                "- [x](https://example.com) link, not a task",
                "- [x][ref] reference link, not a task",
                "[ ] no marker",
                "- plain bullet",
            ]
        )
        self.assertEqual((6, 2), lifecycle.count_tasks(text))

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

    def _merged_main_repo(self, root: Path, main_touches_task_file: bool, extra_archive_files: tuple[str, ...] = ()):
        import subprocess
        from task_content_identity import content_identity

        def git(*args: str) -> str:
            return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()

        git("init", "-b", "main")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.invalid")
        (root / "feature.txt").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-m", "base")
        git("switch", "-c", "agent/task")
        active = root / "openspec" / "changes" / "managed"
        active.mkdir(parents=True)
        (active / "tasks.md").write_text("- [x] one\n", encoding="utf-8")
        (active / "automated-checks.json").write_text("{}\n", encoding="utf-8")
        (active / ".managed-task.json").write_text('{"change":"managed"}\n', encoding="utf-8")
        (active / "specs" / "cap").mkdir(parents=True)
        (active / "specs" / "cap" / "spec.md").write_text("delta\n", encoding="utf-8")
        (root / "feature.txt").write_text("A\nb\nc\nd\ne\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-m", "task")
        git("branch", "origin/main", "main")
        validated_head = git("rev-parse", "HEAD")
        proof = content_identity(root, "managed")
        # main advances and is merged into the task branch, then the task archives.
        git("switch", "main")
        target = root / ("feature.txt" if main_touches_task_file else "other.txt")
        target.write_text("a\nb\nc\nd\nE\n" if main_touches_task_file else "other\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-m", "main advance")
        git("branch", "-f", "origin/main", "main")
        git("switch", "agent/task")
        git("merge", "--no-edit", "main")
        archive = root / "openspec" / "changes" / "archive" / "2026-09-28-managed"
        archive.parent.mkdir(parents=True)
        active.rename(archive)
        for name in extra_archive_files:
            (archive / name).parent.mkdir(parents=True, exist_ok=True)
            (archive / name).write_text("{}\n", encoding="utf-8")
        (root / "openspec" / "specs" / "cap").mkdir(parents=True)
        (root / "openspec" / "specs" / "cap" / "spec.md").write_text("materialized\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-m", "archive")
        current = content_identity(root, "managed")
        return archive, validated_head, proof, current

    def _identity(self, validated_head: str, proof: dict, current: dict, head: str):
        identity = mock.Mock()
        identity.evidence_payload.return_value = {
            "source_issue": "owner/backlog#1", "change": "managed", "worktree": "/task", "branch": "agent/task",
            "head": head, "task_content": current,
        }
        actual = {**identity.evidence_payload(), "head": validated_head, "task_content": proof}
        return identity, actual

    def test_content_aware_evidence_survives_clean_main_merge_plus_archive(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, validated_head, proof, current = self._merged_main_repo(root, main_touches_task_file=False)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
            identity, actual = self._identity(validated_head, proof, current, head)
            self.assertNotEqual(proof["digest"], current["digest"])
            self.assertTrue(lifecycle.evidence_matches_checkout(archive, root, identity, actual))

    def test_content_aware_evidence_accepts_archive_produced_review_evidence(self) -> None:
        import subprocess
        review_files = (
            "independent-review-request.json", "independent-reviews/spec-fidelity.json",
            "independent-reviews/engineering-quality.json", "independent-review-dispositions.json",
        )
        for extra, accepted in ((review_files, True), (("unreviewed-notes.json",), False)):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive, validated_head, proof, current = self._merged_main_repo(
                    root, main_touches_task_file=False, extra_archive_files=extra
                )
                head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
                identity, actual = self._identity(validated_head, proof, current, head)
                self.assertEqual(lifecycle.evidence_matches_checkout(archive, root, identity, actual), accepted)

    def test_content_aware_evidence_rejects_main_merge_touching_task_paths(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, validated_head, proof, current = self._merged_main_repo(root, main_touches_task_file=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
            identity, actual = self._identity(validated_head, proof, current, head)
            self.assertFalse(lifecycle.evidence_matches_checkout(archive, root, identity, actual))

    def test_content_aware_evidence_rejects_source_edit_alongside_main_merge(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, validated_head, proof, current = self._merged_main_repo(root, main_touches_task_file=False)
            (root / "feature.txt").write_text("A\nb\nc\nd\nZ\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "late source edit"], cwd=root, check=True, capture_output=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
            from task_content_identity import content_identity
            identity, actual = self._identity(validated_head, proof, content_identity(root, "managed"), head)
            self.assertFalse(lifecycle.evidence_matches_checkout(archive, root, identity, actual))

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

    # --- Archive-scoped hygiene exemption (BR-386 / archive-exact-target-hygiene) ---

    def test_archive_target_exempts_only_exact_change_in_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "target", "- [x] done\n")
            self.make_change(root, "other", "- [x] done\n")
            self.assertEqual(1, lifecycle.check_hygiene(root))
            with mock.patch.dict(os.environ, self.archive_context(root, "target")):
                for stage in (lifecycle.STAGE_CANDIDATE, lifecycle.STAGE_INTEGRATION):
                    self.assertEqual(1, lifecycle.check_hygiene(root, stage))
            shutil.rmtree(root / "openspec" / "changes" / "other")
            with mock.patch.dict(os.environ, self.archive_context(root, "target")):
                self.assertEqual(0, lifecycle.check_hygiene(root))
            self.assertEqual(1, lifecycle.check_hygiene(root))

    def test_invalid_archive_target_fails_closed_in_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] done\n")
            self.make_change(root, "open", "- [ ] todo\n")
            for target in ("", "missing", "open", "archive", "../done", "done/", "DONE", "a b"):
                with self.subTest(target=target), mock.patch.dict(os.environ, self.archive_context(root, target)):
                    with self.assertRaisesRegex(SystemExit, "archive target"):
                        lifecycle.check_hygiene(root)

    def test_archive_rejects_invalid_target_before_any_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "open", "- [ ] todo\n")
            with mock.patch.object(lifecycle, "run_checked") as run_checked, \
                    mock.patch.object(lifecycle, "ensure_review_evidence") as review:
                for target in ("missing", "open", "../open", ""):
                    with self.subTest(target=target), self.assertRaisesRegex(SystemExit, "archive target"):
                        lifecycle.archive_change(root, target)
            run_checked.assert_not_called()
            review.assert_not_called()

    def test_archive_target_environment_is_a_copy_not_the_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] done\n")
            env = lifecycle.archive_target_environment(root, "done")
            self.assertEqual("done", env[lifecycle.ARCHIVE_TARGET_ENV])
            self.assertEqual(os.path.realpath(root), env[lifecycle.ARCHIVE_ROOT_ENV])
            self.assertNotEqual("done", os.environ.get(lifecycle.ARCHIVE_TARGET_ENV))
            self.assertNotIn(lifecycle.ARCHIVE_ROOT_ENV, os.environ)

    def archive_context(self, root: Path | str, target: str) -> dict[str, str]:
        return {lifecycle.ARCHIVE_TARGET_ENV: target, lifecycle.ARCHIVE_ROOT_ENV: os.path.realpath(root)}

    def test_context_issued_for_another_checkout_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] done\n")
            for context in (self.archive_context(other, "done"), self.archive_context("/nonexistent", "x")):
                with self.subTest(context=context), mock.patch.dict(os.environ, context):
                    self.assertEqual(1, lifecycle.check_hygiene(root))

    def test_context_for_same_root_exempts_only_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "target", "- [x] done\n")
            self.make_change(root, "other", "- [x] done\n")
            with mock.patch.dict(os.environ, self.archive_context(root, "target")):
                self.assertEqual(1, lifecycle.check_hygiene(root))
            shutil.rmtree(root / "openspec" / "changes" / "other")
            with mock.patch.dict(os.environ, self.archive_context(root, "target")):
                self.assertEqual(0, lifecycle.check_hygiene(root))

    def test_half_set_archive_context_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "done", "- [x] done\n")
            for context in ({lifecycle.ARCHIVE_TARGET_ENV: "done"}, {lifecycle.ARCHIVE_ROOT_ENV: os.path.realpath(root)}):
                with self.subTest(context=context), mock.patch.dict(os.environ, context):
                    with self.assertRaisesRegex(SystemExit, "malformed archive context"):
                        lifecycle.check_hygiene(root)

    def test_finalize_rejects_invalid_target_before_any_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_change(root, "open", "- [ ] todo\n")
            with mock.patch.object(lifecycle, "run_checked") as run_checked, \
                    mock.patch.object(lifecycle, "require_review_evidence") as review:
                for target in ("missing", "open", "../open"):
                    with self.subTest(target=target), self.assertRaisesRegex(SystemExit, "archive target"):
                        lifecycle.archive_change(root, target, finalize=True)
            run_checked.assert_not_called()
            review.assert_not_called()
            self.assertTrue((root / "openspec" / "changes" / "open").is_dir())

    # End-to-end: real select_checks.py and the real standard template check mapping.

    FAKE_OPENSPEC = (
        "#!/bin/sh\n"
        'if [ "$1" = archive ]; then\n'
        '  mkdir -p openspec/changes/archive && mv "openspec/changes/$2" "openspec/changes/archive/2026-01-01-$2"\n'
        "fi\nexit 0\n"
    )

    def make_standard_repo(self, root: Path) -> None:
        shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (root / "dev-platform").mkdir()
        shutil.copy(ROOT / "template" / "dev-platform" / "checks.toml", root / "dev-platform" / "checks.toml")
        (root / ".dev-platform.toml").write_text(
            'schema_version = 2\nplatform_version = "customer"\nproject_name = "p"\nproject_slug = "p"\n'
            'main_branch = "main"\nharness_mode = "platform"\n',
            encoding="utf-8",
        )
        bin_dir = root / "bin"
        bin_dir.mkdir()
        openspec = bin_dir / "openspec"
        openspec.write_text(self.FAKE_OPENSPEC, encoding="utf-8")
        openspec.chmod(0o755)
        git = lambda *args: subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)  # noqa: E731
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        git("add", "-A")
        git("commit", "-q", "-m", "base")
        origin = Path(tempfile.mkdtemp(suffix="-origin.git"))
        self.addCleanup(shutil.rmtree, origin, True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
        git("remote", "add", "origin", str(origin))
        git("push", "-q", "origin", "main")
        git("fetch", "-q", "origin")

    def commit_all(self, root: Path) -> None:
        for args in (["add", "-A"], ["commit", "-q", "-m", "change"]):
            subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    def run_archive_e2e(self, root: Path, name: str) -> int:
        patches = [
            mock.patch.object(lifecycle, "require_static_archive_readiness"),
            mock.patch.object(lifecycle, "require_applicable_committed_diff"),
            mock.patch.object(lifecycle, "ensure_review_evidence"),
            mock.patch.object(lifecycle, "require_ready"),
            mock.patch.object(lifecycle.shutil, "which", return_value=str(root / "bin" / "openspec")),
        ]
        gate = load_platform_module("pr_review_gate", SCRIPTS / "pr_review_gate.py")
        patches.append(mock.patch.object(gate, "managed_candidate", return_value=False))
        env = {k: v for k, v in os.environ.items() if k not in (lifecycle.ARCHIVE_TARGET_ENV, lifecycle.ARCHIVE_ROOT_ENV)}
        with mock.patch.dict(os.environ, env, clear=True):
            for patch in patches:
                patch.start()
            try:
                return lifecycle.archive_change(root, name)
            finally:
                mock.patch.stopall()

    def ordinary_check(self, root: Path) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in (lifecycle.ARCHIVE_TARGET_ENV, lifecycle.ARCHIVE_ROOT_ENV)}
        return subprocess.run(
            ["python3", "scripts/openspec_lifecycle.py", "check"], cwd=root, env=env, capture_output=True, text=True
        )

    def test_e2e_standard_mapping_reproduces_deadlock_and_archive_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_standard_repo(root)
            self.make_change(root, "done", "- [x] done\n", "OpenSpec-Verify: PASS\nVerification-Method: test\n")
            self.commit_all(root)
            # Old behavior: the same select_checks invocation without the scoped target deadlocks.
            env = {k: v for k, v in os.environ.items() if k not in (lifecycle.ARCHIVE_TARGET_ENV, lifecycle.ARCHIVE_ROOT_ENV)}
            old = subprocess.run(
                ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute"],
                cwd=root, env=env, capture_output=True, text=True,
            )
            self.assertNotEqual(0, old.returncode, old.stdout + old.stderr)
            self.assertIn("done: all tasks are complete", old.stdout + old.stderr)
            self.assertEqual(1, self.ordinary_check(root).returncode)
            # New behavior: archive of that exact target completes through the real mapping.
            self.assertEqual(0, self.run_archive_e2e(root, "done"))
            self.assertFalse((root / "openspec" / "changes" / "done").exists())
            self.assertEqual(0, self.ordinary_check(root).returncode)

    def test_e2e_second_completed_change_blocks_and_leaves_no_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_standard_repo(root)
            self.make_change(root, "done", "- [x] done\n", "OpenSpec-Verify: PASS\nVerification-Method: test\n")
            self.make_change(root, "stale", "- [x] done\n")
            self.commit_all(root)
            with self.assertRaises(SystemExit):
                self.run_archive_e2e(root, "done")
            self.assertTrue((root / "openspec" / "changes" / "done").is_dir())
            self.assertTrue((root / "openspec" / "changes" / "stale").is_dir())
            self.assertNotIn(lifecycle.ARCHIVE_TARGET_ENV, os.environ)
            blocked = self.ordinary_check(root)
            self.assertEqual(1, blocked.returncode)
            self.assertIn("done:", blocked.stdout)
            self.assertIn("stale:", blocked.stdout)

    def test_e2e_invalid_target_changes_no_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_standard_repo(root)
            self.make_change(root, "done", "- [x] done\n")
            for target in ("missing", "../done", ""):
                with self.subTest(target=target), self.assertRaisesRegex(SystemExit, "archive target"):
                    self.run_archive_e2e(root, target)
            self.assertTrue((root / "openspec" / "changes" / "done").is_dir())
            self.assertEqual(1, self.ordinary_check(root).returncode)


if __name__ == "__main__":
    unittest.main()
