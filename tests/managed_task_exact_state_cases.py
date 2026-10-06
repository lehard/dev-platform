from __future__ import annotations

import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from _platform_modules import load_platform_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "template" / "scripts" / "managed_task.py"
sys.path.insert(0, str(SOURCE.parent))
managed_task = load_platform_module("managed_task_exact_state", SOURCE)


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "exact-state@example.invalid", cwd=root)
    git("config", "user.name", "Exact State Test", cwd=root)


def validation_configuration(case: unittest.TestCase, root: Path) -> None:
    (root / '.dev-platform.toml').write_text('[paths]\nworktrees = ".claude/worktrees"\n')
    storage = root / '.claude' / 'worktrees'
    storage.mkdir(parents=True)
    storage.chmod(0o2775)
    with (root / '.git/info/exclude').open('a') as handle:
        handle.write('\n.dev-platform.toml\n.claude/\n')
    # The Mac system-temp volume strips setgid. Isolate that filesystem limit
    # from Git/policy tests, retaining checks for group rwx, gids and ownership.
    if not storage.stat().st_mode & stat.S_ISGID:
        original = managed_task.shared_workspace._expected_bits
        patcher = patch.object(managed_task.shared_workspace, '_expected_bits',
                               side_effect=lambda path: original(path) & ~stat.S_ISGID if path.is_dir() else original(path))
        patcher.start()
        case.addCleanup(patcher.stop)


