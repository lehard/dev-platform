from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "template" / "scripts" / "managed_task.py"
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("managed_task_exact_state", SOURCE)
assert spec and spec.loader
managed_task = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = managed_task
spec.loader.exec_module(managed_task)


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "exact-state@example.invalid", cwd=root)
    git("config", "user.name", "Exact State Test", cwd=root)


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

    def test_stale_local_checkout_still_observes_the_fetched_target_state(self) -> None:
        # Reproduces the #208 class: root's own working tree is unchanged (still "original"),
        # but a fresh fetch surfaces a newer SHA whose content differs.
        advanced_sha = self.advance_remote("advanced\n")
        git("fetch", "origin", cwd=self.root)
        self.assertEqual((self.root / "marker.txt").read_text(encoding="utf-8"), "original\n")

        with managed_task.exact_target_context(self.root, advanced_sha) as worktree:
            self.assertEqual((worktree / "marker.txt").read_text(encoding="utf-8"), "advanced\n")

        # root's own checkout is untouched by validating a different revision.
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
        # A prepared_against SHA that was never fetched into local objects at all.
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


if __name__ == "__main__":
    unittest.main()
