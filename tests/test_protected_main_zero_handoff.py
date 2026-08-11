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
    git("config", "user.name", "Protected Main Test", cwd=repo)


def install_scripts(repo: Path) -> None:
    target = repo / "scripts"
    target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "project_publish.py", "publication_state.py", "managed_project_status.py", "finish_task.py", "openspec_lifecycle.py"):
        shutil.copy2(SCRIPT_SOURCE / name, target / name)


def bypass_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEV_PLATFORM_ALLOW_NO_CHECKS"] = "1"
    return env


class ProtectedMainZeroHandoffTests(unittest.TestCase):
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

    def make_feature(self, branch: str) -> str:
        git("switch", "-c", branch, cwd=self.repo)
        (self.repo / "feature.txt").write_text(branch + "\n", encoding="utf-8")
        git("add", "feature.txt", cwd=self.repo)
        git("commit", "-m", branch, cwd=self.repo)
        return git("rev-parse", "main", cwd=self.repo).stdout.strip()

    def test_protected_direct_is_rejected_before_local_main_mutation(self) -> None:
        (self.repo / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\nprotected_main = true\npublish_mode = "direct"\npr_merge_mode = "auto"\n',
            encoding="utf-8",
        )
        git("add", ".dev-platform.toml", cwd=self.repo)
        git("commit", "-m", "bad protected direct", cwd=self.repo)
        git("push", cwd=self.repo)
        before = self.make_feature("agent/protected-direct")
        remote_before = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=bypass_env(), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected_main=true", result.stderr + result.stdout)
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), before)
        self.assertEqual(run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(), remote_before)

    def test_auto_pr_waits_checks_merges_remotely_then_syncs_main(self) -> None:
        self.make_feature("agent/auto")
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then\n'
            '  if [ "$4" = "--json" ] && [ "$5" = "state,headRefOid" ]; then\n'
            '    head_sha=$(git rev-parse "$3" 2>/dev/null) || exit 1;\n'
            '    printf \'{"state":"OPEN","headRefOid":"%s"}\\n\' "$head_sha"; exit 0;\n'
            '  fi;\n'
            '  if [ "$4" = "--json" ] && [ "$5" = "state,mergedAt" ]; then\n'
            '    main_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null) || exit 1;\n'
            '    branch_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$3" 2>/dev/null) || exit 1;\n'
            '    if [ "$main_sha" = "$branch_sha" ]; then echo MERGED; else echo OPEN; fi; exit 0;\n'
            '  fi;\n'
            '  exit 1;\n'
            'fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/1"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$3") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("merged through GitHub", result.stdout)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        self.assertTrue((self.repo / "feature.txt").exists())
        local = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        remote = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        self.assertEqual(local, remote)
        remote_feature = run("git", "--git-dir", str(self.remote), "rev-parse", "--verify", "refs/heads/agent/auto", cwd=self.base, check=False)
        self.assertNotEqual(remote_feature.returncode, 0)

    def test_failed_cloud_checks_leave_local_and_remote_main_unchanged(self) -> None:
        local_before = self.make_feature("agent/fail-check")
        remote_before = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        env = self.fake_gh(
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/2"; exit 0; fi\n'
            'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo "platform-ci fail" >&2; exit 1; fi\n'
            'exit 1'
        )
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local main was not changed", result.stderr + result.stdout)
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), local_before)
        self.assertEqual(run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(), remote_before)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "agent/fail-check")

    def test_missing_api_auth_fails_finish_before_feature_push(self) -> None:
        self.make_feature("agent/no-auth")
        env = self.fake_gh('if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 1; fi\nexit 1')
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("authenticated GitHub CLI/API", result.stderr + result.stdout)
        remote_feature = run("git", "--git-dir", str(self.remote), "rev-parse", "--verify", "refs/heads/agent/no-auth", cwd=self.base, check=False)
        self.assertNotEqual(remote_feature.returncode, 0)


if __name__ == "__main__":
    unittest.main()