class ExactTargetContextTests(unittest.TestCase):
    """Real-git coverage for exact_target_context: the primitive that fixes the
    process-issue-#208 class (authoring validated against a stale local checkout
    while claiming a fresher prepared_against SHA)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"
        run("git", "init", "-b", "main", str(self.seed), cwd=self.base)
        configure(self.seed)
        (self.seed / "marker.txt").write_text("original\n", encoding="utf-8")
        git("add", "marker.txt", cwd=self.seed)
        git("commit", "-m", "seed", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.root = self.base / "task"
        run("git", "clone", str(self.remote), str(self.root), cwd=self.base)
        configure(self.root)
        self.seed_sha = git("rev-parse", "HEAD", cwd=self.root).stdout.strip()
        validation_configuration(self, self.root)

    def advance_remote(self, content: str) -> str:
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / "marker.txt").write_text(content, encoding="utf-8")
        git("add", "marker.txt", cwd=other)
        git("commit", "-m", "advance", cwd=other)
        git("push", cwd=other)
        return git("rev-parse", "HEAD", cwd=other).stdout.strip()

    def test_aligned_checkout_observes_the_exact_fetched_revision(self) -> None:
        with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
            self.assertEqual((worktree / "marker.txt").read_text(encoding="utf-8"), "original\n")
        self.assertFalse(worktree.exists())

    def test_system_tmpdir_does_not_choose_validation_worktree_location(self) -> None:
        storage = self.root / '.claude' / 'worktrees'
        external = self.base / 'external-temp'
        external.mkdir()
        with patch.object(managed_task.tempfile, 'tempdir', str(external)):
            with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
                self.assertTrue(worktree.is_relative_to(storage.resolve()), str(worktree))
                self.assertEqual(git('rev-parse', 'HEAD', cwd=worktree).stdout.strip(), self.seed_sha)
        self.assertEqual(list(storage.iterdir()), [])

    def install_admission_hook(self, *, reject: bool = False) -> None:
        policy = {
            'checkout': str(self.root.resolve()), 'workspace_roots': [str(self.base.resolve())],
            'origin': str(self.remote),
        }
        hook = self.root / '.git' / 'hooks' / 'post-checkout'
        code = ('import json; from pathlib import Path; import local_workspace; '
                f'local_workspace.checkout(Path.cwd(), json.loads({json.dumps(policy)!r})); '
                + ('raise SystemExit("deliberate admission hook failure")' if reject else 'print("policy-admitted")'))
        hook.write_text('#!/bin/sh\n' + f'PYTHONPATH={shlex.quote(str(SOURCE.parent))} '
                        f'exec {shlex.quote(sys.executable)} -c {shlex.quote(code)}\n')
        hook.chmod(0o755)

    def test_302_316_real_policy_rejects_system_temp_and_admits_helper_storage(self) -> None:
        self.install_admission_hook()
        with tempfile.TemporaryDirectory() as external:
            old_worktree = Path(external) / 'old-validation'
            old = git('worktree', 'add', '--detach', str(old_worktree), self.seed_sha, cwd=self.root, check=False)
            self.assertNotEqual(old.returncode, 0)
            self.assertIn('outside reviewed workspace', old.stderr)
            git('worktree', 'remove', '--force', str(old_worktree), cwd=self.root)
            with patch.object(managed_task.tempfile, 'tempdir', external):
                with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
                    self.assertTrue(worktree.is_relative_to(self.root.resolve()))
                    self.assertEqual(git('rev-parse', 'HEAD', cwd=worktree).stdout.strip(), self.seed_sha)
        self.assertEqual(git('worktree', 'list', '--porcelain', cwd=self.root).stdout.count('worktree '), 1)
        self.assertEqual(list((self.root / '.claude/worktrees').iterdir()), [])

    def test_failed_checkout_hook_registration_is_cleaned(self) -> None:
        self.install_admission_hook(reject=True)
        with self.assertRaisesRegex(managed_task.ManagedTaskError, 'deliberate admission hook failure'):
            with managed_task.exact_target_context(self.root, self.seed_sha):
                self.fail('validation must not start')
        self.assertEqual(git('worktree', 'list', '--porcelain', cwd=self.root).stdout.count('worktree '), 1)
        self.assertEqual(list((self.root / '.claude/worktrees').iterdir()), [])

    def test_keyboard_interrupt_cleans_helper(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
                directory = worktree.parent
                raise KeyboardInterrupt()
        self.assertFalse(directory.exists())
        self.assertEqual(git('worktree', 'list', '--porcelain', cwd=self.root).stdout.count('worktree '), 1)

    def test_failed_reference_transaction_registration_is_cleaned(self) -> None:
        hook = self.root / '.git/hooks/reference-transaction'
        hook.write_text('#!/bin/sh\nif [ "$1" = prepared ]; then\n  echo deliberate-ref-admission-failure >&2\n  exit 1\nfi\n')
        hook.chmod(0o755)
        with self.assertRaisesRegex(managed_task.ManagedTaskError, 'deliberate-ref-admission-failure'):
            with managed_task.exact_target_context(self.root, self.seed_sha):
                self.fail('validation must not start')
        self.assertEqual(git('worktree', 'list', '--porcelain', cwd=self.root).stdout.count('worktree '), 1)
        self.assertEqual(list((self.root / '.claude/worktrees').iterdir()), [])

    def test_killed_owner_can_be_recovered_idempotently(self) -> None:
        code = '''import sys, stat
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import managed_task
storage = Path(sys.argv[2]) / '.claude/worktrees'
if not storage.stat().st_mode & stat.S_ISGID:
    original = managed_task.shared_workspace._expected_bits
    managed_task.shared_workspace._expected_bits = lambda path: original(path) & ~stat.S_ISGID if path.is_dir() else original(path)
with managed_task.exact_target_context(Path(sys.argv[2]), sys.argv[3]) as worktree:
    print(worktree.parent, flush=True)
    sys.stdin.read()
'''
        child = subprocess.Popen([sys.executable, '-c', code, str(SOURCE.parent), str(self.root), self.seed_sha],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            directory_text = child.stdout.readline().strip()
            self.assertTrue(directory_text)
            directory = Path(directory_text)
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'live owner'):
                managed_task.cleanup_validation_context(self.root, directory)
            child.kill()
            child.wait(timeout=10)
            managed_task.cleanup_validation_context(self.root, directory)
            managed_task.cleanup_validation_context(self.root, directory)
            self.assertFalse(directory.exists())
            self.assertEqual(git('worktree', 'list', '--porcelain', cwd=self.root).stdout.count('worktree '), 1)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()

    def test_cleanup_error_is_explicit_and_original_failure_remains_chained(self) -> None:
        real_git = managed_task.run_git
        def fail_remove(args, **kwargs):
            if args[:2] == ['worktree', 'remove']:
                return subprocess.CompletedProcess(args, 1, '', 'deliberate removal failure')
            return real_git(args, **kwargs)
        with patch.object(managed_task, 'run_git', side_effect=fail_remove):
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'deliberate removal failure') as raised:
                with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
                    raise RuntimeError('original validation failure')
        self.assertIn('cleanup-validation', str(raised.exception))
        self.assertIsInstance(raised.exception.__cause__.__context__, RuntimeError)
        managed_task.cleanup_validation_context(self.root, worktree.parent, creating_process=True)
        managed_task.cleanup_validation_context(self.root, worktree.parent, creating_process=True)

    def test_cleanup_rejects_live_owner_changed_head_and_symlink(self) -> None:
        with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'live owner'):
                managed_task.cleanup_validation_context(self.root, worktree.parent)
            link = self.root / '.claude/worktrees/dev-platform-authoring-validate-link'
            link.symlink_to(worktree.parent, target_is_directory=True)
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'exact helper storage'):
                managed_task.cleanup_validation_context(self.root, link, creating_process=True)
            link.unlink()
            receipt_path = worktree.parent / managed_task.VALIDATION_RECEIPT
            original = receipt_path.read_text()
            receipt = json.loads(original)
            receipt['sha'] = 'e' * 40
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'Git identity mismatch'):
                managed_task.cleanup_validation_context(self.root, worktree.parent, creating_process=True)
            receipt_path.write_text(original)

    def test_missing_invalid_or_symlink_storage_fails_before_git_add(self) -> None:
        config = self.root / '.dev-platform.toml'
        for text in ('[paths]\n', '[paths]\nworktrees="../outside"\n', '[paths]\nworktrees=""\n'):
            config.write_text(text)
            with patch.object(managed_task, 'run_git', wraps=managed_task.run_git) as observed:
                with self.assertRaisesRegex(managed_task.ManagedTaskError, 'validation storage'):
                    with managed_task.exact_target_context(self.root, self.seed_sha):
                        self.fail('body must not execute')
                self.assertFalse(any(call.args[0][:2] == ['worktree', 'add'] for call in observed.call_args_list))
        config.write_text('[paths]\nworktrees="linked-storage"\n')
        (self.root / 'linked-storage').symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(managed_task.ManagedTaskError, 'symlink'):
            with managed_task.exact_target_context(self.root, self.seed_sha):
                self.fail('body must not execute')

    def test_recovery_cwd_observation_fails_explicitly(self) -> None:
        with patch.object(managed_task.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(managed_task.ManagedTaskError, 'requires lsof'):
                managed_task.validation_active_cwds()
        with patch.object(managed_task.shutil, 'which', return_value='/usr/sbin/lsof'):
            with patch.object(managed_task.subprocess, 'run', return_value=subprocess.CompletedProcess([], 2, '', 'inspection denied')):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, 'inspection denied'):
                    managed_task.validation_active_cwds()
            with patch.object(managed_task.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'n/observed\n', '')):
                with patch.object(Path, 'resolve', side_effect=OSError('cwd unreadable')):
                    with self.assertRaisesRegex(OSError, 'cwd unreadable'):
                        managed_task.validation_active_cwds()

    def test_cleanup_rejects_foreign_contents_and_active_or_unknown_cwds(self) -> None:
        from types import SimpleNamespace

        with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
            foreign = worktree / 'foreign.txt'
            foreign.write_text('preserve\n')
            original_lstat = Path.lstat
            def observed_lstat(path, *args, **kwargs):
                if path == foreign:
                    return SimpleNamespace(st_uid=os.geteuid() + 1)
                return original_lstat(path, *args, **kwargs)
            with patch.object(Path, 'lstat', observed_lstat):
                with self.assertRaisesRegex(managed_task.ManagedTaskError, 'foreign contents'):
                    managed_task.cleanup_validation_context(self.root, worktree.parent, creating_process=True)
            self.assertTrue(foreign.exists())
            receipt_path = worktree.parent / managed_task.VALIDATION_RECEIPT
            original = receipt_path.read_text()
            exited = subprocess.Popen([sys.executable, '-c', 'pass'])
            exited.wait(timeout=10)
            receipt = json.loads(original)
            receipt['pid'] = exited.pid
            receipt_path.write_text(json.dumps(receipt))
            try:
                with patch.object(managed_task, 'validation_active_cwds', return_value={worktree.parent}):
                    with self.assertRaisesRegex(managed_task.ManagedTaskError, 'active worktree'):
                        managed_task.cleanup_validation_context(self.root, worktree.parent)
                with patch.object(managed_task, 'validation_active_cwds', side_effect=managed_task.ManagedTaskError('cannot inspect active working directories')):
                    with self.assertRaisesRegex(managed_task.ManagedTaskError, 'cannot inspect active'):
                        managed_task.cleanup_validation_context(self.root, worktree.parent)
            finally:
                receipt_path.write_text(original)

    def test_stale_local_checkout_still_observes_the_fetched_target_state(self) -> None:
        advanced_sha = self.advance_remote("advanced\n")
        git("fetch", "origin", cwd=self.root)
        self.assertEqual((self.root / "marker.txt").read_text(encoding="utf-8"), "original\n")
        with managed_task.exact_target_context(self.root, advanced_sha) as worktree:
            self.assertEqual((worktree / "marker.txt").read_text(encoding="utf-8"), "advanced\n")
        self.assertEqual((self.root / "marker.txt").read_text(encoding="utf-8"), "original\n")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.root).stdout.strip(), self.seed_sha)
        self.assertEqual(git("status", "--porcelain", cwd=self.root).stdout, "")

    def test_unreachable_revision_fails_closed_without_leaving_worktree_state(self) -> None:
        bogus = "f" * 40
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "not available"):
            with managed_task.exact_target_context(self.root, bogus):
                self.fail("body must not run for an unreachable revision")
        self.assertEqual(git("worktree", "list", "--porcelain", cwd=self.root).stdout.count("worktree "), 1)

    def test_malformed_sha_fails_closed(self) -> None:
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "40-character Git SHA"):
            with managed_task.exact_target_context(self.root, "not-a-sha"):
                self.fail("body must not run for a malformed sha")

    def test_worktree_and_tmpdir_are_removed_even_when_the_body_raises(self) -> None:
        captured: list[Path] = []
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with managed_task.exact_target_context(self.root, self.seed_sha) as worktree:
                captured.append(worktree)
                raise RuntimeError("boom")
        self.assertTrue(captured)
        self.assertFalse(captured[0].exists())
        self.assertFalse(captured[0].parent.exists())
        self.assertEqual(git("worktree", "list", "--porcelain", cwd=self.root).stdout.count("worktree "), 1)

    def test_root_without_local_git_history_for_the_sha_fails_closed(self) -> None:
        unfetched = self.advance_remote("never-fetched\n")
        with self.assertRaisesRegex(managed_task.ManagedTaskError, "not available"):
            with managed_task.exact_target_context(self.root, unfetched):
                self.fail("body must not run for an unfetched revision")


class ValidateAuthoringBundleExactStateTests(unittest.TestCase):
    """validate_authoring_bundle wired to the real exact_target_context, proving the
    end-to-end #208 fix: authoring validation observes prepared_against, not root's
    possibly-stale working tree."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"
        run("git", "init", "-b", "main", str(self.seed), cwd=self.base)
        configure(self.seed)
        (self.seed / "README.md").write_text("seed\n", encoding="utf-8")
        git("add", "README.md", cwd=self.seed)
        git("commit", "-m", "seed", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.root = self.base / "task"
        run("git", "clone", str(self.remote), str(self.root), cwd=self.base)
        configure(self.root)
        validation_configuration(self, self.root)

    def test_validation_runs_against_the_worktree_checked_out_at_prepared_against(self) -> None:
        from types import SimpleNamespace

        bundle = SimpleNamespace(
            title="Add feature",
            issue_body="body",
            change="add-feature",
            artifacts=("proposal.md", "design.md", "tasks.md", "specs/feature/spec.md"),
            contents={
                "proposal.md": "content", "design.md": "content", "tasks.md": "content",
                "specs/feature/spec.md": "content",
            },
        )
        schema = {
            "artifactPaths": {
                "proposal": {"outputPath": "proposal.md"}, "specs": {"outputPath": "specs/**/*.md"},
                "design": {"outputPath": "design.md"}, "tasks": {"outputPath": "tasks.md"},
            }
        }
        seen_roots: list[Path] = []

        def fake_json(command, cwd, env=None):
            seen_roots.append(Path(cwd))
            self.assertEqual(command[:3], ["openspec", "new", "change"])
            (Path(cwd) / "openspec" / "changes" / bundle.change).mkdir(parents=True)
            return {"change": {"id": bundle.change}}

        def fake_validate_change(cwd, change):
            seen_roots.append(Path(cwd))

        target_main = managed_task.target_main(self.root)
        with (
            patch.object(managed_task, "run_json", side_effect=fake_json),
            patch.object(managed_task, "openspec_status", return_value=schema),
            patch.object(managed_task, "validate_change", side_effect=fake_validate_change),
            patch.object(managed_task.shutil, "which", return_value="/usr/bin/openspec"),
        ):
            managed_task.validate_authoring_bundle(self.root, bundle, "lehard/dev-platform", target_main)

        self.assertTrue(seen_roots)
        for observed in seen_roots:
            self.assertNotEqual(observed, self.root)
        self.assertFalse((self.root / "openspec").exists())

    def test_unreachable_prepared_against_fails_closed_before_any_openspec_call(self) -> None:
        from types import SimpleNamespace

        bundle = SimpleNamespace(
            title="Add feature", issue_body="body", change="add-feature",
            artifacts=("proposal.md",), contents={"proposal.md": "content"},
        )
        with (
            patch.object(managed_task, "run_json") as run_json,
            patch.object(managed_task.shutil, "which", return_value="/usr/bin/openspec"),
        ):
            with self.assertRaisesRegex(managed_task.ManagedTaskError, "not available"):
                managed_task.validate_authoring_bundle(self.root, bundle, "lehard/dev-platform", "f" * 40)
        run_json.assert_not_called()
