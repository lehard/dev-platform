from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = ROOT / "template" / "scripts"


def run(*args: str, cwd: Path, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check, env=env)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(repo: Path) -> None:
    git("config", "user.email", "test@example.com", cwd=repo)
    git("config", "user.name", "Platform Test", cwd=repo)


def install_scripts(repo: Path, profile: str = "light", publish: str = "direct") -> None:
    target = repo / "scripts"
    target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "project_sync.py", "project_publish.py", "finish_task.py", "openspec_lifecycle.py"):
        shutil.copy2(SCRIPT_SOURCE / name, target / name)
    (repo / ".dev-platform.toml").write_text(
        f'main_branch = "main"\nworkflow_profile = "{profile}"\nprotected_main = false\npublish_mode = "{publish}"\npr_merge_mode = "manual"\n',
        encoding="utf-8",
    )


class GitLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"
        run("git", "init", "-b", "main", str(self.seed), cwd=self.base)
        configure(self.seed)
        (self.seed / "README.md").write_text("seed\n", encoding="utf-8")
        install_scripts(self.seed)
        (self.seed / ".gitignore").write_text(".claude/\n__pycache__/\n*.py[cod]\n", encoding="utf-8")
        git("add", ".", cwd=self.seed)
        git("commit", "-m", "seed platform", cwd=self.seed)
        git("remote", "add", "origin", str(self.remote), cwd=self.seed)
        git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.repo = self.base / "repo"
        run("git", "clone", str(self.remote), str(self.repo), cwd=self.base)
        configure(self.repo)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def fake_gh(self, body: str) -> tuple[Path, dict[str, str]]:
        fake_bin = self.base / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        fake_gh = fake_bin / "gh"
        fake_gh.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        fake_gh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        env["FAKE_REMOTE"] = str(self.remote)
        return fake_gh, env

    def test_sync_fast_forwards_behind_main(self) -> None:
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / "remote.txt").write_text("new\n", encoding="utf-8")
        git("add", "remote.txt", cwd=other)
        git("commit", "-m", "remote", cwd=other)
        git("push", cwd=other)
        result = run("python3", "scripts/project_sync.py", cwd=self.repo)
        self.assertIn("Fast-forwarded", result.stdout)
        self.assertTrue((self.repo / "remote.txt").exists())

    def test_sync_refuses_local_ahead(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=self.repo)
        git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_sync.py", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ahead", result.stderr + result.stdout)

    def test_direct_publish_pushes_fast_forward(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=self.repo)
        git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo)
        self.assertIn("Published main", result.stdout)
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        self.assertEqual(remote_sha, local_sha)

    def test_standard_direct_finish_integrates_and_pushes_when_unprotected(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = false\npublish_mode = "direct"\npr_merge_mode = "manual"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "standard profile", cwd=self.repo)
        git("push", cwd=self.repo)
        git("switch", "-c", "agent/test", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature", cwd=self.repo)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo)
        self.assertIn("Integrated agent/test -> main", result.stdout)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        self.assertEqual(remote_sha, local_sha)

    def test_standard_manual_pr_finish_returns_to_main(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "manual"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "pr profile", cwd=self.repo)
        git("push", cwd=self.repo)
        git("switch", "-c", "agent/pr-test", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature pr", cwd=self.repo)
        _, env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/1"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("manual review", result.stdout.lower())
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        self.assertIsNotNone(run("git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/agent/pr-test", cwd=self.base).stdout.strip())

    def test_protected_auto_pr_waits_merges_remotely_then_syncs_local_main(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "protected pr profile", cwd=self.repo)
        git("push", cwd=self.repo)
        git("switch", "-c", "agent/auto", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature auto", cwd=self.repo)
        _, env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/2"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "platform-ci pass"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then '
            'sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$3") || exit 1; '
            'git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; '
            'git --git-dir "$FAKE_REMOTE" update-ref -d "refs/heads/$3"; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("merged through GitHub", result.stdout)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        self.assertTrue((self.repo / "feature.txt").exists())
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        self.assertEqual(remote_sha, local_sha)

    def test_failed_pr_checks_leave_local_main_unchanged(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "protected pr profile", cwd=self.repo)
        git("push", cwd=self.repo)
        before_main = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        before_remote = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        git("switch", "-c", "agent/fail-check", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature fail", cwd=self.repo)
        _, env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/3"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "platform-ci fail" >&2; exit 1; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local main was not changed", result.stderr + result.stdout)
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), before_main)
        self.assertEqual(run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(), before_remote)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "agent/fail-check")

    def test_protected_direct_finish_fails_before_local_integration(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "direct"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "bad protected direct profile", cwd=self.repo)
        git("push", cwd=self.repo)
        before_main = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        before_remote = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        git("switch", "-c", "agent/protected-direct", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature", cwd=self.repo)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected_main=true", result.stderr + result.stdout)
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), before_main)
        self.assertEqual(run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(), before_remote)

    def test_missing_gh_auth_fails_before_feature_branch_push(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "protected pr profile", cwd=self.repo)
        git("push", cwd=self.repo)
        git("switch", "-c", "agent/no-auth", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature no auth", cwd=self.repo)
        _, env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 1; fi\nexit 1')
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("authenticated GitHub CLI", result.stderr + result.stdout)
        remote_feature = run("git", "--git-dir", str(self.remote), "rev-parse", "--verify", "refs/heads/agent/no-auth", cwd=self.base, check=False)
        self.assertNotEqual(remote_feature.returncode, 0)

    def test_direct_project_publish_pushes_branch_before_reporting_missing_pr_auth(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nprotected_main = true\npublish_mode = "pr"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "protected pr profile", cwd=self.repo)
        git("push", cwd=self.repo)
        git("switch", "-c", "agent/push-first", cwd=self.repo)
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", "feature push first", cwd=self.repo)
        _, env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 1; fi\nexit 1')
        result = run("python3", "scripts/project_publish.py", "--mode", "pr", cwd=self.repo, env=env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already pushed", result.stderr + result.stdout)
        remote_feature = run("git", "--git-dir", str(self.remote), "rev-parse", "--verify", "refs/heads/agent/push-first", cwd=self.base, check=False)
        self.assertEqual(remote_feature.returncode, 0)

    def test_direct_publish_refuses_divergence(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8")
        git("add", "local.txt", cwd=self.repo)
        git("commit", "-m", "local", cwd=self.repo)
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / "remote.txt").write_text("remote\n", encoding="utf-8")
        git("add", "remote.txt", cwd=other)
        git("commit", "-m", "remote", cwd=other)
        git("push", cwd=other)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diverged", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
