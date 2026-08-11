from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPT_ROOT))


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


delegation_containment = _load("delegation_containment", "delegation_containment.py")
guard = _load("delegated_write_guard", "delegated_write_guard.py")


def git(*arguments: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=check)


FAKE_CODEX_WITH_SANDBOX = """#!/usr/bin/env python3
import sys
if sys.argv[1:3] == ["exec", "--help"]:
    print("-s, --sandbox <SANDBOX_MODE> [possible values: read-only, workspace-write, danger-full-access]")
    print("-C, --cd <DIR>")
    raise SystemExit(0)
raise SystemExit("unexpected invocation: " + repr(sys.argv))
"""

FAKE_CODEX_WITHOUT_SANDBOX = """#!/usr/bin/env python3
import sys
if sys.argv[1:3] == ["exec", "--help"]:
    print("no sandbox support in this build")
    raise SystemExit(0)
raise SystemExit("unexpected invocation: " + repr(sys.argv))
"""


def _write_executable(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


class CodexTierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.bin_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hard_tier_when_sandbox_flag_present_on_supported_os(self) -> None:
        codex = _write_executable(self.bin_dir / "codex", FAKE_CODEX_WITH_SANDBOX)
        decision = guard.determine_codex_tier(codex_bin=str(codex), platform_system="Darwin")
        self.assertEqual(decision.tier, guard.EnforcementTier.HARD)
        self.assertEqual(decision.mechanism, "codex-workspace-write-sandbox")

    def test_detection_only_when_binary_missing(self) -> None:
        decision = guard.determine_codex_tier(codex_bin=str(self.bin_dir / "does-not-exist"), platform_system="Darwin")
        self.assertEqual(decision.tier, guard.EnforcementTier.DETECTION_ONLY)
        self.assertTrue(decision.mechanism.startswith("detection-only:codex-binary-not-found"))

    def test_detection_only_on_unsupported_os(self) -> None:
        codex = _write_executable(self.bin_dir / "codex", FAKE_CODEX_WITH_SANDBOX)
        decision = guard.determine_codex_tier(codex_bin=str(codex), platform_system="Windows")
        self.assertEqual(decision.tier, guard.EnforcementTier.DETECTION_ONLY)
        self.assertIn("unsupported-os", decision.mechanism)

    def test_detection_only_when_sandbox_flag_unsupported(self) -> None:
        codex = _write_executable(self.bin_dir / "codex", FAKE_CODEX_WITHOUT_SANDBOX)
        decision = guard.determine_codex_tier(codex_bin=str(codex), platform_system="Linux")
        self.assertEqual(decision.tier, guard.EnforcementTier.DETECTION_ONLY)
        self.assertIn("sandbox-flag-unsupported", decision.mechanism)

    def test_require_hard_fails_closed_when_unavailable(self) -> None:
        with self.assertRaises(delegation_containment.ContainmentError):
            guard.determine_codex_tier(
                codex_bin=str(self.bin_dir / "does-not-exist"), require_hard=True, platform_system="Darwin"
            )

    def test_require_hard_does_not_raise_when_available(self) -> None:
        codex = _write_executable(self.bin_dir / "codex", FAKE_CODEX_WITH_SANDBOX)
        decision = guard.determine_codex_tier(codex_bin=str(codex), require_hard=True, platform_system="Linux")
        self.assertEqual(decision.tier, guard.EnforcementTier.HARD)

    def test_build_codex_argv_hard_tier_restricts_writable_root(self) -> None:
        argv = guard.build_codex_argv("codex", Path("/worktrees/agent-a"), guard.EnforcementTier.HARD, ["do it"])
        self.assertIn("--sandbox", argv)
        self.assertIn("workspace-write", argv)
        self.assertIn("--cd", argv)
        self.assertIn("/worktrees/agent-a", argv)
        self.assertNotIn("--add-dir", argv)
        self.assertEqual(argv[-1], "do it")

    def test_build_codex_argv_detection_only_tier_omits_sandbox_flags(self) -> None:
        argv = guard.build_codex_argv("codex", Path("/worktrees/agent-a"), guard.EnforcementTier.DETECTION_ONLY, ["do it"])
        self.assertNotIn("--sandbox", argv)
        self.assertNotIn("--cd", argv)


class ClaudeTierTests(unittest.TestCase):
    def test_shell_enabled_forces_detection_only(self) -> None:
        decision = guard.determine_claude_tier(shell_enabled=True)
        self.assertEqual(decision.tier, guard.EnforcementTier.DETECTION_ONLY)
        self.assertIn("claude-shell-capable", decision.mechanism)

    def test_structured_only_session_is_hard(self) -> None:
        decision = guard.determine_claude_tier(shell_enabled=False)
        self.assertEqual(decision.tier, guard.EnforcementTier.HARD)
        self.assertEqual(decision.mechanism, "claude-structured-write-hook")


class ClaudeGuardHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.assigned_worktree = Path(self.tmp.name) / "assigned"
        self.assigned_worktree.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _decide(self, tool_input: dict) -> dict:
        written = guard.write_claude_guard(self.assigned_worktree)
        self.assertTrue(written.settings_path.exists())
        settings = json.loads(written.settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["matcher"], "Write|Edit|NotebookEdit")
        payload = {"tool_name": "Write", "tool_input": tool_input}
        completed = subprocess.run(
            [sys.executable, str(written.hook_script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout)["hookSpecificOutput"]

    def test_allows_write_inside_assigned_worktree(self) -> None:
        target = self.assigned_worktree / "src" / "file.py"
        decision = self._decide({"file_path": str(target)})
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_denies_write_outside_assigned_worktree(self) -> None:
        outside = Path(self.tmp.name) / "integration" / "escape.py"
        decision = self._decide({"file_path": str(outside)})
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn(str(outside), decision["permissionDecisionReason"])

    def test_relative_path_resolved_against_assigned_worktree(self) -> None:
        decision = self._decide({"file_path": "nested/inside.py"})
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_path_traversal_outside_assigned_worktree_is_denied(self) -> None:
        decision = self._decide({"file_path": "../../etc/passwd"})
        self.assertEqual(decision["permissionDecision"], "deny")

    def test_notebook_path_key_is_honored(self) -> None:
        target = self.assigned_worktree / "nb.ipynb"
        decision = self._decide({"notebook_path": str(target)})
        self.assertEqual(decision["permissionDecision"], "allow")

    def test_tool_input_without_recognized_target_key_allows(self) -> None:
        decision = self._decide({"some_other_field": "value"})
        self.assertEqual(decision["permissionDecision"], "allow")


class GuardedDelegationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.integration = Path(self.tmp.name) / "integration"
        self.integration.mkdir()
        git("init", "-b", "main", cwd=self.integration)
        git("config", "user.email", "test@example.com", cwd=self.integration)
        git("config", "user.name", "Guard Test", cwd=self.integration)
        (self.integration / "tracked.txt").write_text("initial\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)
        git("commit", "-m", "initial", cwd=self.integration)

        # Friction-recording scaffolding is committed, not left dirty/untracked --
        # it is fixture infrastructure standing in for a real project's committed
        # scripts/, not another agent's in-progress uncommitted work.
        scripts_dir = self.integration / "scripts"
        scripts_dir.mkdir()
        for name in ("_platform_common.py", "agent_friction.py"):
            (scripts_dir / name).write_bytes((SCRIPT_ROOT / name).read_bytes())
        (self.integration / ".dev-platform.toml").write_text(
            'main_branch = "main"\nharness_mode = "platform"\n\n[paths]\n'
            'friction_log = ".claude/agent-friction.jsonl"\n'
            'friction_state = ".claude/agent-friction-state.json"\n'
            'friction_reports = ".claude/reports/process-improvement"\n',
            encoding="utf-8",
        )
        git("add", "scripts", ".dev-platform.toml", cwd=self.integration)
        git("commit", "-m", "fixture: friction scaffolding", cwd=self.integration)

        self.worktree = Path(self.tmp.name) / "worktrees" / "agent-a"
        git("worktree", "add", "-b", "agent-a", str(self.worktree), "main", cwd=self.integration)

        self.hard_tier = guard.EnforcementDecision(guard.EnforcementTier.HARD, "test-hard", "test fixture hard tier")
        self.detection_tier = guard.EnforcementDecision(
            guard.EnforcementTier.DETECTION_ONLY, "test-detection-only", "test fixture detection-only tier"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _friction_log(self) -> Path:
        return self.integration / ".claude" / "agent-friction.jsonl"

    def test_writer_inside_assigned_worktree_succeeds_with_no_violation(self) -> None:
        script = self.worktree / "write_inside.py"
        script.write_text(
            "from pathlib import Path\nPath('output.txt').write_text('ok\\n', encoding='utf-8')\n", encoding="utf-8"
        )
        result = guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.hard_tier,
        )
        self.assertTrue(result.launched)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.violation)
        self.assertTrue((self.worktree / "output.txt").exists())
        self.assertFalse(self._friction_log().exists())

    def test_writer_escaping_into_integration_root_is_a_violation_and_records_friction(self) -> None:
        escape_target = self.integration / "escaped.txt"
        script = self.worktree / "escape.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(escape_target)!r}).write_text('escaped\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        result = guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.hard_tier,
            task="test escape",
        )
        self.assertTrue(result.violation)
        self.assertIn("escaped.txt", result.message)
        self.assertTrue(escape_target.exists())  # never auto-cleaned
        self.assertTrue(self._friction_log().exists())
        self.assertIn("delegated-write-containment-violation", self._friction_log().read_text(encoding="utf-8"))

    def test_detection_only_refuses_to_launch_over_dirty_integration(self) -> None:
        (self.integration / "someone-elses-work.txt").write_text("in progress\n", encoding="utf-8")
        marker = self.worktree / "child-ran.marker"
        script = self.worktree / "should_not_run.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(delegation_containment.ContainmentError, "detection-only delegation"):
            guard.run_guarded_delegation(
                integration_root=self.integration,
                assigned_worktree=self.worktree,
                argv=[sys.executable, str(script)],
                tier_decision=self.detection_tier,
            )
        self.assertFalse(marker.exists())  # the child must never have launched
        self.assertTrue((self.integration / "someone-elses-work.txt").exists())  # untouched, not cleaned up

    def test_detection_only_over_clean_integration_launches_and_succeeds(self) -> None:
        script = self.worktree / "write_inside.py"
        script.write_text(
            "from pathlib import Path\nPath('output.txt').write_text('ok\\n', encoding='utf-8')\n", encoding="utf-8"
        )
        result = guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.detection_tier,
        )
        self.assertFalse(result.violation)
        self.assertTrue((self.worktree / "output.txt").exists())

    def test_child_nonzero_exit_still_runs_post_check_and_reports_returncode(self) -> None:
        script = self.worktree / "fail.py"
        script.write_text("raise SystemExit(7)\n", encoding="utf-8")
        result = guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.hard_tier,
        )
        self.assertTrue(result.launched)
        self.assertEqual(result.returncode, 7)
        self.assertFalse(result.violation)  # nothing touched integration despite the failure

    def test_child_nonzero_exit_with_escape_reports_both_failure_and_violation(self) -> None:
        escape_target = self.integration / "escaped-on-failure.txt"
        script = self.worktree / "fail_and_escape.py"
        script.write_text(
            "from pathlib import Path\n"
            f"Path({str(escape_target)!r}).write_text('oops\\n', encoding='utf-8')\n"
            "raise SystemExit(3)\n",
            encoding="utf-8",
        )
        result = guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.hard_tier,
        )
        self.assertEqual(result.returncode, 3)
        self.assertTrue(result.violation)
        self.assertTrue(self._friction_log().exists())

    def test_child_timeout_cancellation_still_runs_post_check(self) -> None:
        script = self.worktree / "sleep_forever.py"
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        with self.assertRaises(guard.GuardedChildError) as ctx:
            guard.run_guarded_delegation(
                integration_root=self.integration,
                assigned_worktree=self.worktree,
                argv=[sys.executable, str(script)],
                tier_decision=self.hard_tier,
                timeout=1,
            )
        result = ctx.exception.result
        self.assertTrue(result.launched)  # it did start before being cancelled
        self.assertIsNone(result.returncode)
        self.assertFalse(result.violation)
        self.assertIsNotNone(result.containment)

    def test_child_exec_failure_never_launched_still_runs_post_check(self) -> None:
        with self.assertRaises(guard.GuardedChildError) as ctx:
            guard.run_guarded_delegation(
                integration_root=self.integration,
                assigned_worktree=self.worktree,
                argv=[str(self.worktree / "does-not-exist-binary")],
                tier_decision=self.hard_tier,
            )
        result = ctx.exception.result
        self.assertFalse(result.launched)
        self.assertIsNotNone(result.containment)

    def test_never_auto_stashes_resets_or_cleans_integration_state(self) -> None:
        (self.integration / "someone-elses-work.txt").write_text("in progress\n", encoding="utf-8")
        escape_target = self.integration / "escaped.txt"
        script = self.worktree / "escape.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(escape_target)!r}).write_text('escaped\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        guard.run_guarded_delegation(
            integration_root=self.integration,
            assigned_worktree=self.worktree,
            argv=[sys.executable, str(script)],
            tier_decision=self.hard_tier,
        )
        status = git("status", "--porcelain", cwd=self.integration).stdout
        self.assertIn("someone-elses-work.txt", status)
        self.assertIn("escaped.txt", status)
        self.assertTrue(escape_target.exists())

    def test_rejects_unregistered_assigned_worktree_before_launch(self) -> None:
        unregistered = Path(self.tmp.name) / "not-a-worktree"
        unregistered.mkdir()
        marker = unregistered / "ran.marker"
        script = unregistered / "should_not_run.py"
        script.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )
        with self.assertRaises(delegation_containment.ContainmentError):
            guard.run_guarded_delegation(
                integration_root=self.integration,
                assigned_worktree=unregistered,
                argv=[sys.executable, str(script)],
                tier_decision=self.hard_tier,
            )
        self.assertFalse(marker.exists())


