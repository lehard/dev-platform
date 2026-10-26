from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import managed_task  # noqa: E402
import openspec_lifecycle  # noqa: E402
import select_checks  # noqa: E402
import task_content_identity  # noqa: E402


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


class ManagedCheckoutIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.integration = Path(self.tmp.name) / "integration"
        self.integration.mkdir()
        git(self.integration, "init", "-q", "-b", "main")
        git(self.integration, "config", "user.name", "test")
        git(self.integration, "config", "user.email", "test@example.invalid")
        (self.integration / "README.md").write_text("initial\n", encoding="utf-8")
        git(self.integration, "add", "README.md")
        git(self.integration, "commit", "-qm", "initial")
        self.task = Path(self.tmp.name) / "task"
        git(self.integration, "worktree", "add", "-q", "-b", "agent/managed-checkout", str(self.task))
        (self.task / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "example-org/development-backlog#7", "change": "managed-checkout"}) + "\n",
            encoding="utf-8",
        )
        self.sibling = Path(self.tmp.name) / "sibling"
        git(self.integration, "worktree", "add", "-q", "-b", "agent/sibling", str(self.sibling))
        (self.sibling / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "example-org/development-backlog#8", "change": "sibling-checkout"}) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_exact_registered_task_checkout_is_accepted(self) -> None:
        identity = managed_task.require_managed_checkout_identity(self.task, expected_change="managed-checkout")
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.worktree, self.task.resolve())
        self.assertEqual(identity.branch, "agent/managed-checkout")
        self.assertEqual(identity.change, "managed-checkout")

    def test_integration_checkout_is_rejected_before_validation(self) -> None:
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "expected change 'managed-checkout'.*Remediation: cd"):
            managed_task.require_managed_checkout_identity(self.integration, expected_change="managed-checkout")

    def test_integration_diagnostic_identifies_only_provable_current_task_stray(self) -> None:
        stray = self.integration / "openspec" / "changes" / "managed-checkout" / "note.txt"
        stray.parent.mkdir(parents=True)
        stray.write_text("stray\n", encoding="utf-8")
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "Current-task stray integration paths: openspec/changes/managed-checkout/note.txt"):
            managed_task.require_managed_checkout_identity(self.integration, expected_change="managed-checkout")

    def test_integration_diagnostic_never_claims_foreign_strays(self) -> None:
        foreign = self.integration / "ordinary-source.txt"
        foreign.write_text("foreign\n", encoding="utf-8")
        with self.assertRaises(managed_task.ManagedTaskError) as raised:
            managed_task.require_managed_checkout_identity(self.integration, expected_change="managed-checkout")
        self.assertNotIn("ordinary-source.txt", str(raised.exception))

    def test_sibling_checkout_is_rejected_for_expected_managed_task(self) -> None:
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "expected change 'managed-checkout'.*current checkout is"):
            managed_task.require_managed_checkout_identity(self.sibling, expected_change="managed-checkout")

    def test_task_state_source_mismatch_is_rejected_for_canonical_identity(self) -> None:
        (self.task / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "example-org/development-backlog#99", "change": "managed-checkout"}) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "cannot find registered task state for canonical identity"):
            managed_task.require_managed_checkout_identity(
                self.task,
                expected_change="managed-checkout",
                expected_source_issue="example-org/development-backlog#7",
            )

    def test_cwd_reset_to_integration_blocks_before_selected_command(self) -> None:
        command = "printf SHOULD-NOT-RUN"
        original_argv = sys.argv
        try:
            sys.argv = ["select_checks.py", "--mode", "protected-full", "--execute"]
            with (
                mock.patch.object(select_checks, "current_worktree_root", return_value=self.integration),
                mock.patch.object(select_checks, "load_config", return_value={"settings": {"full_commands": [command]}}),
                mock.patch.object(
                    select_checks,
                    "read_platform_config",
                    return_value={"harness_mode": "platform", "main_branch": "main"},
                ),
                mock.patch("sys.stdout") as stdout,
            ):
                with self.assertRaisesRegex(SystemExit, "identity gate blocked validation"):
                    select_checks.main()
        finally:
            sys.argv = original_argv
        output = "".join(str(call.args[0]) for call in stdout.write.call_args_list)
        self.assertNotIn("DEV_PLATFORM_CHECK_COMMAND", output)
        self.assertNotIn("SHOULD-NOT-RUN", output)

    def _run_select_checks(self, *extra: str) -> str:
        command = "printf SHOULD-NOT-RUN"
        original_argv = sys.argv
        try:
            sys.argv = ["select_checks.py", "--mode", "protected-full", "--execute", *extra]
            with (
                mock.patch.object(select_checks, "current_worktree_root", return_value=self.task),
                mock.patch.object(select_checks, "load_config", return_value={"settings": {"full_commands": [command]}}),
                mock.patch.object(
                    select_checks,
                    "read_platform_config",
                    return_value={"harness_mode": "platform", "main_branch": "main"},
                ),
                mock.patch("sys.stdout") as stdout,
            ):
                try:
                    select_checks.main()
                except SystemExit as exc:
                    message = str(exc)
                else:
                    self.fail("select_checks did not stop")
        finally:
            sys.argv = original_argv
        output = "".join(str(call.args[0]) for call in stdout.write.call_args_list)
        self.assertNotIn("DEV_PLATFORM_CHECK_COMMAND", output)
        self.assertNotIn("SHOULD-NOT-RUN", output)
        return message

    def _active_change(self, tasks: str) -> Path:
        change = self.task / "openspec" / "changes" / "managed-checkout"
        change.mkdir(parents=True)
        (change / "tasks.md").write_text(tasks, encoding="utf-8")
        return change

    def test_active_managed_change_without_evidence_is_refused_before_any_command(self) -> None:
        self._active_change("- [x] 1.1 done\n")
        message = self._run_select_checks()
        self.assertIn("Managed task preflight blocked validation before any expensive command started", message)
        self.assertIn("--evidence openspec/changes/managed-checkout/automated-checks.json", message)

    def test_open_task_checkbox_is_refused_before_any_command(self) -> None:
        self._active_change("- [x] 1.1 done\n- [ ] 2.1 run checks\n")
        message = self._run_select_checks("--evidence", "openspec/changes/managed-checkout/automated-checks.json")
        self.assertIn("1 of 2 task(s) remain incomplete", message)
        self.assertIn("before the full run", message)

    def test_archive_ready_or_archived_change_passes_the_preflight(self) -> None:
        select_checks.require_active_change_ready(self.task, "managed-checkout", False)  # archived: no active change
        self._active_change("- [x] 1.1 done\n")
        select_checks.require_active_change_ready(self.task, "managed-checkout", True)

    def test_detached_task_checkout_is_rejected(self) -> None:
        git(self.task, "checkout", "--detach", "-q")
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "detached"):
            managed_task.require_managed_checkout_identity(self.task, expected_change="managed-checkout")

    def test_quick_task_checkout_ignores_stale_sibling_managed_state(self) -> None:
        quick = Path(self.tmp.name) / "quick"
        git(self.integration, "worktree", "add", "-q", "-b", "agent/quick-task", str(quick))
        # ``self.sibling`` still carries leftover managed task-local state from
        # setUp; ``quick`` has none of its own and is not the integration root.
        identity = managed_task.require_managed_checkout_identity(quick)
        self.assertIsNone(identity)

    def test_integration_checkout_without_expectation_still_finds_the_sole_managed_task(self) -> None:
        # Mirrors ``test_cwd_reset_to_integration_blocks_before_selected_command``
        # at the ``managed_task`` API level: an invocation with no explicit
        # expected identity, resolved to the shared integration checkout while
        # a managed task is active elsewhere, must still fail closed.
        git(self.integration, "worktree", "remove", "--force", str(self.sibling))
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "expected change 'managed-checkout'.*Remediation: cd"):
            managed_task.require_managed_checkout_identity(self.integration)

    def test_ambiguous_managed_state_without_expectation_fails_closed(self) -> None:
        # ``self.task`` and ``self.sibling`` both carry distinct managed
        # task-local state; with no expected identity supplied, neither can be
        # inferred as "the" task, and ambiguity must fail closed rather than
        # silently pick one.
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "ambiguous across registered task worktrees"):
            managed_task.require_managed_checkout_identity(self.integration)


    def _task_commit(self) -> managed_task.ManagedCheckoutIdentity:
        (self.task / "feature.txt").write_text("feature\n", encoding="utf-8")
        git(self.task, "add", "feature.txt")
        git(self.task, "commit", "-qm", "feature")
        identity = managed_task.require_managed_checkout_identity(self.task, expected_change="managed-checkout")
        assert identity is not None
        return identity

    def test_evidence_payload_binds_the_task_content_proof(self) -> None:
        git(self.integration, "update-ref", "refs/remotes/origin/main", "main")
        identity = self._task_commit()
        payload = identity.evidence_payload()
        expected = task_content_identity.content_identity(self.task.resolve(), "managed-checkout")
        self.assertIsNotNone(expected)
        self.assertEqual(payload["task_content"], expected)
        self.assertEqual(managed_task.require_task_content(payload, "selected-check evidence"), expected)

    def test_proof_computation_error_is_raised_not_swallowed(self) -> None:
        identity = self._task_commit()
        with mock.patch.object(task_content_identity, "content_identity", side_effect=RuntimeError("git object store unreadable")):
            with self.assertRaisesRegex(RuntimeError, "git object store unreadable"):
                identity.evidence_payload()

    def test_no_origin_payload_stays_diagnostic_but_mandatory_check_refuses_it(self) -> None:
        identity = self._task_commit()
        payload = identity.evidence_payload()
        self.assertNotIn("task_content", payload)
        self.assertEqual(payload["change"], "managed-checkout")
        with self.assertRaisesRegex(
            managed_task.ManagedTaskError,
            "selected-check evidence requires the task-content proof of managed change 'managed-checkout'.*Fetch origin/main",
        ):
            managed_task.require_task_content(payload, "selected-check evidence")

    def test_evidence_run_without_task_content_proof_blocks_before_selected_command(self) -> None:
        self._task_commit()
        command = "printf SHOULD-NOT-RUN"
        evidence = Path(self.tmp.name) / "automated-checks.json"
        original_argv = sys.argv
        try:
            sys.argv = ["select_checks.py", "--mode", "protected-full", "--execute", "--evidence", str(evidence)]
            with (
                mock.patch.object(select_checks, "current_worktree_root", return_value=self.task.resolve()),
                mock.patch.object(select_checks, "load_config", return_value={"settings": {"full_commands": [command]}}),
                mock.patch.object(
                    select_checks,
                    "read_platform_config",
                    return_value={"harness_mode": "platform", "main_branch": "main"},
                ),
                mock.patch("sys.stdout") as stdout,
            ):
                with self.assertRaisesRegex(SystemExit, "identity gate blocked validation.*requires the task-content proof"):
                    select_checks.main()
        finally:
            sys.argv = original_argv
        output = "".join(str(call.args[0]) for call in stdout.write.call_args_list)
        self.assertNotIn("DEV_PLATFORM_CHECK_COMMAND", output)
        self.assertFalse(evidence.exists())


class ManagedTaskImportTests(unittest.TestCase):
    def test_gates_use_the_real_managed_checkout_identity(self) -> None:
        self.assertIs(select_checks.require_managed_checkout_identity, managed_task.require_managed_checkout_identity)
        self.assertIs(openspec_lifecycle.require_managed_checkout_identity, managed_task.require_managed_checkout_identity)
        self.assertIs(openspec_lifecycle.read_provenance, managed_task.read_provenance)

    def test_missing_managed_task_module_stops_the_gate_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / "scripts"
            shutil.copytree(SCRIPTS, scripts, ignore=shutil.ignore_patterns("__pycache__", "managed_task.py"))
            for module in ("select_checks", "openspec_lifecycle"):
                result = subprocess.run(
                    [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(scripts)!r}); import {module}"],
                    text=True, capture_output=True, check=False,
                )
                self.assertNotEqual(result.returncode, 0, module)
                self.assertIn("No module named 'managed_task'", result.stderr, module)


if __name__ == "__main__":
    unittest.main()
