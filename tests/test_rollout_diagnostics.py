from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
SELECTOR = ROOT / "template" / "scripts" / "select_checks.py"


class RolloutDiagnosticsTests(unittest.TestCase):
    def test_prepare_surfaces_blocker_and_preserves_exit_status(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("rc=${PIPESTATUS[0]}", text)
        self.assertIn("::error title=Managed rollout blocked::", text)
        self.assertIn('exit "$rc"', text)
        self.assertNotIn("continue-on-error: true", text)

    def test_selected_checks_emit_reserved_command_marker(self) -> None:
        text = SELECTOR.read_text(encoding="utf-8")
        self.assertIn('print(f"DEV_PLATFORM_CHECK_COMMAND: {command}", flush=True)', text)

    def test_diagnostic_prefers_stable_blocker_then_reserved_check_marker(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("grep -F 'Managed rollout: BLOCKED:'", text)
        self.assertIn("grep -F 'DEV_PLATFORM_CHECK_COMMAND:'", text)
        self.assertIn('blocker="command failed (exit $rc): ${check_marker#DEV_PLATFORM_CHECK_COMMAND: }"', text)
        self.assertNotIn("grep -E '^\\+ '", text)
        self.assertNotIn("\\[fail\\]|Error:|ERROR:", text)

    def test_failed_prepare_cannot_push_or_open_pr(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        condition = "steps.pending.outputs.found != 'true' && steps.prepare.outputs.status == 'updated'"
        self.assertGreaterEqual(text.count(condition), 2)

    def test_rollout_branch_contract_remains_exact_version_service_branch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('branch="dev-platform/rollout-${VERSION}"', text)
        self.assertNotIn("agent/rollout-", text)


if __name__ == "__main__":
    unittest.main()
