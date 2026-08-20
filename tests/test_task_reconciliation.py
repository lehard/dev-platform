from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import publication_state  # noqa: E402
import task_reconciliation  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "reconcile@example.invalid", cwd=root)
    git("config", "user.name", "Reconciliation Test", cwd=root)


class TaskReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"
        run("git", "init", "-b", "main", str(self.seed), cwd=self.base)
        configure(self.seed)
        (self.seed / "shared.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.seed); git("commit", "-m", "base", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed); git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.task = self.base / "task"
        run("git", "clone", str(self.remote), str(self.task), cwd=self.base); configure(self.task)
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\npublish_mode = "pr"\n', encoding="utf-8"
        )
        git("add", ".dev-platform.toml", cwd=self.task); git("commit", "-m", "configure platform", cwd=self.task); git("push", cwd=self.task)
        git("switch", "-c", "agent/task", cwd=self.task)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def advance_main(self, filename: str = "main.txt", content: str = "advanced\n") -> None:
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base); configure(other)
        (other / filename).write_text(content, encoding="utf-8")
        git("add", filename, cwd=other); git("commit", "-m", "advance main", cwd=other); git("push", cwd=other)

    def reconcile(self) -> task_reconciliation.Freshness:
        with mock.patch.object(task_reconciliation, "_require_managed_lineage"):
            return task_reconciliation.reconcile(self.task)

    def test_unpublished_task_merges_authoritative_main_without_rewriting_history(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        task_head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        self.advance_main()

        result = self.reconcile()

        self.assertEqual(result.state, "ahead")
        self.assertEqual(git("merge-base", "--is-ancestor", task_head, "HEAD", cwd=self.task).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=self.task).returncode, 0)

    def test_current_task_is_an_idempotent_no_op(self) -> None:
        before = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()

        result = self.reconcile()

        self.assertEqual(result.state, "equal")
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.task).stdout.strip(), before)

    def test_dirty_task_is_left_untouched(self) -> None:
        self.advance_main()
        (self.task / "dirty.txt").write_text("keep\n", encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "dirty.*automatic stash/reset"):
            self.reconcile()

        self.assertTrue((self.task / "dirty.txt").is_file())

    def test_conflict_reports_repository_relative_paths_and_preserves_merge_state(self) -> None:
        (self.task / "shared.txt").write_text("task\n", encoding="utf-8")
        git("add", "shared.txt", cwd=self.task); git("commit", "-m", "task edit", cwd=self.task)
        self.advance_main("shared.txt", "main\n")

        with self.assertRaisesRegex(SystemExit, "conflicting paths: shared.txt"):
            self.reconcile()

        self.assertIn("UU shared.txt", git("status", "--porcelain", cwd=self.task).stdout)
        with self.assertRaisesRegex(SystemExit, "unfinished merge.*Conflicting paths: shared.txt"):
            self.reconcile()

    def test_remote_branch_with_changed_head_is_refused_before_merge(self) -> None:
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        self.advance_main()
        remote = self.base / "remote-writer"
        run("git", "clone", str(self.remote), str(remote), cwd=self.base); configure(remote)
        git("switch", "agent/task", cwd=remote)
        (remote / "remote.txt").write_text("changed\n", encoding="utf-8")
        git("add", "remote.txt", cwd=remote); git("commit", "-m", "remote changed task", cwd=remote); git("push", cwd=remote)

        with self.assertRaisesRegex(SystemExit, "remote task branch head differs"):
            self.reconcile()

    def test_issue_190_open_exact_pr_is_reconciled_and_remains_fast_forward_pushable(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        self.advance_main()
        exact = publication_state.ExactHeadPrLookup(
            available=True,
            exact_open={
                "number": 190,
                "url": "https://example.invalid/pr/190",
                "baseRefName": "main",
                "headRepositoryOwner": "owner",
            },
        )
        with (
            mock.patch.object(task_reconciliation, "_require_managed_lineage"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(task_reconciliation.publication_state, "find_exact_head_pr", return_value=exact),
            mock.patch.object(task_reconciliation.publication_state, "github_repo_name", return_value="owner/repo"),
        ):
            result = task_reconciliation.reconcile(self.task)

        self.assertEqual(result.state, "ahead")
        self.assertEqual(git("rev-parse", "origin/agent/task", cwd=self.task).stdout.strip(), git("rev-parse", "HEAD", cwd=self.task).stdout.strip())

    def test_read_only_status_detects_advanced_main_without_updating_origin_main(self) -> None:
        observed_before = git("rev-parse", "origin/main", cwd=self.task).stdout.strip()
        self.advance_main()

        payload = task_reconciliation.status_payload(self.task)

        self.assertEqual(payload["task_freshness"], "behind")
        self.assertTrue(payload["reconcile_required"])
        self.assertEqual(git("rev-parse", "origin/main", cwd=self.task).stdout.strip(), observed_before)

    def test_status_reports_ambiguous_managed_provenance_as_bounded_evidence(self) -> None:
        with mock.patch.object(task_reconciliation, "resolve_canonical_provenance", side_effect=task_reconciliation.ManagedTaskError("two canonical task lineages")):
            payload = task_reconciliation.status_payload(self.task)

        self.assertEqual(payload["managed_provenance"], "ambiguous")
        self.assertEqual(payload["provenance_detail"], "two canonical task lineages")


if __name__ == "__main__":
    unittest.main()
