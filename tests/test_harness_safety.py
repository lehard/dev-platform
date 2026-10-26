from __future__ import annotations

import os
import shutil
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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

    def test_serialized_integration_is_reentrant_within_one_process(self) -> None:
        if finish_task.fcntl is None:
            self.skipTest("fcntl is unavailable on this platform")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = {"paths": {"main_merge_lock": ".claude/main-merge.lock"}}
            # A nested acquisition on the same lock path must not self-deadlock:
            # e.g. finish preflight repairs shared config while finish already
            # holds the integration lock for a direct publish.
            with finish_task.serialized_integration(root, config, 1.0):
                with finish_task.serialized_integration(root, config, 0.05):
                    pass
            # The lock is fully released afterwards, so a fresh acquisition works.
            with finish_task.serialized_integration(root, config, 0.05):
                pass

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

    def test_agent_doctor_installs_claude_write_gate_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = root / ".claude" / "settings.local.json"
            settings.parent.mkdir()
            settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}), encoding="utf-8")
            self.assertEqual(agent_doctor.ensure_claude_write_gate(root), ("installed", 0))
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
            self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)
            self.assertEqual(data["hooks"]["PreToolUse"][1]["matcher"], "Write|Edit|MultiEdit|NotebookEdit")
            self.assertEqual(data["hooks"]["PreToolUse"][1]["hooks"][0]["command"], agent_doctor.WRITE_GATE_COMMAND)
            before = settings.read_text(encoding="utf-8")
            self.assertEqual(agent_doctor.ensure_claude_write_gate(root), ("present", 0))
            self.assertEqual(settings.read_text(encoding="utf-8"), before)

    def test_agent_doctor_creates_missing_settings_for_write_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(agent_doctor.ensure_claude_write_gate(root), ("installed", 0))
            self.assertTrue((root / ".claude" / "settings.local.json").is_file())

    def test_agent_doctor_refuses_to_overwrite_malformed_write_gate_settings(self) -> None:
        bad = ["{not json", "[]", json.dumps({"hooks": []}), json.dumps({"hooks": {"PreToolUse": {}}})]
        for content in bad:
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                settings = root / ".claude" / "settings.local.json"
                settings.parent.mkdir()
                settings.write_text(content, encoding="utf-8")
                state, failures = agent_doctor.ensure_claude_write_gate(root)
                self.assertTrue(state.startswith("malformed-settings"), state)
                self.assertEqual(failures, 1)
                self.assertEqual(settings.read_text(encoding="utf-8"), content)

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

    def test_agent_doctor_describes_local_friction_review_as_recovery_surface(self) -> None:
        completed = subprocess.CompletedProcess(
            ["python3", "scripts/agent_friction.py"], 0,
            '{"ready": true, "pending_count": 5, "reason": "minimum-events"}', "",
        )
        with patch.object(agent_doctor.subprocess, "run", return_value=completed), patch.object(agent_doctor, "report") as report:
            agent_doctor.run_friction_review_status(ROOT)
        kind, message = report.call_args.args
        self.assertEqual(kind, "ok")
        self.assertIn("weekly cloud Process Health Review is the routine cadence", message)
        self.assertIn("recovery/diagnostic", message)
        self.assertNotIn("review is ready", message)

    def test_doctor_and_finish_never_wait_on_friction_routing(self) -> None:
        # Routing retry is an explicit operator command; ordinary start/doctor/finish/advance never run it.
        for module in (agent_doctor, finish_task):
            with self.subTest(module.__name__):
                source = Path(module.__file__).read_text(encoding="utf-8")
                self.assertNotIn("route-pending", source)
                self.assertNotIn("friction routing retry", source)
        self.assertFalse(hasattr(agent_doctor, "retry_friction_routing"))
        self.assertFalse(hasattr(finish_task, "run_friction_route_pending_retry"))

    def test_agent_doctor_distinguishes_degraded_board_warning_from_a_blocked_error(self) -> None:
        board = subprocess.CompletedProcess(
            ["python3", "scripts/agent_board.py", "doctor"],
            1,
            '{"status":"diagnostic","entries":[{"id":"sibling","eligibility":"degraded","problems":["branch-path-mismatch"]}]}',
            "",
        )
        cleanup = subprocess.CompletedProcess(
            ["python3", "scripts/worktree_cleanup.py", "scan"],
            0,
            '{"pending":0,"eligible":0}',
            "",
        )
        with patch.object(agent_doctor.subprocess, "run", side_effect=[board, cleanup]), patch.object(agent_doctor, "report") as report:
            self.assertEqual(agent_doctor.run_multi_agent_hygiene(ROOT), 0)
        warnings = [call.args for call in report.call_args_list if call.args[0] == "warn"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("contribute no blocking scope claim", warnings[0][1])
        self.assertIn("sibling (degraded: branch-path-mismatch)", warnings[0][1])


if __name__ == "__main__":
    unittest.main()
