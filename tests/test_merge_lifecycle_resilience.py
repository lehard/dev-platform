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
    git("config", "user.name", "Merge Lifecycle Test", cwd=repo)


def install_scripts(repo: Path) -> None:
    target = repo / "scripts"
    target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "integration_state.py", "project_publish.py", "publication_state.py", "task_reconciliation.py", "managed_project_status.py", "finish_task.py", "openspec_lifecycle.py"):
        shutil.copy2(SCRIPT_SOURCE / name, target / name)


def bypass_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEV_PLATFORM_ALLOW_NO_CHECKS"] = "1"
    return env


COMMON_PR_BODY = r'''
if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
  branch=$(git branch --show-current) || exit 1
  head_sha=$(git rev-parse "$branch") || exit 1
  printf '[{"number":1,"url":"https://example.invalid/pr/1","state":"OPEN","headRefOid":"%s","baseRefName":"main","headRefName":"%s"}]\n' "$head_sha" "$branch"
  exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
  branch=$(git branch --show-current) || exit 1
  if [ "$4" = "--json" ] && [ "$5" = "state,headRefOid" ]; then
    head_sha=$(git rev-parse "$branch" 2>/dev/null) || exit 1
    main_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null) || exit 1
    branch_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$branch" 2>/dev/null) || exit 1
    if [ "$main_sha" = "$branch_sha" ]; then state=MERGED; else state=OPEN; fi
    printf '{"state":"%s","headRefOid":"%s"}\n' "$state" "$head_sha"
    exit 0
  fi
  if [ "$4" = "--json" ] && [ "$5" = "state,mergedAt" ]; then
    main_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse refs/heads/main 2>/dev/null) || exit 1
    branch_sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$branch" 2>/dev/null) || exit 1
    if [ "$main_sha" = "$branch_sha" ]; then echo MERGED; else echo OPEN; fi
    exit 0
  fi
  exit 1
fi
if [ "$1" = "pr" ] && [ "$2" = "create" ]; then echo "https://example.invalid/pr/1"; exit 0; fi
'''


class MergeLifecycleResilienceTests(unittest.TestCase):
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
        return git("rev-parse", branch, cwd=self.repo).stdout.strip()

    def test_stale_environment_tokens_fall_back_to_persistent_gh_auth(self) -> None:
        self.make_feature("agent/stale-token")
        body = (
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then\n'
            '  if [ -n "$GH_TOKEN" ] || [ -n "$GITHUB_TOKEN" ]; then exit 1; fi\n'
            '  exit 0\n'
            'fi\n'
            + COMMON_PR_BODY
            + 'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            + 'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then branch=$(git branch --show-current) || exit 1; sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$branch") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0; fi\n'
            + 'exit 1'
        )
        env = self.fake_gh(body)
        env["GH_TOKEN"] = "expired-token"
        env["GITHUB_TOKEN"] = "expired-token"
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("merged through GitHub", result.stdout)
        self.assertNotIn("auth login", result.stdout + result.stderr)

    def test_delayed_required_check_registration_is_waited_out(self) -> None:
        self.make_feature("agent/delayed-checks")
        check_state = self.base / "check-count"
        body = (
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            + COMMON_PR_BODY
            + 'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then\n'
            + '  count=0; if [ -f "$FAKE_CHECK_STATE" ]; then count=$(cat "$FAKE_CHECK_STATE"); fi; count=$((count + 1)); echo "$count" > "$FAKE_CHECK_STATE";\n'
            + '  if [ "$count" -lt 2 ]; then echo "[]"; exit 0; fi;\n'
            + '  echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0;\n'
            + 'fi\n'
            + 'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then\n'
            + '  count=0; if [ -f "$FAKE_CHECK_STATE" ]; then count=$(cat "$FAKE_CHECK_STATE"); fi\n'
            + '  if [ "$count" -lt 2 ]; then echo "required status check is expected" >&2; exit 1; fi\n'
            + '  branch=$(git branch --show-current) || exit 1; sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$branch") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0\n'
            + 'fi\n'
            + 'exit 1'
        )
        env = self.fake_gh(body)
        env["FAKE_CHECK_STATE"] = str(check_state)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn(
            "Native GitHub auto-merge/merge-queue could not be armed for the exact validated head",
            result.stdout,
        )
        self.assertIn("not registered yet", result.stdout)
        self.assertEqual(check_state.read_text(encoding="utf-8").strip(), "2")
        self.assertIn("merged through GitHub", result.stdout)

    def test_merge_policy_falls_back_to_auto_merge(self) -> None:
        self.make_feature("agent/merge-queue")
        body = (
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            + COMMON_PR_BODY
            + 'if [ "$1" = "pr" ] && [ "$2" = "checks" ]; then echo \'[{"name":"platform-ci","state":"SUCCESS","workflow":"platform-ci","link":""}]\'; exit 0; fi\n'
            + 'if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then\n'
            + '  case " $* " in *" --auto "*) branch=$(git branch --show-current) || exit 1; sha=$(git --git-dir "$FAKE_REMOTE" rev-parse "refs/heads/$branch") || exit 1; git --git-dir "$FAKE_REMOTE" update-ref refs/heads/main "$sha" || exit 1; exit 0;; esac;\n'
            + '  echo "merge queue required" >&2; exit 1;\n'
            + 'fi\n'
            + 'exit 1'
        )
        env = self.fake_gh(body)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("trying the next protected GitHub merge mode", result.stdout)
        self.assertIn("merged through GitHub", result.stdout)

    def test_rerun_recovers_when_exact_pr_head_is_already_merged(self) -> None:
        feature_sha = self.make_feature("agent/already-merged")
        base_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip()
        tree_sha = git("rev-parse", "agent/already-merged^{tree}", cwd=self.repo).stdout.strip()
        squash_sha = git("commit-tree", tree_sha, "-p", base_sha, "-m", "squash merged", cwd=self.repo).stdout.strip()
        git("push", "origin", f"{squash_sha}:refs/heads/main", cwd=self.repo)

        body = (
            'if [ "$1" = "auth" ] && [ "$2" = "status" ]; then exit 0; fi\n'
            + 'if [ "$1" = "pr" ] && [ "$2" = "list" ]; then\n'
            + f'  printf \'[{{"number":1,"url":"https://example.invalid/pr/1","state":"MERGED","headRefOid":"{feature_sha}","baseRefName":"main","headRefName":"agent/already-merged"}}]\\n\'; exit 0;\n'
            + 'fi\n'
            + 'if [ "$1" = "pr" ] && [ "$2" = "view" ] && [ "$4" = "--json" ] && [ "$5" = "state,headRefOid" ]; then\n'
            + f'  printf \'{{"state":"MERGED","headRefOid":"{feature_sha}"}}\\n\'; exit 0;\n'
            + 'fi\n'
            + 'exit 1'
        )
        env = self.fake_gh(body)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo, env=env)
        self.assertIn("already merged through GitHub", result.stdout)
        self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        self.assertEqual(git("rev-parse", "main", cwd=self.repo).stdout.strip(), squash_sha)
        self.assertTrue((self.repo / "feature.txt").exists())


if __name__ == "__main__":
    unittest.main()
