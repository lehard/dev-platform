"""Lifecycle breakages of the simple delivery path, replayed on local Git.

Each scenario guards a breakage that already happened in a real delivery and
that no other test catches. They run real entrypoints in a temporary
repository with a bare remote: no network, no sandbox and no GitHub CLI.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import lifecycle_preflight as preflight  # noqa: E402
from _platform_config import write_platform_config  # noqa: E402

# A declared generator: it lists the files of src/, so main and the task both change its output.
GENERATOR = """\
import pathlib, sys
root = pathlib.Path(sys.argv[sys.argv.index("--root") + 1]) if "--root" in sys.argv else pathlib.Path(".")
content = "".join(sorted(path.name + "\\n" for path in (root / "src").iterdir()))
target = root / "gen" / "manifest.txt"
if "--check" in sys.argv:
    sys.exit(0 if target.read_text(encoding="utf-8") == content else 1)
target.parent.mkdir(exist_ok=True)
target.write_text(content, encoding="utf-8")
"""
CHECKS_WITH_GENERATED_FILE = """\
[settings]
full_commands = ["python3 scripts/gen.py --check"]

[[generated_files]]
path = "gen/manifest.txt"
regenerate = ["python3", "scripts/gen.py", "--write", "--root", "{tree}"]
check = ["python3", "scripts/gen.py", "--check"]
"""
COVERAGE_COMMAND = "python3 scripts/run_test_groups.py --verify-coverage"
RECONCILE = "python3 scripts/finish_task.py --reconcile"


def run(*args: str, cwd: Path, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise AssertionError(f"{' '.join(args)} exited {result.returncode} in {cwd}:\n{result.stdout}{result.stderr}")
    return result


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("git", *args, cwd=cwd, check=check)


def configure(root: Path) -> None:
    git("config", "user.email", "scenario@example.invalid", cwd=root)
    git("config", "user.name", "Lifecycle Scenario", cwd=root)


def copy_lifecycle_scripts(root: Path) -> None:
    """The whole template script directory, so a new lifecycle dependency never breaks the fixture."""
    shutil.copytree(ROOT / "template" / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))


class ReconcileConflictHintScenario(unittest.TestCase):
    """Source: the 2026-11-06 bad-outcome drill, fixed in lehard/dev-platform#940.

    The reconcile conflict hint stopped at "resolve and commit", and a declared
    generated file had to be guessed. The fix was proven only by a manual probe
    that followed the hint literally; the unit test checks the text with the
    generated-file declaration mocked. Here the hint is followed as printed.
    """

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        remote = self.base / "remote.git"
        run("git", "init", "-q", "--bare", str(remote), cwd=self.base)
        run("git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main", cwd=self.base)

        seed = self.base / "seed"
        run("git", "init", "-q", "-b", "main", str(seed), cwd=self.base)
        configure(seed)
        copy_lifecycle_scripts(seed)
        (seed / "scripts" / "gen.py").write_text(GENERATOR, encoding="utf-8")
        (seed / "src").mkdir()
        (seed / "src" / "base.txt").write_text("base\n", encoding="utf-8")
        (seed / "shared.txt").write_text("base\n", encoding="utf-8")
        (seed / "dev-platform").mkdir()
        (seed / "dev-platform" / "checks.toml").write_text(CHECKS_WITH_GENERATED_FILE, encoding="utf-8")
        write_platform_config(seed, workflow_profile="standard", capabilities={"agent_board": False})
        run("python3", "scripts/gen.py", "--write", "--root", ".", cwd=seed)
        git("add", "-A", cwd=seed)
        git("commit", "-qm", "base", cwd=seed)
        git("remote", "add", "origin", str(remote), cwd=seed)
        git("push", "-q", "-u", "origin", "main", cwd=seed)

        self.task = self.clone(remote, "task")
        git("switch", "-qc", "agent/task", cwd=self.task)
        self.change(self.task, "task.txt", "task\n", "task work")
        self.task_commit = git("rev-parse", "HEAD", cwd=self.task).stdout.strip()

        other = self.clone(remote, "other")
        self.change(other, "main.txt", "main\n", "main moves")
        git("push", "-q", cwd=other)
        self.main_commit = git("rev-parse", "HEAD", cwd=other).stdout.strip()

        # Only git and python3 are reachable: no GitHub CLI, so nothing can talk to GitHub.
        tools = self.base / "bin"
        tools.mkdir()
        for tool in ("git", "python3"):
            found = shutil.which(tool)
            if found is None:
                raise AssertionError(f"{tool} is required on PATH for this scenario")
            (tools / tool).symlink_to(found)
        self.env = {**os.environ, "PATH": str(tools)}

    def clone(self, remote: Path, name: str) -> Path:
        path = self.base / name
        run("git", "clone", "-q", str(remote), str(path), cwd=self.base)
        configure(path)
        return path

    def change(self, root: Path, source_name: str, shared: str, message: str) -> None:
        """Add a source file, change the shared file and regenerate, as a real template change does."""
        (root / "src" / source_name).write_text(source_name + "\n", encoding="utf-8")
        (root / "shared.txt").write_text(shared, encoding="utf-8")
        run("python3", "scripts/gen.py", "--write", "--root", ".", cwd=root)
        git("add", "-A", cwd=root)
        git("commit", "-qm", message, cwd=root)

    def finish_task(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run("python3", "scripts/finish_task.py", *args, cwd=self.task, env=self.env, check=False)

    def hint_steps(self, result: subprocess.CompletedProcess[str]) -> list[str]:
        output = result.stdout + result.stderr
        match = re.search(r"Then: 1\) (.*?)\.\s*$", output, re.S)
        if match is None:
            raise AssertionError("reconcile printed no numbered steps:\n" + output)
        return re.split(r"; \d+\) ", match.group(1))

    def test_following_the_printed_steps_literally_reconciles_the_task(self) -> None:
        stopped = self.finish_task("--reconcile")
        self.assertEqual(stopped.returncode, 1, stopped.stdout + stopped.stderr)
        self.assertIn("conflicting paths: gen/manifest.txt, shared.txt", stopped.stdout + stopped.stderr)
        steps = self.hint_steps(stopped)
        self.assertEqual(steps[0], "edit the conflicting files")
        self.assertEqual(steps[-1], RECONCILE)

        # While the merge is unfinished, status answers and names reconcile; reconcile repeats the steps.
        status = self.finish_task("--status")
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        self.assertNotIn("Traceback", status.stdout + status.stderr)
        self.assertIn(RECONCILE, status.stdout)
        repeated = self.finish_task("--reconcile")
        self.assertEqual(repeated.returncode, 1, repeated.stdout + repeated.stderr)
        self.assertIn("unfinished merge", repeated.stdout + repeated.stderr)
        self.assertEqual(self.hint_steps(repeated), steps)

        # Step 1 is the only one a person does; every other step runs exactly as printed.
        (self.task / "shared.txt").write_text("task and main\n", encoding="utf-8")
        outputs = []
        for step in steps[1:]:
            result = run(*shlex.split(step), cwd=self.task, env=self.env, check=False)
            self.assertEqual(result.returncode, 0, f"step {step!r} failed:\n{result.stdout}{result.stderr}")
            outputs.append(result.stdout)
        self.assertIn("reconcile is a no-op", outputs[-1])

        self.assertEqual(git("status", "--porcelain", cwd=self.task).stdout, "")
        self.assertEqual(git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=self.task, check=False).returncode, 1)
        self.assertEqual((self.task / "gen" / "manifest.txt").read_text(encoding="utf-8"), "base.txt\nmain.txt\ntask.txt\n")
        parents = git("rev-list", "--parents", "-n", "1", "HEAD", cwd=self.task).stdout.split()[1:]
        self.assertEqual(parents, [self.task_commit, self.main_commit], "the task commit stays in history; main is merged, not rebased")


class UngroupedTestStopsPreflightScenario(unittest.TestCase):
    """Source: the 2026-11-06 bad-outcome drill, fixed in lehard/dev-platform#936.

    A new test file without a group was caught only by the required CI check,
    after a full local finish. The fix is one line of this repository's
    `preflight_commands`; this scenario fails if that line goes away or stops
    refusing an ungrouped test.
    """

    def configured_coverage_command(self) -> str:
        with (ROOT / "dev-platform" / "checks.toml").open("rb") as handle:
            commands = tomllib.load(handle)["settings"]["preflight_commands"]
        if COVERAGE_COMMAND not in commands:
            raise AssertionError(f"dev-platform/checks.toml preflight_commands lacks {COVERAGE_COMMAND!r}: {commands}")
        return COVERAGE_COMMAND

    def test_a_test_file_without_a_group_stops_the_cheap_project_gates(self) -> None:
        command = self.configured_coverage_command()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            git("init", "-q", "-b", "main", cwd=root)
            copy_lifecycle_scripts(root)
            write_platform_config(root, workflow_profile="standard", capabilities={"agent_board": False})
            (root / "tests").mkdir()
            for name in ("test_grouped", "test_new_scenario"):
                (root / "tests" / f"{name}.py").write_text(
                    "import unittest\n\n\nclass Case(unittest.TestCase):\n    def test_it(self) -> None:\n        pass\n",
                    encoding="utf-8",
                )
            checks = root / "dev-platform" / "checks.toml"
            checks.parent.mkdir()

            def declare_group(*targets: str) -> None:
                listed = ", ".join(f'"{target}"' for target in targets)
                checks.write_text(
                    f'[settings]\npreflight_commands = ["{command}"]\n\n'
                    f'[test_groups.only]\ntargets = [{listed}]\nmode = "parallel"\n',
                    encoding="utf-8",
                )

            context = preflight.PreflightContext(root=root, integration=root, branch="agent/task", entry="scenario")
            declare_group("test_grouped")
            with self.assertRaises(preflight.PreflightRefusal) as refused:
                preflight.check_project_cheap_gates(context)
            self.assertIn(command, str(refused.exception))
            self.assertIn("belong to no group: test_new_scenario.Case.test_it", str(refused.exception))

            declare_group("test_grouped", "test_new_scenario")
            self.assertEqual(preflight.check_project_cheap_gates(context).state, preflight.PASSED)


if __name__ == "__main__":
    unittest.main()
