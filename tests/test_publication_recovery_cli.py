from __future__ import annotations

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
    for name in ("_platform_common.py", "integration_state.py", "project_publish.py", "publication_state.py", "task_reconciliation.py", "managed_project_status.py", "finish_task.py", "openspec_lifecycle.py"):
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
        (seed / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
        (seed / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
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
        env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\nexit 1\n')
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
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"OPEN","headRefOid":"{head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "url,number,autoMergeRequest,baseRefName" ]; then printf \'{"url":"https://example.invalid/pr/5","number":5,"baseRefName":"main"}\'; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "[]"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--status", cwd=self.repo, env=env)
        self.assertIn("open_checks_pending", result.stdout)
        self.assertIn("#5", result.stdout)
        log_text = gh_log.read_text(encoding="utf-8") if gh_log.exists() else ""
        self.assertNotIn("create", log_text)
        self.assertNotIn("merge", log_text)
        remote_has_branch = run("git", "ls-remote", "--exit-code", "--heads", "origin", "agent/status-open", cwd=self.repo, check=False)
        self.assertNotEqual(remote_has_branch.returncode, 0, "status must not push the branch")

    def test_status_is_read_only_and_reports_not_applicable_for_project_harness(self) -> None:
        self.make_feature("agent/status-project")
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "light"\nharness_mode = "project"\npublish_mode = "pr"\n',
            encoding="utf-8",
        )
        result = run("python3", "scripts/finish_task.py", "--status", cwd=self.repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("not_applicable", result.stdout)

    def test_status_json_is_sanitized_and_valid(self) -> None:
        self.make_feature("agent/status-json")
        env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\nexit 1\n')
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
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,headRefOid" ]; then printf \'{{"state":"CLOSED","headRefOid":"{head}"}}\'; exit 0; fi\n'
            '  if [ "$5" = "state,mergedAt" ]; then\n'
            f'    remote_head=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null)\n'
            f'    if [ "$remote_head" = "{head}" ]; then echo MERGED; else echo OPEN; fi\n'
            '    exit 0\n'
            '  fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/11"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$3") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("https://example.invalid/pr/11", result.stdout)
        self.assertIn("merged through GitHub", result.stdout)

    # -- Manual PR mode is unaffected by the reconciler --

    def test_manual_pr_mode_publishes_without_attempting_any_merge(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "manual"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "manual mode", cwd=self.repo)
        git("push", cwd=self.repo)
        self.make_feature("agent/manual-mode")
        gh_log = self.base / "gh-manual.log"
        env = self.fake_gh(
            f"echo \"$*\" >> '{gh_log}'\n"
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/21"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("manual review", result.stdout)
        log_text = gh_log.read_text(encoding="utf-8") if gh_log.exists() else ""
        self.assertNotIn("merge", log_text)

    # -- harness_mode=project is unaffected outside of --status --

    def test_harness_mode_project_still_rejects_normal_finish(self) -> None:
        self.make_feature("agent/project-harness")
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "light"\nharness_mode = "project"\npublish_mode = "pr"\n',
            encoding="utf-8",
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
        for proc in procs:
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stderr)
            outputs.append(stdout.strip().splitlines()[-1])
        import json as jsonlib

        results = [jsonlib.loads(line) for line in outputs]
        self.assertEqual(results[0]["url"], results[1]["url"])
        self.assertEqual(results[0]["url"], "https://example.invalid/pr/42")

    def test_two_merge_requests_for_the_same_exact_head_are_convergent(self) -> None:
        # Only one process's `gh pr merge` call actually flips the ref; the
        # other observes MERGED and treats it as success rather than erroring.
        merge_lock = self.base / "merge-lock"
        remote = self.base / "remote-race.git"
        run("git", "init", "--bare", str(remote), cwd=self.base)
        git("remote", "add", "origin", str(remote), cwd=self.root)
        git("push", "-u", "origin", "main", cwd=self.root)
        git("push", "-u", "origin", "agent/race", cwd=self.root)
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$5" = "state,mergedAt" ] || [ "$5" = "state,headRefOid" ]; then\n'
            f'    remote_head=$(git --git-dir "{remote}" rev-parse refs/heads/main 2>/dev/null)\n'
            f'    if [ "$remote_head" = "{self.head}" ]; then echo MERGED; else echo OPEN; fi\n'
            '    exit 0\n'
            '  fi\n'
            '  exit 1\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then\n'
            f'  if mkdir "{merge_lock}" 2>/dev/null; then\n'
            f'    git --git-dir "{remote}" update-ref refs/heads/main "{self.head}"; exit 0\n'
            '  fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        worker = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
            "import os; import project_publish; "
            "root = Path(sys.argv[2]); env = os.environ.copy(); "
            "outcome = project_publish.request_protected_merge(root, env, 'agent/race', 'origin', sys.argv[3]); "
            "print(outcome)"
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
        outcomes = []
        for proc in procs:
            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, stderr)
            outcomes.append(stdout.strip().splitlines()[-1])
        self.assertEqual(outcomes, ["merged", "merged"])
        self.assertEqual(
            run("git", "--git-dir", str(remote), "rev-parse", "refs/heads/main", cwd=self.base).stdout.strip(),
            self.head,
        )


class ExactHeadMergeGuardTests(unittest.TestCase):
    """Direct tests of project_publish.request_protected_merge's fail-closed guard."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git("init", "-b", "main", cwd=self.root)
        configure(self.root)
        (self.root / "f.txt").write_text("base\n", encoding="utf-8")
        git("add", ".", cwd=self.root)
        git("commit", "-m", "base", cwd=self.root)
        git("switch", "-c", "agent/guard", cwd=self.root)
        (self.root / "f.txt").write_text("feature\n", encoding="utf-8")
        git("commit", "-am", "feature", cwd=self.root)
        self.head = git("rev-parse", "agent/guard", cwd=self.root).stdout.strip()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        sys.path.insert(0, str(SCRIPT_SOURCE))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> dict[str, str]:
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env["PATH"]
        return env

    def test_merge_request_fails_closed_when_head_changed_since_validation(self) -> None:
        import project_publish

        changed_head = "1" * 40
        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then echo "rejected" >&2; exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            f'  if [ "$4" = "--json" ] && [ "$5" = "headRefOid" ]; then echo "{changed_head}"; exit 0; fi\n'
            '  if [ "$4" = "--json" ] && [ "$5" = "state,mergedAt" ]; then echo OPEN; exit 0; fi\n'
            '  exit 1\n'
            'fi\n'
            'exit 1'
        )
        with self.assertRaisesRegex(SystemExit, "PR head changed"):
            project_publish.request_protected_merge(self.root, env, "agent/guard", "origin", self.head)

    def test_merge_unavailable_without_head_change_falls_back_gracefully(self) -> None:
        import project_publish

        env = self.fake_gh(
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then echo "auto-merge is not allowed" >&2; exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'exit 1'
        )
        with mock.patch.object(project_publish, "MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS", 0):
            outcome = project_publish.request_protected_merge(self.root, env, "agent/guard", "origin", self.head)
        self.assertEqual(outcome, "unavailable")


if __name__ == "__main__":
    unittest.main()
