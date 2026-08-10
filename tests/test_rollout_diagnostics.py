from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"


class RolloutDiagnosticsTests(unittest.TestCase):
    def test_prepare_surfaces_blocker_and_preserves_exit_status(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("rc=${PIPESTATUS[0]}", text)
        self.assertIn("::error title=Managed rollout blocked::", text)
        self.assertIn('exit "$rc"', text)
        self.assertNotIn("continue-on-error: true", text)

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
