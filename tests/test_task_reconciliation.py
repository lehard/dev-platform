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
sys.path.insert(0, str(ROOT / "tests"))

import json  # noqa: E402

import _platform_common  # noqa: E402
import finish_task  # noqa: E402
from _platform_config import write_platform_config  # noqa: E402
import managed_task  # noqa: E402
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
        write_platform_config(self.task, workflow_profile="standard")
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
        with mock.patch.object(task_reconciliation, "task_kind", return_value="managed"):
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

    def archived_change_with_evidence(self) -> managed_task.CanonicalProvenance:
        """An archived managed change whose committed evidence proves the current task content."""
        from task_content_identity import review_content_identity

        (self.task / "shared.txt").write_text("base\n" + "\n" * 8 + "tail\n", encoding="utf-8")
        (self.task / "dev-platform").mkdir()
        (self.task / "dev-platform" / "checks.toml").write_text("", encoding="utf-8")
        git("add", "shared.txt", "dev-platform", cwd=self.task); git("commit", "-m", "widen shared", cwd=self.task); git("push", "origin", "agent/task:main", cwd=self.task)
        git("fetch", "origin", cwd=self.task)
        (self.task / "shared.txt").write_text("task\n" + "\n" * 8 + "tail\n", encoding="utf-8")
        change = self.task / "openspec" / "changes" / "archive" / "2026-10-30-demo"
        change.mkdir(parents=True)
        (change / "tasks.md").write_text("- [x] 1.1 demo\n", encoding="utf-8")
        (change / ".managed-task.json").write_text(json.dumps({"change": "demo"}), encoding="utf-8")
        git("add", ".", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        proof = review_content_identity(self.task, "demo")
        (change / "automated-checks.json").write_text(json.dumps({"outcome": "success", "gate_task_content": proof}), encoding="utf-8")
        git("add", ".", cwd=self.task); git("commit", "-m", "record evidence", cwd=self.task)
        return managed_task.CanonicalProvenance("owner/repo#1", "demo", change, "archived")

    def test_stale_committed_evidence_after_the_merge_fails_with_the_refresh_command(self) -> None:
        provenance = self.archived_change_with_evidence()
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base); configure(other)
        (other / "shared.txt").write_text("base\n" + "\n" * 8 + "main tail\n", encoding="utf-8")
        git("commit", "-am", "main touches a task path", cwd=other); git("push", cwd=other)
        with mock.patch.object(managed_task, "resolve_canonical_provenance", return_value=provenance):
            with self.assertRaises(SystemExit) as stopped:
                self.reconcile()
        message = str(stopped.exception)
        self.assertIn("Task reconciliation merged main", message)
        self.assertIn("python3 scripts/select_checks.py --base origin/main --execute --evidence "
                      "openspec/changes/archive/2026-10-30-demo/automated-checks.json", message)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=self.task).returncode, 0)

    def test_committed_evidence_survives_a_main_move_that_touches_no_task_path(self) -> None:
        provenance = self.archived_change_with_evidence()
        self.advance_main()
        with mock.patch.object(managed_task, "resolve_canonical_provenance", return_value=provenance), \
                mock.patch("sys.stdout") as out:
            self.reconcile()
        printed = "".join(call.args[0] for call in out.write.call_args_list)
        self.assertIn("Committed selected-check evidence: current", printed)

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
            mock.patch.object(task_reconciliation, "task_kind", return_value="managed"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(task_reconciliation.publication_state, "find_exact_head_pr", return_value=exact),
            mock.patch.object(task_reconciliation.publication_state, "github_repo_name", return_value="owner/repo"),
        ):
            result = task_reconciliation.reconcile(self.task)

        self.assertEqual(result.state, "ahead")
        self.assertEqual(git("rev-parse", "origin/agent/task", cwd=self.task).stdout.strip(), git("rev-parse", "HEAD", cwd=self.task).stdout.strip())

    def test_issue_97_local_ci_fix_descendant_continues_same_exact_pr_after_main_advance(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        published_head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        # A local CI fix lands on top of the already-published exact PR head.
        (self.task / "task.txt").write_text("task fixed\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "ci fix", cwd=self.task)
        ci_fix_head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        self.advance_main()
        exact = publication_state.ExactHeadPrLookup(
            available=True,
            exact_open={
                "number": 97,
                "url": "https://example.invalid/pr/97",
                "baseRefName": "main",
                "headRepositoryOwner": "owner",
            },
        )
        with (
            mock.patch.object(task_reconciliation, "task_kind", return_value="managed"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(task_reconciliation.publication_state, "find_exact_head_pr", return_value=exact),
            mock.patch.object(task_reconciliation.publication_state, "github_repo_name", return_value="owner/repo"),
        ):
            result = task_reconciliation.reconcile(self.task)

        self.assertEqual(result.state, "ahead")
        head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        # Same branch fast-forwarded to the descendant, then to the reconciled head.
        self.assertEqual(git("rev-parse", "origin/agent/task", cwd=self.task).stdout.strip(), head)
        self.assertEqual(git("merge-base", "--is-ancestor", ci_fix_head, head, cwd=self.task).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", published_head, head, cwd=self.task).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", head, cwd=self.task).returncode, 0)

    def reconcile_armed_pr(self, disable_result: subprocess.CompletedProcess[str], *, still_armed: bool = False) -> mock.Mock:
        """Reconcile a published task whose exact PR is armed; returns the mocked gh call."""
        pr = {"number": 932, "url": "https://example.invalid/pr/932", "baseRefName": "main",
              "headRepositoryOwner": "owner", "autoMergeRequest": {"mergeMethod": "SQUASH"}}
        disarmed = pr if still_armed else {**pr, "autoMergeRequest": None}
        remote_at_disable: list[str] = []

        def lookup(*_args: object) -> publication_state.ExactHeadPrLookup:
            return publication_state.ExactHeadPrLookup(available=True, exact_open=disarmed if remote_at_disable else pr)

        def disable(_command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            remote_at_disable.append(git("ls-remote", "origin", "agent/task", cwd=self.task).stdout.split()[0])
            return disable_result

        gh = mock.Mock(side_effect=disable)
        gh.remote_at_disable = remote_at_disable
        with (
            mock.patch.object(task_reconciliation, "task_kind", return_value="quick"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(task_reconciliation, "run_github_with_retry", gh),
            mock.patch.object(task_reconciliation.publication_state, "find_exact_head_pr", side_effect=lookup),
            mock.patch.object(task_reconciliation.publication_state, "github_repo_name", return_value="owner/repo"),
        ):
            try:
                task_reconciliation.reconcile(self.task)
            except SystemExit as exc:
                gh.refusal = str(exc)
        return gh

    def publish_task_and_advance_main(self) -> str:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        self.advance_main()
        return git("rev-parse", "HEAD", cwd=self.task).stdout.strip()

    def test_armed_pr_is_disarmed_before_the_new_head_is_pushed(self) -> None:
        published = self.publish_task_and_advance_main()

        gh = self.reconcile_armed_pr(subprocess.CompletedProcess([], 0, "", ""))

        self.assertEqual(gh.call_args.args[0], ["gh", "pr", "merge", "932", "--disable-auto"])
        self.assertEqual(gh.remote_at_disable, [published])
        head = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        self.assertNotEqual(head, published)
        self.assertEqual(git("ls-remote", "origin", "agent/task", cwd=self.task).stdout.split()[0], head)

    def test_failed_disarm_refuses_and_pushes_nothing(self) -> None:
        published = self.publish_task_and_advance_main()

        gh = self.reconcile_armed_pr(subprocess.CompletedProcess([], 1, "", "auto-merge busy"))

        self.assertIn("could not be disabled: auto-merge busy", gh.refusal)
        self.assertEqual(git("ls-remote", "origin", "agent/task", cwd=self.task).stdout.split()[0], published)

    def test_auto_merge_still_armed_after_disarm_refuses_and_pushes_nothing(self) -> None:
        published = self.publish_task_and_advance_main()

        gh = self.reconcile_armed_pr(subprocess.CompletedProcess([], 0, "", ""), still_armed=True)

        self.assertIn("still has auto-merge armed", gh.refusal)
        self.assertEqual(git("ls-remote", "origin", "agent/task", cwd=self.task).stdout.split()[0], published)

    def test_local_descendant_push_also_disarms_first(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        published = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        (self.task / "task.txt").write_text("task fixed\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "ci fix", cwd=self.task)

        gh = self.reconcile_armed_pr(subprocess.CompletedProcess([], 0, "", ""))

        self.assertEqual(gh.remote_at_disable, [published])
        self.assertEqual(git("ls-remote", "origin", "agent/task", cwd=self.task).stdout.split()[0],
                         git("rev-parse", "HEAD", cwd=self.task).stdout.strip())

    def test_issue_97_squash_merged_exact_pr_routes_to_terminal_finish_without_new_head(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        before = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        # The remote branch has been deleted after a squash merge.
        run("git", "--git-dir", str(self.remote), "branch", "-D", "agent/task", cwd=self.base, check=False)
        self.advance_main()
        merged = publication_state.ExactHeadPrLookup(
            available=True,
            exact_merged={
                "number": 97,
                "url": "https://example.invalid/pr/97",
                "baseRefName": "main",
                "state": "MERGED",
            },
        )
        with (
            mock.patch.object(task_reconciliation, "task_kind", return_value="managed"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(task_reconciliation.publication_state, "find_exact_head_pr", return_value=merged),
        ):
            with self.assertRaisesRegex(SystemExit, "already merged.*finish_task.py"):
                task_reconciliation.reconcile(self.task)

        self.assertEqual(git("rev-parse", "HEAD", cwd=self.task).stdout.strip(), before)
        self.assertEqual(git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=self.task, check=False).returncode, 1)

    def test_issue_97_diverged_local_head_is_still_refused(self) -> None:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("push", "-u", "origin", "agent/task", cwd=self.task)
        self.advance_main()
        # Remote task branch gains a commit that the local head does not contain.
        remote = self.base / "remote-writer"
        run("git", "clone", str(self.remote), str(remote), cwd=self.base); configure(remote)
        git("switch", "agent/task", cwd=remote)
        (remote / "remote.txt").write_text("changed\n", encoding="utf-8")
        git("add", "remote.txt", cwd=remote); git("commit", "-m", "remote changed task", cwd=remote); git("push", cwd=remote)
        # And the local head also diverges with its own commit.
        (self.task / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=self.task); git("commit", "-m", "local only", cwd=self.task)

        with (
            mock.patch.object(task_reconciliation, "task_kind", return_value="managed"),
            mock.patch.object(task_reconciliation, "github_cli_env", return_value={}),
            mock.patch.object(
                task_reconciliation.publication_state,
                "find_exact_head_pr",
                return_value=publication_state.ExactHeadPrLookup(available=True),
            ),
        ):
            with self.assertRaisesRegex(SystemExit, "remote task branch head differs"):
                task_reconciliation.reconcile(self.task)

    def commit_task_work(self) -> str:
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        return git("rev-parse", "HEAD", cwd=self.task).stdout.strip()

    def test_quick_task_is_classified_and_merges_authoritative_main(self) -> None:
        task_head = self.commit_task_work()
        self.advance_main()

        self.assertEqual(task_reconciliation.task_kind(self.task, "main"), task_reconciliation.TASK_KIND_QUICK)
        result = task_reconciliation.reconcile(self.task)

        self.assertEqual(result.state, "ahead")
        self.assertEqual(git("merge-base", "--is-ancestor", task_head, "HEAD", cwd=self.task).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=self.task).returncode, 0)

    def test_installed_merge_hook_admits_only_the_reconcile_merge_in_a_task_worktree(self) -> None:
        hook = self.task / ".git" / "hooks" / "pre-merge-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_bytes((SCRIPTS / "git_hooks" / "pre-merge-commit").read_bytes())
        hook.chmod(0o755)
        git("config", "core.hooksPath", str(hook.parent), cwd=self.task)
        worktree = self.base / "task-worktree"
        git("worktree", "add", "-b", "agent/worktree-task", str(worktree), cwd=self.task)
        (worktree / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=worktree); git("commit", "-m", "task work", cwd=worktree)
        task_head = git("rev-parse", "HEAD", cwd=worktree).stdout.strip()
        self.advance_main()

        with mock.patch.object(task_reconciliation, "task_kind", return_value=task_reconciliation.TASK_KIND_QUICK):
            result = task_reconciliation.reconcile(worktree)

        self.assertEqual(result.state, "ahead")
        self.assertEqual(git("merge-base", "--is-ancestor", task_head, "HEAD", cwd=worktree).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=worktree).returncode, 0)
        git_dir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", cwd=worktree).stdout.strip())
        self.assertFalse((git_dir / task_reconciliation.RECONCILE_MERGE_INTENT).exists(), "the reconcile intent outlived its merge")

        other = self.base / "other"
        (other / "later.txt").write_text("later\n", encoding="utf-8")
        git("add", "later.txt", cwd=other); git("commit", "-m", "advance main again", cwd=other); git("push", cwd=other)
        git("fetch", "origin", cwd=worktree)
        before = git("rev-parse", "HEAD", cwd=worktree).stdout
        ad_hoc = git("merge", "--no-edit", "origin/main", cwd=worktree, check=False)
        self.assertNotEqual(ad_hoc.returncode, 0)
        self.assertIn("merge commits in task worktrees are blocked", ad_hoc.stderr)
        self.assertEqual(before, git("rev-parse", "HEAD", cwd=worktree).stdout)

    def test_conflicting_reconcile_leaves_no_intent(self) -> None:
        (self.task / "shared.txt").write_text("task side\n", encoding="utf-8")
        git("add", "shared.txt", cwd=self.task); git("commit", "-m", "task edits shared", cwd=self.task)
        self.advance_main("shared.txt", "main side\n")

        with self.assertRaisesRegex(SystemExit, "merge conflicts.*shared.txt"):
            self.reconcile()
        git_dir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", cwd=self.task).stdout.strip())
        self.assertFalse((git_dir / task_reconciliation.RECONCILE_MERGE_INTENT).exists())
        git("merge", "--abort", cwd=self.task)

    def test_quick_task_reconcile_cli_named_by_blockers_works(self) -> None:
        write_platform_config(self.task, workflow_profile="standard", platform_version="1.9.3")
        git("add", ".dev-platform.toml", cwd=self.task); git("commit", "-m", "pin platform version", cwd=self.task)
        task_head = self.commit_task_work()
        self.advance_main()

        result = run("python3", str(SCRIPTS / "finish_task.py"), "--reconcile", cwd=self.task, check=False)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Task reconciliation: quick task.", result.stdout)
        self.assertEqual(finish_task.RECONCILE_COMMAND, task_reconciliation.RECONCILE_COMMAND)
        self.assertEqual(git("merge-base", "--is-ancestor", task_head, "HEAD", cwd=self.task).returncode, 0)
        self.assertEqual(git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=self.task).returncode, 0)

    def test_quick_dirty_task_is_refused_untouched(self) -> None:
        before = self.commit_task_work()
        self.advance_main()
        (self.task / "dirty.txt").write_text("keep\n", encoding="utf-8")

        with self.assertRaisesRegex(SystemExit, "dirty.*automatic stash/reset"):
            task_reconciliation.reconcile(self.task)

        self.assertTrue((self.task / "dirty.txt").is_file())
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.task).stdout.strip(), before)

    def test_managed_lineage_is_classified_managed(self) -> None:
        with mock.patch.object(managed_task, "resolve_canonical_provenance", return_value=object()):
            self.assertEqual(task_reconciliation.task_kind(self.task, "main"), task_reconciliation.TASK_KIND_MANAGED)

    def test_ambiguous_managed_lineage_stops_before_any_merge(self) -> None:
        self.commit_task_work()
        self.advance_main()
        before = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()
        with mock.patch.object(managed_task, "resolve_canonical_provenance", side_effect=managed_task.ManagedTaskError("two lineages")):
            with self.assertRaisesRegex(SystemExit, "cannot determine the task kind: two lineages"):
                task_reconciliation.reconcile(self.task)
        self.assertEqual(git("rev-parse", "HEAD", cwd=self.task).stdout.strip(), before)

    def test_orphan_active_openspec_change_is_not_classified_quick(self) -> None:
        change = self.task / "openspec" / "changes" / "orphan"
        change.mkdir(parents=True)
        (change / "proposal.md").write_text("orphan\n", encoding="utf-8")
        git("add", ".", cwd=self.task); git("commit", "-m", "orphan change", cwd=self.task)

        with self.assertRaisesRegex(SystemExit, "cannot determine the task kind: active OpenSpec change lacks managed-task provenance"):
            task_reconciliation.task_kind(self.task, "main")

    def test_branch_added_managed_provenance_without_state_is_not_classified_quick(self) -> None:
        archived = self.task / "openspec" / "changes" / "archive" / "2026-01-01-change"
        archived.mkdir(parents=True)
        (archived / ".managed-task.json").write_text("{}\n", encoding="utf-8")
        git("add", ".", cwd=self.task); git("commit", "-m", "archived managed change", cwd=self.task)

        with self.assertRaisesRegex(SystemExit, "adds managed OpenSpec provenance without a managed task state record"):
            task_reconciliation.task_kind(self.task, "main")

    def test_branch_archiving_managed_change_without_state_is_not_classified_quick(self) -> None:
        # The active managed package already exists on main; the branch only
        # archives it (a rename), which must still count as added provenance.
        git("switch", "main", cwd=self.task)
        active = self.task / "openspec" / "changes" / "managed-change"
        active.mkdir(parents=True)
        (active / ".managed-task.json").write_text("{}\n", encoding="utf-8")
        git("add", ".", cwd=self.task); git("commit", "-m", "managed change", cwd=self.task); git("push", cwd=self.task)
        git("switch", "agent/task", cwd=self.task); git("merge", "--ff-only", "main", cwd=self.task)
        (self.task / "openspec" / "changes" / "archive").mkdir()
        git("mv", "openspec/changes/managed-change", "openspec/changes/archive/2026-01-01-managed-change", cwd=self.task)
        git("commit", "-m", "archive managed change", cwd=self.task)

        with self.assertRaisesRegex(SystemExit, "adds managed OpenSpec provenance without a managed task state record"):
            task_reconciliation.task_kind(self.task, "main")

    def test_freshness_blockers_name_the_working_reconcile_command(self) -> None:
        write_platform_config(self.task, workflow_profile="standard", platform_version="1.9.3")
        self.commit_task_work()
        self.advance_main()
        git("fetch", "origin", cwd=self.task)
        with (
            mock.patch.object(finish_task, "run_openspec_hygiene", return_value=None),
            mock.patch.object(finish_task, "enforce_scope_gate"),
            mock.patch.object(finish_task, "observe_private_reference_blocker", return_value=None),
        ):
            blockers = dict(finish_task.observe_completion_blockers(
                self.task, self.task, "agent/task", "main", "origin/main", "pr", None
            ))

        self.assertIn("Reconcile before expensive validation: python3 scripts/finish_task.py --reconcile", blockers["task-freshness"])
        self.assertIn("python3 scripts/finish_task.py --reconcile", blockers["branch-base"])
        self.assertNotIn("Rebase", blockers["branch-base"])

    def test_quick_checkpoint_proof_survives_a_merge_only_reconcile_but_not_an_edit(self) -> None:
        import agent_friction
        import task_content_identity

        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task); git("commit", "-m", "task work", cwd=self.task)
        git("fetch", "origin", cwd=self.task)
        with mock.patch.object(task_content_identity, "_declared_generated_at_base", return_value=set()):
            recorded = agent_friction.current_task_content(self.task)
            self.advance_main()
            with mock.patch.object(task_reconciliation, "task_kind", return_value="quick"):
                task_reconciliation.reconcile(self.task)

            merged = agent_friction.current_task_content(self.task)
            self.assertTrue(task_content_identity.equivalent_proofs(self.task, recorded, merged))

            (self.task / "task.txt").write_text("task edited\n", encoding="utf-8")
            git("add", "task.txt", cwd=self.task); git("commit", "-m", "edit", cwd=self.task)
            edited = agent_friction.current_task_content(self.task)
            self.assertFalse(task_content_identity.equivalent_proofs(self.task, recorded, edited))

    def test_read_only_status_detects_advanced_main_without_updating_origin_main(self) -> None:
        write_platform_config(self.task, workflow_profile="standard", platform_version="1.9.3")
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
