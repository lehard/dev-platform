from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(TEMPLATE_SCRIPTS))

import start_worktree  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from _platform_config import platform_config_text  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev = _load("fresh_worktree_dev", TEMPLATE_SCRIPTS / "dev.py")
doctor = _load("fresh_worktree_doctor", TEMPLATE_SCRIPTS / "platform_doctor.py")

CAPABILITY = "systematic-bug-diagnosis"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


class FreshWorktreeReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        scripts = self.root / "scripts"
        scripts.mkdir()
        (scripts / "agent_board.py").write_text('import sys\nif sys.argv[1] == "start": print("synthetic-board")\n')
        shutil.copy2(TEMPLATE_SCRIPTS / "capability_manager.py", scripts / "capability_manager.py")
        shutil.copy2(TEMPLATE_SCRIPTS / "capability_evals.py", scripts / "capability_evals.py")
        # capability_manager reads the validated platform configuration through these modules.
        for name in ("_platform_common.py", "shared_workspace.py"):
            shutil.copy2(TEMPLATE_SCRIPTS / name, scripts / name)
        capabilities = self.root / "dev-platform" / "capabilities"
        capabilities.mkdir(parents=True)
        for suffix in (".toml", ".md"):
            shutil.copy2(ROOT / "dev-platform" / "capabilities" / f"{CAPABILITY}{suffix}", capabilities / f"{CAPABILITY}{suffix}")
        (self.root / "dev-platform" / "capabilities.toml").write_text(f'version = 1\nenabled = ["{CAPABILITY}"]\n')
        (self.root / ".dev-platform.toml").write_text(platform_config_text())
        (self.root / ".gitignore").write_text(".claude/\n.codex/\n__pycache__/\n")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "synthetic baseline")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(self):
        with mock.patch.object(start_worktree, "preflight"), \
             mock.patch.object(start_worktree, "read_platform_config", return_value={"workflow_profile": "multi-agent", "main_branch": "main"}), \
             mock.patch.object(start_worktree, "machine_path", return_value=self.root / ".claude/worktrees"):
            return start_worktree.create_worktree(self.root, "change", "Synthetic task", sync=False)

    def test_fresh_worktree_has_selected_surfaces_and_passes_audit(self) -> None:
        created = self._create()
        for provider in ("claude", "codex"):
            self.assertTrue((created.worktree / f".{provider}/skills/dev-platform-{CAPABILITY}/SKILL.md").is_file())
        audit = subprocess.run(
            [sys.executable, "scripts/capability_manager.py", "--json", "audit"],
            cwd=created.worktree, text=True, capture_output=True, check=False,
        )
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
        self.assertEqual(json.loads(audit.stdout)["status"], "ok")
        self.assertEqual(git(created.worktree, "status", "--porcelain"), "")

    def test_failed_sync_stops_start_and_rolls_back(self) -> None:
        (self.root / "scripts" / "capability_manager.py").write_text(
            "import sys\nprint('cannot write .claude/skills: permission denied', file=sys.stderr)\nraise SystemExit(1)\n"
        )
        git(self.root, "commit", "-am", "broken manager")
        with self.assertRaises(RuntimeError) as raised:
            self._create()
        message = str(raised.exception)
        self.assertIn("permission denied", message)
        self.assertIn("python3 scripts/capability_manager.py sync", message)
        self.assertIn(str(self.root / ".claude/worktrees/change"), message)
        self.assertFalse((self.root / ".claude/worktrees/change").exists())
        self.assertEqual(git(self.root, "branch", "--list", "agent/change"), "")


class GeneratedExcludeLocationTests(unittest.TestCase):
    def test_linked_worktree_writes_common_exclude_without_private_info_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "repo"
            root.mkdir()
            git(root, "init", "-b", "main")
            git(root, "-c", "user.email=t@example.invalid", "-c", "user.name=T", "commit", "--allow-empty", "-m", "i")
            linked = Path(tmp).resolve() / "linked"
            git(root, "worktree", "add", "-q", str(linked))
            private = Path(git(linked, "rev-parse", "--path-format=absolute", "--git-dir"))
            dev.ensure_local_generated_excludes(linked)
            dev.ensure_local_generated_excludes(linked)
            self.assertFalse((private / "info").exists())
            exclude = (root / ".git" / "info" / "exclude").read_text(encoding="utf-8")
            for pattern in dev.LOCAL_GENERATED_EXCLUDES:
                self.assertEqual(exclude.splitlines().count(pattern), 1)
            self.assertEqual(git(linked, "check-ignore", "AGENTS.local.md"), "AGENTS.local.md")


class DoctorCapabilityHintTests(unittest.TestCase):
    def test_capability_failure_names_sync_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "dev-platform" / "capabilities").mkdir(parents=True)
            (root / "dev-platform" / "capabilities.toml").write_text("version = 1\nenabled = []\n")
            (root / "scripts" / "capability_manager.py").write_text(
                "import json\nprint(json.dumps({'status': 'error', 'issues': ['stale']}))\nraise SystemExit(1)\n"
            )
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            failures = [0]
            with mock.patch("builtins.print") as printed:
                doctor.check_engineering_capabilities(root, failures)
            self.assertEqual(failures, [1])
            line = printed.call_args.args[0]
            self.assertIn("python3 scripts/capability_manager.py sync", line)
            self.assertEqual(sorted(path.relative_to(root) for path in root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
