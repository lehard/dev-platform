from __future__ import annotations

import json
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
import select_checks  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
