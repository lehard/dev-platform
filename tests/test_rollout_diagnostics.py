import sys
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
GENERATED_GATE = ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja"
SELECTOR = ROOT / "template" / "scripts" / "select_checks.py"
PINNED_NODE_VERSION = "24.22.2"
NODE_PINNED_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "ci.yml",
    WORKFLOW,
    ROOT / ".github" / "workflows" / "adopt-project.yml",
    ROOT / ".github" / "workflows" / "project-ci.yml",
    GENERATED_GATE,
)
sys.path.insert(0, str(ROOT / "scripts"))


def node_versions(path: Path) -> list[str]:
    if not path.is_file():
        raise AssertionError(f"Node-pinned workflow is missing: {path}")
    versions = re.findall(r"""node-version:\s*["']?([^"'\s]+)""", path.read_text(encoding="utf-8"))
    if not versions:
        raise AssertionError(f"node-version not found in {path}")
    return versions


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

    def test_every_workflow_pins_the_same_node_version(self) -> None:
        for path in NODE_PINNED_WORKFLOWS:
            with self.subTest(workflow=path.relative_to(ROOT).as_posix()):
                self.assertEqual(set(node_versions(path)), {PINNED_NODE_VERSION})

    def test_missing_node_pinned_workflow_fails_explicitly(self) -> None:
        missing = ROOT / ".github" / "workflows" / "absent.yml"
        with self.assertRaisesRegex(AssertionError, "Node-pinned workflow is missing"):
            node_versions(missing)

    def test_failed_prepare_cannot_push_or_open_pr(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        condition = "steps.pending.outputs.found != 'true' && steps.prepare.outputs.status == 'updated'"
        self.assertGreaterEqual(text.count(condition), 2)

    def test_rollout_branch_contract_remains_exact_version_service_branch(self) -> None:
        # The branch name is now computed by platform-owned Python (used by both
        # rollout_project.py, which creates it, and rollout_supersession.py,
        # which must recognize it) rather than inline workflow shell -- assert
        # the contract against those sources of truth instead of a literal
        # shell expression that no longer appears in the workflow text.
        import rollout_project
        import rollout_supersession

        self.assertEqual(rollout_project.rollout_branch("v1.2.3"), "dev-platform/rollout-v1.2.3")
        self.assertEqual(rollout_supersession.rollout_branch("v1.2.3"), "dev-platform/rollout-v1.2.3")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("agent/rollout-", text)


if __name__ == "__main__":
    unittest.main()
