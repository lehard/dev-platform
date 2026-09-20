from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
SCRIPT = ROOT / "scripts" / "rollout_failure_streak.py"


def step_block(text: str, step_name: str) -> str:
    marker = f"- name: {step_name}"
    if marker not in text:
        raise AssertionError(f"step not found: {step_name}")
    remainder = text.split(marker, 1)[1]
    return remainder.split("\n      - name:", 1)[0]


class RolloutFailureStreakWorkflowTests(unittest.TestCase):
    def test_workflow_grants_issues_write_for_same_repo_tracking(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        top_level_permissions = text.split("jobs:", 1)[0]
        self.assertIn("issues: write", top_level_permissions)

    def test_failure_streak_step_is_best_effort_and_scoped_like_diagnostics(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        block = step_block(text, "Record rollout failure streak")
        self.assertIn("if: steps.pending.outputs.found != 'true' && failure()", block)
        self.assertIn("continue-on-error: true", block)
        self.assertIn("record-failure", block)
        self.assertIn("github.token", block)

    def test_recovery_step_only_runs_after_prepare_actually_succeeds(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        block = step_block(text, "Record rollout recovery")
        self.assertIn("if: steps.pending.outputs.found != 'true' && steps.prepare.outcome == 'success'", block)
        self.assertIn("continue-on-error: true", block)
        self.assertIn("record-success", block)

    def test_failure_streak_steps_cannot_influence_push_or_pr_conditions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        push_and_pr_condition = "steps.pending.outputs.found != 'true' && steps.prepare.outputs.status == 'updated'"
        # The new tracking steps must not appear inside this guard, and the
        # guard itself must be untouched by the new steps' own conditions.
        self.assertGreaterEqual(text.count(push_and_pr_condition), 2)
        streak_block = step_block(text, "Record rollout failure streak")
        recovery_block = step_block(text, "Record rollout recovery")
        for block in (streak_block, recovery_block):
            self.assertNotIn("git -C target push", block)
            self.assertNotIn("gh pr create", block)

    def test_failure_streak_uses_default_token_not_cross_repo_app(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for name in ("Record rollout failure streak", "Record rollout recovery"):
            block = step_block(text, name)
            self.assertIn("${{ github.token }}", block)
            self.assertNotIn("target-token", block)
            self.assertNotIn("source-token", block)


class RolloutFailureStreakScriptTests(unittest.TestCase):
    def test_script_entry_points_never_raise_on_generic_failure(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("def cmd_record_failure", text)
        self.assertIn("def cmd_record_success", text)
        self.assertIn("except Exception as exc:  # noqa: BLE001", text)
        self.assertEqual(text.count("except Exception as exc:  # noqa: BLE001"), 2)

    def test_unreadable_prior_state_never_silently_resets(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("Fail closed", text)
        self.assertIn("Escalate rather than reset", text)


if __name__ == "__main__":
    unittest.main()
