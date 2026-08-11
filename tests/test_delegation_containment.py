from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "template" / "scripts" / "delegation_containment.py"

SPEC = importlib.util.spec_from_file_location("delegation_containment", SCRIPT_PATH)
assert SPEC and SPEC.loader
delegation_containment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = delegation_containment
SPEC.loader.exec_module(delegation_containment)


def git(*arguments: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=check)


class DelegationContainmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.integration = Path(self.temporary.name) / "integration"
        self.integration.mkdir()
        git("init", "-b", "main", cwd=self.integration)
        git("config", "user.email", "test@example.com", cwd=self.integration)
        git("config", "user.name", "Containment Test", cwd=self.integration)
        (self.integration / "tracked.txt").write_text("initial\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)
        git("commit", "-m", "initial", cwd=self.integration)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def add_worktree(self, name: str) -> Path:
        path = Path(self.temporary.name) / "worktrees" / name
        git("worktree", "add", "-b", name, str(path), "main", cwd=self.integration)
        return path

    def test_resolve_assigned_worktree_accepts_registered_worktree(self) -> None:
        worktree = self.add_worktree("agent-a")
        resolved = delegation_containment.resolve_assigned_worktree(self.integration, worktree)
        self.assertEqual(resolved, worktree.resolve())

    def test_resolve_assigned_worktree_rejects_integration_copy_itself(self) -> None:
        with self.assertRaisesRegex(delegation_containment.ContainmentError, "must not be the integration copy"):
            delegation_containment.resolve_assigned_worktree(self.integration, self.integration)

    def test_resolve_assigned_worktree_rejects_unregistered_path(self) -> None:
        unregistered = Path(self.temporary.name) / "not-a-worktree"
        unregistered.mkdir()
        with self.assertRaisesRegex(delegation_containment.ContainmentError, "not a registered git worktree"):
            delegation_containment.resolve_assigned_worktree(self.integration, unregistered)

    def test_resolve_assigned_worktree_rejects_relative_path(self) -> None:
        with self.assertRaisesRegex(delegation_containment.ContainmentError, "must be an absolute path"):
            delegation_containment.resolve_assigned_worktree(self.integration, "relative/path")

    def test_delegated_writer_inside_assigned_worktree_passes(self) -> None:
        worktree = self.add_worktree("agent-a")
        before = delegation_containment.snapshot(self.integration)
        (worktree / "agent-a-output.txt").write_text("written by the delegated agent\n", encoding="utf-8")
        git("add", "agent-a-output.txt", cwd=worktree)
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertFalse(result.violated)
        self.assertEqual(result.new_changes, ())
        self.assertFalse(result.head_moved)

    def test_delegated_writer_into_integration_main_is_blocked(self) -> None:
        self.add_worktree("agent-a")  # assigned elsewhere; writer misbehaves and writes into integration copy
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "escaped.txt").write_text("this should not be here\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertIn("escaped.txt", result.new_changes)
        self.assertFalse(result.head_moved)
        message = delegation_containment.format_violation_message(Path("/agent-a"), result)
        self.assertIn("escaped.txt", message)

    def test_direct_commit_into_integration_main_is_blocked(self) -> None:
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "sneaky.txt").write_text("committed directly\n", encoding="utf-8")
        git("add", "sneaky.txt", cwd=self.integration)
        git("commit", "-m", "sneaky direct commit", cwd=self.integration)
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertTrue(result.head_moved)

    def test_pre_existing_dirty_integration_main_is_not_a_new_violation(self) -> None:
        # integration/main already has someone else's uncommitted work before delegation starts.
        (self.integration / "someone-elses-work.txt").write_text("in progress\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        self.add_worktree("agent-a")
        # Nothing further changes in integration/main during delegation.
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertFalse(result.violated)
        self.assertEqual(result.new_changes, ())
        self.assertIn("someone-elses-work.txt", result.pre_existing_changes)
        # The pre-existing file must still be present, untouched by the containment check.
        self.assertTrue((self.integration / "someone-elses-work.txt").exists())
        self.assertEqual(
            (self.integration / "someone-elses-work.txt").read_text(encoding="utf-8"), "in progress\n"
        )

    def test_pre_existing_dirty_state_does_not_mask_a_new_violation(self) -> None:
        (self.integration / "someone-elses-work.txt").write_text("in progress\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "new-escape.txt").write_text("new violation\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertEqual(result.new_changes, ("new-escape.txt",))
        self.assertIn("someone-elses-work.txt", result.pre_existing_changes)
        self.assertNotIn("someone-elses-work.txt", result.new_changes)

    def test_snapshot_failure_is_a_containment_error_not_a_silent_pass(self) -> None:
        not_a_repo = Path(self.temporary.name) / "not-a-repo"
        not_a_repo.mkdir()
        with self.assertRaises(delegation_containment.ContainmentError):
            delegation_containment.snapshot(not_a_repo)

    def test_record_containment_friction_writes_local_event_without_github(self) -> None:
        target = self.integration / "scripts"
        target.mkdir()
        for name in ("_platform_common.py", "agent_friction.py"):
            (target / name).write_bytes((ROOT / "template" / "scripts" / name).read_bytes())
        (self.integration / ".dev-platform.toml").write_text(
            'main_branch = "main"\nharness_mode = "platform"\n\n[paths]\n'
            'friction_log = ".claude/agent-friction.jsonl"\n'
            'friction_state = ".claude/agent-friction-state.json"\n'
            'friction_reports = ".claude/reports/process-improvement"\n',
            encoding="utf-8",
        )
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "escaped.txt").write_text("oops\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)

        env_without_github = {"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(Path(self.temporary.name))}
        import os

        original_environ = dict(__import__("os").environ)
        try:
            os.environ.clear()
            os.environ.update(env_without_github)
            delegation_containment.record_containment_friction(
                self.integration, Path("/agent-a"), result, task="verify containment"
            )
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

        log_file = self.integration / ".claude" / "agent-friction.jsonl"
        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("delegated-write-containment-violation", content)
        self.assertIn("escaped.txt", content)


if __name__ == "__main__":
    unittest.main()
