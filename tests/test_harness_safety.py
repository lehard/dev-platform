from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))

import agent_doctor  # noqa: E402
import finish_task  # noqa: E402


class HarnessSafetyTests(unittest.TestCase):
    def test_serialized_integration_rejects_concurrent_holder(self) -> None:
        if finish_task.fcntl is None:
            self.skipTest("fcntl is unavailable on this platform")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"paths": {"main_merge_lock": ".claude/main-merge.lock"}}
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SCRIPT_ROOT)
            child = """
from pathlib import Path
from finish_task import serialized_integration
with serialized_integration(Path(%r), {"paths": {"main_merge_lock": ".claude/main-merge.lock"}}, 0.05):
    pass
""" % str(root)
            with finish_task.serialized_integration(root, config, 1.0):
                result = subprocess.run(
                    [sys.executable, "-c", child],
                    text=True,
                    capture_output=True,
                    env=env,
                )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Another agent is still integrating", result.stderr)

    def test_agent_doctor_installs_managed_hooks_and_preserves_foreign_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            target_hooks = root / "scripts" / "git_hooks"
            shutil.copytree(SCRIPT_ROOT / "git_hooks", target_hooks)

            results, failures = agent_doctor.ensure_git_hooks(root)
            self.assertEqual(failures, 0)
            self.assertEqual(results["pre-commit"], "installed")
            self.assertEqual(results["pre-merge-commit"], "installed")
            installed = root / ".git" / "hooks" / "pre-commit"
            self.assertTrue(installed.stat().st_mode & 0o111)

            installed.write_text("#!/bin/sh\n# foreign project hook\nexit 0\n", encoding="utf-8")
            before = installed.read_text(encoding="utf-8")
            results, failures = agent_doctor.ensure_git_hooks(root)
            self.assertEqual(results["pre-commit"], "foreign-hook-kept")
            self.assertEqual(failures, 1)
            self.assertEqual(installed.read_text(encoding="utf-8"), before)

    def test_main_copy_status_surfaces_dirty_integration_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
            (root / "tracked.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "base"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            (root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
            dirty, conflicted = agent_doctor.main_copy_status(root)
            self.assertEqual(conflicted, [])
            self.assertIn("tracked.txt", dirty)


if __name__ == "__main__":
    unittest.main()