class CliSmokeTests(unittest.TestCase):
    """End-to-end check that the CLI wiring (argument parsing, tier resolution,
    argv construction) reaches the same guarded core exercised by the tests above."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.integration = Path(self.tmp.name) / "integration"
        self.integration.mkdir()
        git("init", "-b", "main", cwd=self.integration)
        git("config", "user.email", "test@example.com", cwd=self.integration)
        git("config", "user.name", "CLI Smoke Test", cwd=self.integration)
        (self.integration / "tracked.txt").write_text("initial\n", encoding="utf-8")
        git("add", "tracked.txt", cwd=self.integration)
        git("commit", "-m", "initial", cwd=self.integration)
        self.worktree = Path(self.tmp.name) / "worktrees" / "agent-a"
        git("worktree", "add", "-b", "agent-a", str(self.worktree), "main", cwd=self.integration)
        self.bin_dir = Path(self.tmp.name) / "bin"
        self.bin_dir.mkdir()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_codex_subcommand_end_to_end_with_fake_hard_sandbox_binary(self) -> None:
        fake_codex = _write_executable(
            self.bin_dir / "codex",
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "from pathlib import Path\n"
            "if sys.argv[1:3] == ['exec', '--help']:\n"
            "    print('--sandbox workspace-write --cd')\n"
            "    raise SystemExit(0)\n"
            "if sys.argv[1] == 'exec':\n"
            "    Path('cli-output.txt').write_text('ok\\n', encoding='utf-8')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit('unexpected: ' + repr(sys.argv))\n",
        )
        argv = [
            sys.executable,
            str(SCRIPT_ROOT / "delegated_write_guard.py"),
            "codex",
            "--integration-root",
            str(self.integration),
            "--assigned-worktree",
            str(self.worktree),
            "--codex-bin",
            str(fake_codex),
            "--",
            "do the task",
        ]
        completed = subprocess.run(argv, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("hard", completed.stderr)
        self.assertTrue((self.worktree / "cli-output.txt").exists())


if __name__ == "__main__":
    unittest.main()
