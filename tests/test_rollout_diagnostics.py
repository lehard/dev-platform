from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
GENERATED_GATE = ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja"
SELECTOR = ROOT / "template" / "scripts" / "select_checks.py"


def node_version(path: Path) -> str:
    match = re.search(r'node-version: "([^"]+)"', path.read_text(encoding="utf-8"))
    if not match:
        raise AssertionError(f"node-version not found in {path}")
    return match.group(1)


class RolloutDiagnosticsTests(unittest.TestCase):
    def test_prepare_surfaces_blocker_and_preserves_exit_status(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("rc=${PIPESTATUS[0]}", text)
        self.assertIn("::error title=Managed rollout blocked::", text)
        self.assertIn('exit "$rc"', text)
        prepare_block = text.split("Prepare exact-version Copier update", 1)[1]
        prepare_block = prepare_block.split("- name:", 1)[0]
        self.assertNotIn("continue-on-error: true", prepare_block)

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

    def test_rollout_node_matches_generated_platform_gate(self) -> None:
        self.assertEqual(node_version(WORKFLOW), node_version(GENERATED_GATE))
        self.assertEqual(node_version(WORKFLOW), "20.19.0")

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
