from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = ROOT / "template" / "scripts"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]: return run("git", *args, cwd=cwd, check=check)

def configure(repo: Path) -> None:
    git("config", "user.email", "test@example.com", cwd=repo); git("config", "user.name", "Platform Test", cwd=repo)

def install_scripts(repo: Path, profile: str = "light", publish: str = "direct") -> None:
    target = repo / "scripts"; target.mkdir(exist_ok=True)
    for name in ("_platform_common.py", "project_sync.py", "project_publish.py", "finish_task.py"): shutil.copy2(SCRIPT_SOURCE / name, target / name)
    (repo / ".dev-platform.toml").write_text(f'main_branch = "main"\nworkflow_profile = "{profile}"\npublish_mode = "{publish}"\n', encoding="utf-8")


class GitLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name); self.remote = self.base / "remote.git"
        run("git", "init", "--bare", str(self.remote), cwd=self.base)
        self.seed = self.base / "seed"; run("git", "init", "-b", "main", str(self.seed), cwd=self.base); configure(self.seed)
        (self.seed / "README.md").write_text("seed\n", encoding="utf-8"); install_scripts(self.seed); (self.seed / ".gitignore").write_text("__pycache__/\n*.py[cod]\n", encoding="utf-8")
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

    def test_direct_publish_pushes_fast_forward(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo); self.assertIn("Published main", result.stdout)
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(); local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip(); self.assertEqual(remote_sha, local_sha)

    def test_standard_direct_finish_integrates_and_pushes(self) -> None:
        (self.repo / ".dev-platform.toml").write_text('main_branch = "main"\nworkflow_profile = "standard"\npublish_mode = "direct"\n', encoding="utf-8"); git("add", ".dev-platform.toml", cwd=self.repo); git("commit", "-m", "standard profile", cwd=self.repo); git("push", cwd=self.repo)
        git("switch", "-c", "agent/test", cwd=self.repo); (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8"); git("add", "feature.txt", cwd=self.repo); git("commit", "-m", "feature", cwd=self.repo)
        result = run("python3", "scripts/finish_task.py", "--no-checks", cwd=self.repo); self.assertIn("Integrated agent/test -> main", result.stdout); self.assertEqual(git("branch", "--show-current", cwd=self.repo).stdout.strip(), "main")
        remote_sha = run("git", "--git-dir", str(self.remote), "rev-parse", "main", cwd=self.base).stdout.strip(); local_sha = git("rev-parse", "main", cwd=self.repo).stdout.strip(); self.assertEqual(remote_sha, local_sha)

    def test_direct_publish_refuses_divergence(self) -> None:
        (self.repo / "local.txt").write_text("local\n", encoding="utf-8"); git("add", "local.txt", cwd=self.repo); git("commit", "-m", "local", cwd=self.repo)
        other = self.base / "other"; run("git", "clone", str(self.remote), str(other), cwd=self.base); configure(other); (other / "remote.txt").write_text("remote\n", encoding="utf-8"); git("add", "remote.txt", cwd=other); git("commit", "-m", "remote", cwd=other); git("push", cwd=other)
        result = run("python3", "scripts/project_publish.py", "--mode", "direct", cwd=self.repo, check=False); self.assertNotEqual(result.returncode, 0); self.assertIn("diverged", result.stderr + result.stdout)


if __name__ == "__main__": unittest.main()
