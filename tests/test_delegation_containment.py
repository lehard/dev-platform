from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "template" / "scripts" / "delegation_containment.py"
# verify_remote_fast_forward() does a local `from _platform_common import
# read_platform_config`; that sibling module must be importable too.
sys.path.insert(0, str(SCRIPT_PATH.parent))

SPEC = importlib.util.spec_from_file_location("delegation_containment", SCRIPT_PATH)
assert SPEC and SPEC.loader
delegation_containment = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = delegation_containment
SPEC.loader.exec_module(delegation_containment)


def git(
    *arguments: str, cwd: Path, check: bool = True, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = {**os.environ, **env} if env else None
    return subprocess.run(
        ["git", *arguments], cwd=cwd, text=True, capture_output=True, check=check, env=merged_env
    )


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
        self.assertEqual(result.disappeared_changes, ())
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

    # --- content-aware fingerprinting: the core correctness gap this change fixes ---

    def test_same_status_content_mutation_of_already_dirty_tracked_file_is_a_violation(self) -> None:
        # tracked.txt is already dirty (" M") before delegation starts.
        (self.integration / "tracked.txt").write_text("first edit\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        self.assertEqual(before.paths["tracked.txt"].status, " M")
        # The delegated writer changes its *contents* again, but the status code stays " M".
        (self.integration / "tracked.txt").write_text("second edit by delegated writer\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        self.assertEqual(after.paths["tracked.txt"].status, " M")
        self.assertNotEqual(before.paths["tracked.txt"].fingerprint, after.paths["tracked.txt"].fingerprint)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertIn("tracked.txt", result.new_changes)
        self.assertNotIn("tracked.txt", result.pre_existing_changes)

    def test_unchanged_dirty_tracked_index_and_untracked_state_is_not_a_violation(self) -> None:
        (self.integration / "tracked.txt").write_text("staged edit\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)  # staged ("M ")
        (self.integration / "loose.txt").write_text("untracked\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        self.assertEqual(before.paths["tracked.txt"].status, "M ")
        self.assertEqual(before.paths["loose.txt"].status, "??")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertFalse(result.violated)
        self.assertEqual(result.new_changes, ())
        self.assertEqual(set(result.pre_existing_changes), {"tracked.txt", "loose.txt"})

    def test_staged_index_content_change_is_detected_even_with_clean_worktree(self) -> None:
        (self.integration / "tracked.txt").write_text("staged v1\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)
        before = delegation_containment.snapshot(self.integration)
        self.assertEqual(before.paths["tracked.txt"].status, "M ")
        # Re-stage different content; status code stays "M " (worktree matches index both times).
        (self.integration / "tracked.txt").write_text("staged v2 by delegated writer\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)
        after = delegation_containment.snapshot(self.integration)
        self.assertEqual(after.paths["tracked.txt"].status, "M ")
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertIn("tracked.txt", result.new_changes)

    def test_untracked_content_mutation_without_path_disappearance_is_detected(self) -> None:
        (self.integration / "loose.txt").write_text("version one\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "loose.txt").write_text("version two\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        self.assertEqual(before.paths["loose.txt"].status, after.paths["loose.txt"].status)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertEqual(result.new_changes, ("loose.txt",))

    def test_untracked_file_creation_is_a_violation(self) -> None:
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "brand-new.txt").write_text("created during delegation\n", encoding="utf-8")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertEqual(result.new_changes, ("brand-new.txt",))

    def test_untracked_file_deletion_is_reported_as_disappeared(self) -> None:
        (self.integration / "loose.txt").write_text("will be deleted\n", encoding="utf-8")
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "loose.txt").unlink()
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertEqual(result.disappeared_changes, ("loose.txt",))
        self.assertEqual(result.new_changes, ())

    def test_tracked_file_deletion_in_worktree_is_a_violation(self) -> None:
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "tracked.txt").unlink()
        after = delegation_containment.snapshot(self.integration)
        self.assertEqual(after.paths["tracked.txt"].status, " D")
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertIn("tracked.txt", result.new_changes)

    def test_symlink_target_mutation_is_detected(self) -> None:
        if os.name == "nt":
            self.skipTest("symlinks are not reliably creatable on this platform")
        (self.integration / "link.txt").symlink_to("tracked.txt")
        before = delegation_containment.snapshot(self.integration)
        (self.integration / "link.txt").unlink()
        (self.integration / "target-two.txt").write_text("other target\n", encoding="utf-8")
        (self.integration / "link.txt").symlink_to("target-two.txt")
        after = delegation_containment.snapshot(self.integration)
        result = delegation_containment.check_containment(before, after)
        self.assertTrue(result.violated)
        self.assertIn("link.txt", result.new_changes)

    def test_snapshot_content_hashing_does_not_touch_clean_tracked_files(self) -> None:
        # A large clean tracked file must never be read/hashed by snapshot(); only
        # dirty/untracked paths are fingerprinted, so this stays fast regardless of
        # overall repository size.
        big = self.integration / "big-clean-file.bin"
        big.write_bytes(b"0" * (2 * 1024 * 1024))
        git("add", "big-clean-file.bin", cwd=self.integration)
        git("commit", "-m", "add big clean file", cwd=self.integration)
        snap = delegation_containment.snapshot(self.integration)
        self.assertNotIn("big-clean-file.bin", snap.paths)

    def _with_main_branch_config(self) -> None:
        (self.integration / ".dev-platform.toml").write_text('main_branch = "main"\n', encoding="utf-8")

    def test_verify_remote_fast_forward_accepts_a_matching_fast_forward(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", after_head, cwd=self.integration)
        self.assertTrue(
            delegation_containment.verify_remote_fast_forward(self.integration, before_head, after_head)
        )

    def test_verify_remote_fast_forward_rejects_a_mismatched_remote_ref(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        # refs/remotes/origin/main still points at the old head, not after_head.
        git("update-ref", "refs/remotes/origin/main", before_head, cwd=self.integration)
        self.assertFalse(
            delegation_containment.verify_remote_fast_forward(self.integration, before_head, after_head)
        )

    def test_verify_remote_fast_forward_rejects_a_non_ancestor_before_head(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        tree = git("write-tree", cwd=self.integration).stdout.strip()
        unrelated = git("commit-tree", tree, "-m", "unrelated", cwd=self.integration).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", unrelated, cwd=self.integration)
        self.assertFalse(
            delegation_containment.verify_remote_fast_forward(self.integration, before_head, unrelated)
        )

    def test_verify_remote_fast_forward_fails_closed_without_remote_ref(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        # No refs/remotes/origin/main exists at all.
        self.assertFalse(
            delegation_containment.verify_remote_fast_forward(self.integration, before_head, after_head)
        )

    def test_verify_remote_fast_forward_uses_default_main_branch_without_platform_config(self) -> None:
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", after_head, cwd=self.integration)
        # No .dev-platform.toml: read_platform_config() itself must still resolve a
        # default main_branch of "main", so this is expected to pass -- verifying the
        # fallback path is exercised rather than silently short-circuited.
        self.assertTrue(
            delegation_containment.verify_remote_fast_forward(self.integration, before_head, after_head)
        )

    def test_verify_historical_external_advance_accepts_reflog_bound_after_head_no_longer_current_tip(
        self,
    ) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git(
            "update-ref",
            "refs/remotes/origin/main",
            after_head,
            cwd=self.integration,
            env={"GIT_COMMITTER_DATE": "2026-01-01T12:00:00+00:00"},
        )
        # Main legitimately advances further after the historical incident -- after_head
        # is no longer the current tip, which is exactly the bug this change fixes.
        (self.integration / "third.txt").write_text("third\n", encoding="utf-8")
        git("add", "third.txt", cwd=self.integration)
        git("commit", "-m", "third", cwd=self.integration)
        newest_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", newest_head, cwd=self.integration)
        self.assertTrue(
            delegation_containment.verify_historical_external_advance(
                self.integration,
                before_head,
                after_head,
                not_before="2026-01-01T00:00:00+00:00",
                not_after="2026-01-01T23:59:59+00:00",
            )
        )

    def test_verify_historical_external_advance_rejects_reflog_timestamp_outside_window(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        after_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git(
            "update-ref",
            "refs/remotes/origin/main",
            after_head,
            cwd=self.integration,
            env={"GIT_COMMITTER_DATE": "2026-01-01T12:00:00+00:00"},
        )
        # after_head is a real ancestor of current main, but the supplied window does not
        # cover the reflog-recorded timestamp -- ancestry alone must not be enough.
        self.assertFalse(
            delegation_containment.verify_historical_external_advance(
                self.integration,
                before_head,
                after_head,
                not_before="2020-01-01T00:00:00+00:00",
                not_after="2020-01-01T23:59:59+00:00",
            )
        )

    def test_verify_historical_external_advance_rejects_non_ancestor_of_current_main(self) -> None:
        self._with_main_branch_config()
        before_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        tree = git("write-tree", cwd=self.integration).stdout.strip()
        unrelated = git("commit-tree", tree, "-m", "unrelated", cwd=self.integration).stdout.strip()
        # Current main stays at real, accepted history -- not the orphan commit.
        git("update-ref", "refs/remotes/origin/main", before_head, cwd=self.integration)
        self.assertFalse(
            delegation_containment.verify_historical_external_advance(
                self.integration,
                before_head,
                unrelated,
                not_before="2000-01-01T00:00:00+00:00",
                not_after="2100-01-01T00:00:00+00:00",
            )
        )

    def test_verify_historical_external_advance_rejects_non_fast_forward_before_after(self) -> None:
        self._with_main_branch_config()
        earlier_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        (self.integration / "second.txt").write_text("second\n", encoding="utf-8")
        git("add", "second.txt", cwd=self.integration)
        git("commit", "-m", "second", cwd=self.integration)
        later_head = git("rev-parse", "HEAD", cwd=self.integration).stdout.strip()
        git("update-ref", "refs/remotes/origin/main", later_head, cwd=self.integration)
        # before_head (later_head) is not an ancestor of after_head (earlier_head): non-fast-forward.
        self.assertFalse(
            delegation_containment.verify_historical_external_advance(
                self.integration,
                later_head,
                earlier_head,
                not_before="2000-01-01T00:00:00+00:00",
                not_after="2100-01-01T00:00:00+00:00",
            )
        )

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

        # A stub `gh` placed first on PATH proves isolation structurally: even if this
        # stub would be the *first* `gh` resolved (as a real, host-authenticated `gh`
        # could be -- e.g. Homebrew's /usr/local/bin on Intel Macs, with credentials
        # in the OS keychain rather than $HOME), it must never be invoked. Scrubbing
        # PATH/HOME to merely hide a real `gh` was host-dependent and is not relied on
        # here; `route=False` is what must prevent the GitHub call.
        stub_bin = Path(self.temporary.name) / "stub-bin"
        stub_bin.mkdir()
        stub_gh = stub_bin / "gh"
        stub_invocation_log = stub_bin / "gh-invoked.log"
        stub_gh.write_text(f'#!/bin/sh\necho "$@" >> "{stub_invocation_log}"\nexit 1\n', encoding="utf-8")
        stub_gh.chmod(0o755)

        original_environ = dict(os.environ)
        try:
            os.environ["PATH"] = f"{stub_bin}{os.pathsep}{original_environ.get('PATH', '')}"
            delegation_containment.record_containment_friction(
                self.integration, Path("/agent-a"), result, task="verify containment", enforcement_tier="hard", route=False,
            )
        finally:
            os.environ.clear()
            os.environ.update(original_environ)

        self.assertFalse(
            stub_invocation_log.exists(),
            "hermetic synthetic containment friction must never invoke gh, even when gh is resolvable",
        )

        log_file = self.integration / ".claude" / "agent-friction.jsonl"
        self.assertTrue(log_file.exists())
        content = log_file.read_text(encoding="utf-8")
        self.assertIn("delegated-write-containment-violation", content)
        self.assertIn("escaped.txt", content)


if __name__ == "__main__":
    unittest.main()
