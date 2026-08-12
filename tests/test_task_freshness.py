from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _platform_common  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "freshness@example.invalid", cwd=root)
    git("config", "user.name", "Freshness Test", cwd=root)


class TaskFreshnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
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
        self.task = self.base / "task"
        run("git", "clone", str(self.remote), str(self.task), cwd=self.base)
        configure(self.task)
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "platform"\n', encoding="utf-8"
        )
        checks = self.task / "dev-platform" / "checks.toml"
        checks.parent.mkdir()
        checks.write_text(
            '[settings]\nfull_commands = ["printf full-validation-ran > validation-ran.txt"]\n', encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def selector(self) -> subprocess.CompletedProcess[str]:
        return run(
            "python3", str(SCRIPTS / "select_checks.py"), "--mode", "protected-full", "--execute", cwd=self.task, check=False
        )

    def advance_main(self) -> None:
        other = self.base / "other"
        run("git", "clone", str(self.remote), str(other), cwd=self.base)
        configure(other)
        (other / "main.txt").write_text("advanced\n", encoding="utf-8")
        git("add", "main.txt", cwd=other)
        git("commit", "-m", "advance main", cwd=other)
        git("push", cwd=other)

    def test_fresh_task_runs_the_selected_full_command(self) -> None:
        result = self.selector()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Task freshness gate passed", result.stdout)
        self.assertIn("DEV_PLATFORM_CHECK_COMMAND: printf full-validation-ran", result.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_stale_task_stops_before_full_validation_and_retry_after_reconciliation_runs_it(self) -> None:
        self.advance_main()

        stale = self.selector()
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("Task freshness gate blocked full/protected validation before any expensive command started", stale.stderr + stale.stdout)
        self.assertIn("behind relative", stale.stderr + stale.stdout)
        self.assertFalse((self.task / "validation-ran.txt").exists())
        self.assertNotIn("DEV_PLATFORM_CHECK_COMMAND", stale.stdout)

        git("merge", "--ff-only", "origin/main", cwd=self.task)
        retried = self.selector()
        self.assertEqual(retried.returncode, 0, retried.stderr + retried.stdout)
        self.assertIn("Task freshness gate passed", retried.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_unavailable_remote_never_claims_the_task_is_fresh(self) -> None:
        git("remote", "set-url", "origin", str(self.base / "missing.git"), cwd=self.task)

        result = self.selector()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unable to refresh authoritative origin/main", result.stderr + result.stdout)
        self.assertFalse((self.task / "validation-ran.txt").exists())

    def test_project_harness_keeps_its_existing_validation_runner_ownership(self) -> None:
        (self.task / ".dev-platform.toml").write_text(
            'main_branch = "main"\nworkflow_profile = "standard"\nharness_mode = "project"\n', encoding="utf-8"
        )
        git("remote", "set-url", "origin", str(self.base / "missing.git"), cwd=self.task)

        result = self.selector()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn("Task freshness gate", result.stdout)
        self.assertTrue((self.task / "validation-ran.txt").is_file())

    def test_helper_reports_diverged_task_without_reconciliation(self) -> None:
        self.advance_main()
        (self.task / "task.txt").write_text("task\n", encoding="utf-8")
        git("add", "task.txt", cwd=self.task)
        git("commit", "-m", "task diverges", cwd=self.task)

        with self.assertRaisesRegex(_platform_common.TaskFreshnessError, "diverged relative"):
            _platform_common.require_fresh_task_base(self.task, "origin", "main")
        self.assertEqual(git("log", "-1", "--format=%s", cwd=self.task).stdout.strip(), "task diverges")


if __name__ == "__main__":
    unittest.main()
