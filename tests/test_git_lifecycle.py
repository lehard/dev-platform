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


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]: return run("git", *args, cwd=cwd, check=check)

def configure(repo: Path) -> None:
    git("config", "user.email", "test@example.com", cwd=repo); git("config", "user.name", "Platform Test", cwd=repo)

def install_scripts(repo: Path, profile: str = "light", publish: str = "direct") -> None:
    target = repo / "scripts"; target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "project_sync.py", "project_publish.py", "publication_state.py", "finish_task.py", "openspec_lifecycle.py"): shutil.copy2(SCRIPT_SOURCE / name, target / name)
    (repo / ".dev-platform.toml").write_text(f'main_branch = "main"\nworkflow_profile = "{profile}"\nharness_mode = "platform"\npublish_mode = "{publish}"\n', encoding="utf-8")


def explicit_bypass_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEV_PLATFORM_ALLOW_NO_CHECKS"] = "1"
    return env


def validated_direct_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"] = "1"
    return env


class GitLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name); self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"; run("git", "init", "-b", "main", str(self.seed), cwd=self.base); configure(self.seed)
        (self.seed / "README.md").write_text("seed\n", encoding="utf-8"); install_scripts(self.seed); (self.seed / ".gitignore").write_text(".claude/\n__pycache__/\n*.py[cod]\n", encoding="utf-8")
        git("add", ".", cwd=self.seed); git("commit", "-m", "seed platform", cwd=self.seed); git("remote", "add", "origin", str(self.remote), cwd=self.seed); git("push", "-u", "origin", "main", cwd=self.seed)
        run("git", "--git-dir", str(self.remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)
        self.repo = self.base / "repo"; run("git", "clone", str(self.remote), str(self.repo), cwd=self.base); configure(self.repo)

    def tearDown(self) -> None: self.tmp.cleanup()

    def test_sync_fast_forwards_behind_main(self) -> None:
        other = self.base / "other"; run("git", "clone", str(self.remote), str(other), cwd=self.base); configure(other)
        (other / "remote.txt").write_text("new\n", encoding="utf-8"); git("add", "remote.txt", cwd=other); git("commit", "-m", "remote", cwd=other); git("push", cwd=other)
        result = run("python3", "scripts/project_sync.py", cwd=self.repo); self.assertIn("Fast-forwarded", result.stdout); self.assertTrue((self.repo / "remote.txt").exists())

    def test_sync_refuses_local_ahead(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_sync.py", cwd=self.repo, check=False); self.assertNotEqual(result.returncode, 0); self.assertIn("ahead", result.stderr + result.stdout)

    def test_direct_publish_is_blocked_outside_validated_lifecycle(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("validated finish_task lifecycle", result.stderr + result.stdout)

    def test_direct_publish_pushes_fast_forward_with_explicit_validated_guard(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo, env=validated_direct_env()); self.assertIn("Published main", result.stdout)
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(); local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip(); self.assertEqual(remote_sha, local_sha)

    def test_no_checks_requires_explicit_operator_override(self) -> None:
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEV_PLATFORM_ALLOW_NO_CHECKS", result.stderr + result.stdout)

    def test_standard_direct_finish_integrates_and_pushes(self) -> None:
        (self.repo / ".dev-platform.toml").write_text('main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\npublish_mode = "direct"\n', encoding="utf-8"); git("add", ".dev-platform.toml", cwd=self.repo); git("commit", "-m", "standard profile", cwd=self.repo); git("push", cwd=self.repo)
        git("switch", "-c", "agent/test", cwd=self.repo); (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8"); git("add", "feature.txt", cwd=self.repo); git("commit", "-m", "feature", cwd=self.repo)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=explicit_bypass_env()); self.assertIn("Integrated agent/test -> main", result.stdout); self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(); local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip(); self.assertEqual(remote_sha, local_sha)

    def test_standard_pr_finish_returns_to_main(self) -> None:
        (self.repo / ".dev-platform.toml").write_text('main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\npublish_mode = "pr"\n', encoding="utf-8"); git("add", ".dev-platform.toml", cwd=self.repo); git("commit", "-m", "pr profile", cwd=self.repo); git("push", cwd=self.repo)
        git("switch", "-c", "agent/pr-test", cwd=self.repo); (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8"); git("add", "feature.txt", cwd=self.repo); git("commit", "-m", "feature pr", cwd=self.repo)
        fake_bin = self.base / "fake-bin"; fake_bin.mkdir(); fake_gh = fake_bin / "gh"
        fake_gh.write_text('#!/bin/sh\nif [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\nif [ "$1" = "pr" ] && [ "$2" = "view" ]; then exit 1; fi\nif [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/1"; exit 0; fi\nexit 1\n', encoding="utf-8"); fake_gh.chmod(0o755)
        env = explicit_bypass_env(); env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("Returned integration copy to main", result.stdout); self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        self.assertIsNotNone(run("git", "--git-dir", str(self.remote), "rev-parse", "refs/heads/agent/pr-test", cwd=self.base).stdout.strip())

    def test_multi_agent_pr_finish_reconciles_remote_merge_after_nonzero_gh_exit(self) -> None:
        config = (
            'main_branch = "main"\n'
            'workflow_profile = "multi-agent"\n'
            'harness_mode = "platform"\n'
            'protected_main = true\n'
            'publish_mode = "pr"\n'
            'pr_merge_mode = "auto"\n'
            '[paths]\n'
            'agent_board = ".claude/agents-board.json"\n'
            'main_merge_lock = ".claude/main-merge.lock"\n'
        )
        (self.repo / ".dev-platform.toml").write_text(config, encoding="utf-8")
        git("add", ".dev-platform.toml", cwd=self.repo); git("commit", "-m", "multi-agent protected pr", cwd=self.repo); git("push", cwd=self.repo)

        worktree = self.repo / ".claude" / "worktrees" / "pr-reconcile"
        worktree.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "-b", "agent/pr-reconcile", str(worktree), "main", cwd=self.repo)
        configure(worktree)
        (worktree / "feature.txt").write_text("feature\n", encoding="utf-8")
        git("add", "feature.txt", cwd=worktree); git("commit", "-m", "feature via protected pr", cwd=worktree)

        fake_bin = self.base / "fake-gh-bin"; fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        merged_marker = self.base / "merged.marker"
        created_marker = self.base / "created.marker"
        gh_log = self.base / "gh.log"
        fake_gh.write_text(
            "#!/bin/sh\n"
            f"echo \"$*\" >> '{gh_log}'\n"
            "if [ \"$1\" = \"auth\" ] && [ \"$2\" = \"status\" ]; then exit 0; fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"view\" ]; then\n"
            "  case \" $* \" in\n"
            "    *\" state,headRefOid \"*)\n"
            "      head_sha=$(git rev-parse \"$3\") || exit 1; printf '{\"state\":\"OPEN\",\"headRefOid\":\"%s\"}\\n' \"$head_sha\"; exit 0;;\n"
            "    *\" state,mergedAt \"*)\n"
            f"      if [ -f '{merged_marker}' ]; then echo MERGED; else echo OPEN; fi; exit 0;;\n"
            "    *)\n"
            f"      if [ -f '{created_marker}' ]; then echo https://example.invalid/pr/2; exit 0; fi; exit 1;;\n"
            "  esac\n"
            "fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"create\" ]; then\n"
            f"  touch '{created_marker}'; echo https://example.invalid/pr/2; exit 0\n"
            "fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"checks\" ]; then echo '[{\"name\":\"platform-ci\",\"state\":\"SUCCESS\",\"workflow\":\"platform-ci\",\"link\":\"\"}]'; exit 0; fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"merge\" ]; then\n"
            "  git push origin HEAD:main >/dev/null 2>&1\n"
            f"  touch '{merged_marker}'\n"
            "  echo \"simulated post-merge client failure\" >&2\n"
            "  exit 1\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        fake_gh.chmod(0o755)
        env = explicit_bypass_env(); env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

        result = run("python3", "scripts/finish_task.py", "--no-checks", "--cleanup", cwd=worktree, check=False, env=env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("GitHub confirms the PR is MERGED", result.stdout)
        self.assertIn("Task PR passed required checks, merged through GitHub", result.stdout)
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip()
        local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        self.assertEqual(remote_sha, local_sha)
        self.assertFalse(worktree.exists())
        self.assertNotEqual(git("show-ref", "--verify", "refs/heads/agent/pr-reconcile", cwd=self.repo, check=False).returncode, 0)
        self.assertNotEqual(run("git", "--git-dir", str(self.remote), "show-ref", "--verify", "refs/heads/agent/pr-reconcile", cwd=self.base, check=False).returncode, 0)
        logged = gh_log.read_text(encoding="utf-8")
        self.assertNotIn("--delete-branch", logged)
        self.assertIn("pr view agent/pr-reconcile --json state,mergedAt", logged)

    def test_direct_publish_refuses_divergence(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        other = self.base / "other"; run("git", "clone", str(self.remote), str(other), cwd=self.base); configure(other); (other / "remote.txt").write_text("remote\n", encoding="utf-8"); git("add", "remote.txt", cwd=other); git("commit", "-m", "remote", cwd=other); git("push", cwd=other)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo, check=False, env=validated_direct_env()); self.assertNotEqual(result.returncode, 0); self.assertIn("diverged", result.stderr + result.stdout)


if __name__ == "__main__": unittest.main()
