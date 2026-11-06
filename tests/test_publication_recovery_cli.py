from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_SOURCE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _platform_config import write_platform_config  # noqa: E402
from _concurrent_lifecycle import communicate_within_deadline, wait_for_readiness  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check, env=env)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(repo: Path) -> None:
    git("config", "user.email", "test@example.com", cwd=repo)
    git("config", "user.name", "Publication Recovery Test", cwd=repo)


def install_scripts(repo: Path) -> None:
    target = repo / "scripts"
    target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "shared_workspace.py", "local_workspace.py", "agent_board.py", "delegation_containment.py", "integration_state.py", "project_publish.py", "publication_state.py", "task_reconciliation.py", "lifecycle_preflight.py", "managed_project_status.py", "finish_task.py", "worktree_cleanup.py", "openspec_lifecycle.py", "requirement_integration.py", "managed_task.py", "managed_work_identity.py", "private_lineage.py", "start_tier_routing.py", "independent_review.py", "task_content_identity.py"):
        shutil.copy2(SCRIPT_SOURCE / name, target / name)


def bypass_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEV_PLATFORM_ALLOW_NO_CHECKS"] = "1"
    return env


class PublicationRecoveryCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        seed = self.base / "seed"
        run("git", "init", "-b", "main", str(seed), cwd=self.base)
        configure(seed)
        install_scripts(seed)
        (seed / "README.md").write_text("seed\n", encoding="utf-8")
        (seed / ".gitignore").write_text(".claude/\n__pycache__/\n*.py[cod]\n", encoding="utf-8")
        write_platform_config(seed, workflow_profile="standard", capabilities={"agent_board": False})
        git("add", ".", cwd=seed)
        git("commit", "-m", "seed", cwd=seed)
        git("remote", "add", "origin", str(self.remote), cwd=seed)
        git("push", "-u", "origin", "main", cwd=seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.repo = self.base / "repo"
        run("git", "clone", str(self.remote), str(self.repo), cwd=self.base)
        configure(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> dict[str, str]:
        fake_bin = self.base / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        gh = fake_bin / "gh"
        gh.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        gh.chmod(0o755)
        env = bypass_env()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        env["FAKE_REMOTE"] = str(self.remote)
        return env

    def make_feature(self, branch: str, *, base: str = "main") -> str:
        git("switch", "-c", branch, base, cwd=self.repo)
        (self.repo / "feature.txt").write_text(branch + "\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", branch, cwd=self.repo)
        return git("rev-parse", branch, cwd=self.repo).stdout.strip()

    def advance_remote_main(self, filename: str = "advance.txt") -> None:
        other = self.base / "other-clone"
        if other.exists():
            shutil.rmtree(other)
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / filename).write_text("advance\n", encoding="utf-8")
        git("add", filename, cwd=other)
        git("commit", "-m", "advance main", cwd=other)
        git("push", "origin", "HEAD:main", cwd=other)

    # -- GitHub unavailable: fails closed without any local-main or remote mutation --

    def test_github_unavailable_fails_closed_before_any_push(self) -> None:
        self.make_feature("agent/no-auth")
        env = bypass_env()
        env["PATH"] = "/usr/bin:/bin"  # no fake gh on PATH, and real gh (if any) will fail auth
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        remote_has_branch = run(
            "git", "ls-remote", "--exit-code", "--heads", "origin", "agent/no-auth", cwd=self.repo, check=False
        )
        self.assertNotEqual(remote_has_branch.returncode, 0, "feature branch must not reach origin before GitHub auth is validated")
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), git("rev-parse", "origin/main", cwd=self.repo).stdout.strip())

    # -- --status is strictly read-only across every publication state --

    def test_status_makes_zero_mutations_when_not_yet_published(self) -> None:
        self.make_feature("agent/status-fresh")
        before_head = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then echo "[]"; exit 0; fi\n'
            'exit 1\n'
        )
        result = run("python3", "scripts/finish_task.py", "--status", cwd=self.repo, env=env)
        self.assertIn("not_published", result.stdout)
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), before_head)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "agent/status-fresh")
        remote_has_branch = run("git", "ls-remote", "--exit-code", "--heads", "origin", "agent/status-fresh", cwd=self.repo, check=False)
        self.assertNotEqual(remote_has_branch.returncode, 0)

    def test_status_makes_zero_mutations_when_pr_open_and_checks_pending(self) -> None:
        head = self.make_feature("agent/status-open")
        gh_log = self.base / "gh-status-open.log"
        env = self.fake_gh(
            f"echo \"$*\" >> '{gh_log}'\n"
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  printf \'[{{"number":5,"url":"https://example.invalid/pr/5","state":"OPEN","headRefOid":"{head}","baseRefName":"main","headRefName":"agent/status-open"}}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--status", cwd=self.repo, env=env)
        self.assertIn("open_checks_pending", result.stdout)
        self.assertIn("#5", result.stdout)
        log_text = gh_log.read_text(encoding="utf-8") if gh_log.exists() else ""
        self.assertNotIn("create", log_text)
        self.assertNotIn("pr merge", log_text)
        remote_has_branch = run("git", "ls-remote", "--exit-code", "--heads", "origin", "agent/status-open", cwd=self.repo, check=False)
        self.assertNotEqual(remote_has_branch.returncode, 0, "status must not push the branch")

    def test_status_is_read_only_and_reports_not_applicable_for_project_harness(self) -> None:
        self.make_feature("agent/status-project")
        write_platform_config(
            self.repo, workflow_profile="light", harness_mode="project", protected_main=False, pr_merge_mode="manual", capabilities={"agent_board": False}
        )
        result = run("python3", "scripts/finish_task.py", "--status", cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("not_applicable", result.stdout)

    def test_status_json_is_sanitized_and_valid(self) -> None:
        self.make_feature("agent/status-json")
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then echo "[]"; exit 0; fi\n'
            'exit 1\n'
        )
        result = run("python3", "scripts/finish_task.py", "--status", "--json", cwd=self.repo, env=env)
        import json as jsonlib

        payload = jsonlib.loads(result.stdout)
        self.assertEqual(payload["status"], "not_published")
        blob = result.stdout
        for forbidden in ("GH_TOKEN", "GITHUB_TOKEN", "password"):
            self.assertNotIn(forbidden, blob)

    # -- Recovery is checked before first-publication stale-base rejection --

    def test_existing_exact_head_pr_requires_reconciliation_after_base_advances(self) -> None:
        head = self.make_feature("agent/base-advances")
        git("push", "-u", "origin", "agent/base-advances", cwd=self.repo)
        self.advance_remote_main()
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/7","number":7,"baseRefName":"main"}\'; exit 0; fi\n'
            '  if [ "$5" = "state,mergedAt" ]; then\n'
            f'    remote_head=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null)\n'
            f'    if [ "$remote_head" = "{head}" ]; then echo MERGED; else echo OPEN; fi\n'
            '    exit 0\n'
            '  fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$3") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reconcile before expensive validation", result.stdout + result.stderr)
        self.assertNotIn("Resuming existing exact-head PR", result.stdout)

    def test_new_unpublished_stale_branch_is_still_rejected(self) -> None:
        self.make_feature("agent/never-published-stale")
        self.advance_remote_main()
        env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\nexit 1\n')
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Reconcile before expensive validation", result.stdout + result.stderr)

    # -- Closed-unmerged PR does not block a fresh publication --

    def test_closed_unmerged_pr_does_not_block_new_publication(self) -> None:
        head = self.make_feature("agent/reopen")
        created = self.base / "reopen-created"
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  if [ -d "{created}" ]; then printf \'[{{"number":11,"url":"https://example.invalid/pr/11","state":"OPEN","headRefOid":"{head}","baseRefName":"main","headRefName":"agent/reopen"}}]\'; else printf \'[{{"number":10,"url":"https://example.invalid/pr/10","state":"CLOSED","headRefOid":"{head}","baseRefName":"main","headRefName":"agent/reopen"}}]\'; fi; exit 0\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  remote_head=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null); if [ "$remote_head" = "{head}" ]; then printf \'{{"state":"MERGED","headRefOid":"{head}","baseRefName":"main"}}\'; else printf \'{{"state":"OPEN","headRefOid":"{head}","baseRefName":"main"}}\'; fi; exit 0\n'
            'fi\n'
            f'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then mkdir "{created}"; echo "https://example.invalid/pr/11"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            f'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "{head}" || exit 1; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("https://example.invalid/pr/11", result.stdout)
        self.assertIn("merged through GitHub", result.stdout)

    # -- Manual PR mode is unaffected by the reconciler --

    def test_manual_pr_mode_publishes_without_attempting_any_merge(self) -> None:
        write_platform_config(self.repo, workflow_profile="standard", pr_merge_mode="manual", capabilities={"agent_board": False})
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "manual mode", cwd=self.repo)
        git("push", cwd=self.repo)
        head = self.make_feature("agent/manual-mode")
        gh_log = self.base / "gh-manual.log"
        created = self.base / "manual-created"
        env = self.fake_gh(
            f"echo \"$*\" >> '{gh_log}'\n"
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  if [ -d "{created}" ]; then printf \'[{{"number":21,"url":"https://example.invalid/pr/21","state":"OPEN","headRefOid":"{head}","baseRefName":"main","headRefName":"agent/manual-mode"}}]\'; else echo "[]"; fi; exit 0\n'
            'fi\n'
            f'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then mkdir "{created}"; echo "https://example.invalid/pr/21"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("manual review", result.stdout)
        log_text = gh_log.read_text(encoding="utf-8") if gh_log.exists() else ""
        self.assertNotIn("pr merge", log_text)

    # -- harness_mode=project is unaffected outside of --status --

    def test_harness_mode_project_still_rejects_normal_finish(self) -> None:
        self.make_feature("agent/project-harness")
        write_platform_config(
            self.repo, workflow_profile="light", harness_mode="project", protected_main=False, pr_merge_mode="manual", capabilities={"agent_board": False}
        )
        result = run("python3", "scripts/finish_task.py", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("harness_mode=project", result.stdout + result.stderr)


class PublicationRecoveryConcurrencyTests(unittest.TestCase):
    """Exercise project_publish.py's create-race and merge-race convergence directly."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        run("git", "init", "-b", "main", str(self.root), cwd=self.base)
        configure(self.root)
        (self.root / "f.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.root)
        git("commit", "-m", "base", cwd=self.root)
        git("switch", "-c", "agent/race", cwd=self.root)
        (self.root / "f.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=self.root)
        self.head = git("rev-parse", "agent/race", cwd=self.root).stdout.strip()
        self.bin = self.base / "bin"
        self.bin.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> dict[str, str]:
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return env

    def test_two_publishers_creating_the_same_exact_pr_converge_on_one(self) -> None:
        # Neither publisher observes an existing PR; the first `pr create` wins
        # an atomic `mkdir` race, the loser's create fails and it must re-query
        # and reuse the winner's PR rather than producing a duplicate.
        marker = self.base / "created-lock"
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            f'  if [ -d "{marker}" ]; then printf \'[{{"number":42,"url":"https://example.invalid/pr/42","state":"OPEN","headRefOid":"{self.head}","baseRefName":"main","headRefName":"agent/race"}}]\'; else printf "[]"; fi; exit 0\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then\n'
            f'    if [ -d "{marker}" ]; then printf \'{{"state":"OPEN","headRefOid":"{self.head}"}}\'; exit 0; fi\n'
            '    exit 1\n'
            '  fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/42","number":42,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then\n'
            f'  if mkdir "{marker}" 2>/dev/null; then echo "https://example.invalid/pr/42"; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        worker = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "import os, json; import project_publish; "
            "root = Path(sys.argv[2]); env = os.environ.copy(); "
            "pr = project_publish.ensure_pr(root, env, 'agent/race', 'main', 'title', 'body', sys.argv[3]); "
            "print(json.dumps({'number': pr.number, 'url': pr.url}))"
        )
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", worker, str(SCRIPT_SOURCE), str(self.root), self.head],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(2)
        ]
        outputs = []
        for index, proc in enumerate(procs):
            stdout, stderr = communicate_within_deadline(proc, description=f"pr-create worker {index}")
            self.assertEqual(proc.returncode, 0, stderr)
            outputs.append(stdout.strip().splitlines()[-1])
        import json as jsonlib

        results = [jsonlib.loads(line) for line in outputs]
        self.assertEqual(results[0]["url"], results[1]["url"])
        self.assertEqual(results[0]["url"], "https://example.invalid/pr/42")

class ProtectedMergeRequestTests(unittest.TestCase):
    """project_publish.request_protected_merge: one exact-head request, explicit refusals, no fallback."""

    HEAD = "a" * 40
    MERGE = ["gh", "pr", "merge", "8", "--auto", "--squash", "--match-head-commit", HEAD]

    def setUp(self) -> None:
        import project_publish
        import publication_state

        self.publish = project_publish
        self.state = publication_state.RequiredCheckState
        self.pr = project_publish.PrRef(8, "https://example.invalid/pr/8")

    def request(self, state, *, merge_exit: int = 0, stderr: str = "", wait_error: SystemExit | None = None):
        """Run one merge request; return the recorded gh commands, the merge wait and the branch cleanup."""
        done = subprocess.CompletedProcess([], merge_exit, "", stderr)
        with mock.patch.object(self.publish, "required_check_state_for_ref", return_value=state) as checks, \
                mock.patch.object(self.publish.subprocess, "run", return_value=done) as run, \
                mock.patch.object(self.publish, "wait_for_merge_outcome", side_effect=wait_error) as wait, \
                mock.patch.object(self.publish, "delete_remote_branch") as cleanup:
            try:
                self.publish.request_protected_merge(Path("/unused"), {}, "agent/guard", self.pr, "origin", self.HEAD,
                                                     timeout_seconds=3600.0)
            finally:
                self.calls = [call.args[0] for call in run.call_args_list]
                self.wait, self.cleanup = wait, cleanup
        checks.assert_called_once_with(Path("/unused"), {}, self.pr.ref, self.HEAD)

    def test_passed_or_pending_checks_make_one_auto_merge_request_for_the_exact_head(self) -> None:
        for kind in ("passed", "pending"):
            with self.subTest(kind=kind):
                self.request(self.state(kind))
                self.assertEqual(self.calls, [self.MERGE])
                self.wait.assert_called_once_with(Path("/unused"), {}, self.pr, self.HEAD, timeout_seconds=3600.0)
                self.cleanup.assert_called_once_with(Path("/unused"), "origin", "agent/guard")

    def test_no_required_checks_is_a_refusal_not_a_pass(self) -> None:
        with self.assertRaisesRegex(SystemExit, "no required checks.*nothing would gate the merge.*pr_merge_mode=manual"):
            self.request(self.state("not_registered", detail="no required check is attached"))
        self.assertEqual(self.calls, [])
        self.wait.assert_not_called()

    def test_failed_or_unknown_checks_are_refused_before_any_merge_request(self) -> None:
        for state, message in ((self.state("failed", detail="platform-ci failed"), "Required PR checks failed.*platform-ci failed"),
                               (self.state("unknown", detail="gh failed", cause="transport"), r"state is unknown \(transport\): gh failed")):
            with self.subTest(kind=state.kind):
                with self.assertRaisesRegex(SystemExit, message):
                    self.request(state)
                self.assertEqual(self.calls, [])
                self.wait.assert_not_called()

    def test_github_rejection_stops_with_the_reason_and_no_retry_or_fallback(self) -> None:
        with mock.patch.object(self.publish.time, "sleep") as pause:
            with self.assertRaisesRegex(SystemExit, f"GitHub refused auto-merge for exact head {self.HEAD}: auto-merge is not allowed"):
                self.request(self.state("passed"), merge_exit=1, stderr="auto-merge is not allowed")
        self.assertEqual(self.calls, [self.MERGE], "exactly one request, never a different merge mode")
        pause.assert_not_called()
        self.wait.assert_not_called()
        self.cleanup.assert_not_called()

    def test_foreground_wait_and_merge_chain_no_longer_exist(self) -> None:
        for name in ("wait_for_pr_checks", "CHECK_COMPLETION_TIMEOUT_SECONDS", "MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS"):
            self.assertFalse(hasattr(self.publish, name), name)

    def test_a_stop_while_following_the_merge_keeps_the_branch(self) -> None:
        with self.assertRaisesRegex(SystemExit, "platform-ci"):
            self.request(self.state("pending"), wait_error=SystemExit("Required check failed: platform-ci"))
        self.assertEqual(self.calls, [self.MERGE])
        self.cleanup.assert_not_called()

    def test_merge_guard_wraps_only_the_merge_request(self) -> None:
        events: list[str] = []

        @contextlib.contextmanager
        def guard():
            events.append("guard-enter")
            yield
            events.append("guard-exit")

        def run(command, **_kwargs):
            events.append("merge")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.publish, "required_check_state_for_ref",
                               side_effect=lambda *_a: events.append("checks") or self.state("passed")), \
                mock.patch.object(self.publish.subprocess, "run", side_effect=run), \
                mock.patch.object(self.publish, "wait_for_merge_outcome"), \
                mock.patch.object(self.publish, "delete_remote_branch"):
            self.publish.request_protected_merge(Path("/unused"), {}, "agent/guard", self.pr, "origin", self.HEAD,
                                                 timeout_seconds=3600.0, merge_guard=guard)
        self.assertEqual(events, ["checks", "guard-enter", "merge", "guard-exit"])


class MergeOutcomeTests(unittest.TestCase):
    """project_publish.wait_for_merge_outcome: MERGED returns, every other outcome is a named refusal."""

    HEAD = "a" * 40
    OPEN = {"state": "OPEN", "headRefOid": HEAD, "autoMergeRequest": {"enabledBy": "bot"}, "mergeStateStatus": "BLOCKED"}
    MERGED = {**OPEN, "state": "MERGED", "autoMergeRequest": None, "mergeStateStatus": "UNKNOWN"}

    def setUp(self) -> None:
        import project_publish
        import publication_state

        self.publish = project_publish
        self.state = publication_state.RequiredCheckState
        self.pr = project_publish.PrRef(8, "https://example.invalid/pr/8")

    def follow(self, snapshots: list, checks=None, *, clock=None) -> mock.Mock:
        """Run the wait over scripted PR reads; return the sleep mock."""
        reads = [subprocess.CompletedProcess([], 0, json.dumps(item), "") if isinstance(item, dict) else item for item in snapshots]
        with mock.patch.object(self.publish, "run_github_with_retry", side_effect=reads), \
                mock.patch.object(self.publish, "required_check_state_for_ref", return_value=checks or self.state("pending")), \
                mock.patch.object(self.publish.time, "monotonic", side_effect=clock or (lambda: 0.0)), \
                mock.patch.object(self.publish.time, "sleep") as pause:
            self.publish.wait_for_merge_outcome(Path("/unused"), {}, self.pr, self.HEAD, timeout_seconds=3600.0)
        return pause

    def test_green_pr_is_followed_past_the_old_local_timer_to_merged(self) -> None:
        pause = self.follow([self.OPEN, self.OPEN, self.MERGED], self.state("passed"),
                            clock=iter([0.0, 700.0, 1400.0]).__next__)
        self.assertEqual(pause.call_count, 2)

    def test_failed_required_check_stops_naming_the_check(self) -> None:
        with self.assertRaisesRegex(SystemExit, f"Required check failed for head {self.HEAD}: validate"):
            self.follow([self.OPEN], self.state("failed", detail="validate"))

    def test_the_configured_bound_stops_with_the_exact_command_to_continue(self) -> None:
        with self.assertRaisesRegex(SystemExit, r"ci_completion_minutes \(60 min\).*python3 scripts/finish_task\.py --cleanup"):
            self.follow([self.OPEN], clock=iter([0.0, 3600.0]).__next__)

    def test_outcomes_that_can_never_merge_stop_at_once(self) -> None:
        for snapshot, message in (
            ({**self.OPEN, "state": "CLOSED"}, "is CLOSED, not merged"),
            ({**self.OPEN, "mergeStateStatus": "BEHIND"}, "BEHIND against its base.*--reconcile"),
            ({**self.OPEN, "mergeStateStatus": "DIRTY"}, "DIRTY against its base"),
            ({**self.OPEN, "autoMergeRequest": None}, "no longer has auto-merge armed"),
            ({**self.OPEN, "headRefOid": "b" * 40}, "not the validated head"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(SystemExit, message):
                self.follow([snapshot])

    def test_unusable_observations_stop_with_the_command_to_continue(self) -> None:
        unreadable = subprocess.CompletedProcess([], 1, "", "HTTP 502")
        with self.assertRaisesRegex(SystemExit, "HTTP 502.*finish_task.py --cleanup"):
            self.follow([unreadable])
        with self.assertRaisesRegex(SystemExit, "not JSON.*finish_task.py --cleanup"):
            self.follow([subprocess.CompletedProcess([], 0, "<html>", "")])
        with self.assertRaisesRegex(SystemExit, r"state is unknown \(transport\).*finish_task.py --cleanup"):
            self.follow([self.OPEN], self.state("unknown", detail="gh failed", cause="transport"))

    def test_following_drops_the_remote_branch_only_after_merged(self) -> None:
        with mock.patch.object(self.publish, "wait_for_merge_outcome", side_effect=SystemExit("stop")), \
                mock.patch.object(self.publish, "delete_remote_branch") as cleanup, self.assertRaises(SystemExit):
            self.publish.follow_armed_merge(Path("/unused"), {}, "agent/x", self.pr, "origin", self.HEAD, timeout_seconds=1.0)
        cleanup.assert_not_called()


class RemoteBranchCleanupTests(unittest.TestCase):
    def cleanup_output(self, *exits: int) -> str:
        """Run the cleanup over the given ls-remote, push and ls-remote exit codes; return what it printed."""
        import project_publish

        results = [subprocess.CompletedProcess([], code, "", "remote ref does not exist") for code in exits]
        printed = io.StringIO()
        with mock.patch.object(project_publish, "run_git", side_effect=results), contextlib.redirect_stdout(printed):
            project_publish.delete_remote_branch(Path("."), "origin", "agent/task")
        return printed.getvalue()

    def test_a_branch_github_deleted_during_the_race_is_absent_not_a_failure(self) -> None:
        output = self.cleanup_output(0, 1, 2)

        self.assertIn("already absent", output)
        self.assertNotIn("WARNING", output)

    def test_a_branch_that_survives_a_failed_delete_stays_a_warning(self) -> None:
        self.assertIn("WARNING", self.cleanup_output(0, 1, 0))


class BoundedTestDeadlineHelperTests(unittest.TestCase):
    """The shared helper backing the concurrency tests' subprocess waits."""

    def test_completed_helper_returns_its_output(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, "-c", "print('done')"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, _err = communicate_within_deadline(proc, description="fast helper")
        self.assertEqual(out.strip(), "done")
        self.assertEqual(proc.returncode, 0)

    def test_expired_helper_fails_with_process_identity_and_retained_output(self) -> None:
        import _concurrent_lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            readiness = Path(tmp) / "partial-output-ready"
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import pathlib,sys,time; time.sleep(0.4); print('partial', flush=True); pathlib.Path(sys.argv[1]).touch(); time.sleep(30)",
                    str(readiness),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                wait_for_readiness(readiness.exists, proc, description="hung recovery helper")
                with mock.patch.object(_concurrent_lifecycle, "process_deadline_seconds", return_value=0.3):
                    with self.assertRaises(_concurrent_lifecycle.HelperTimeout) as ctx:
                        communicate_within_deadline(proc, description="hung recovery helper")
                message = str(ctx.exception)
                self.assertIn("hung recovery helper", message)
                self.assertIn(f"pid={proc.pid}", message)
                self.assertIn("partial", message)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_operator_override_env_var_changes_the_deadline(self) -> None:
        import _concurrent_lifecycle

        with mock.patch.dict(os.environ, {"DEV_PLATFORM_TEST_PROCESS_TIMEOUT": "7.5"}):
            self.assertEqual(_concurrent_lifecycle.process_deadline_seconds(), 7.5)
        with mock.patch.dict(os.environ, {"DEV_PLATFORM_TEST_PROCESS_TIMEOUT": "not-a-number"}):
            self.assertEqual(
                _concurrent_lifecycle.process_deadline_seconds(),
                _concurrent_lifecycle._DEFAULT_PROCESS_DEADLINE_SECONDS,
            )


if __name__ == "__main__":
    unittest.main()
