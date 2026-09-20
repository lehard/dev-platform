"""Regression tests for the three defects found by the real v1.4.21 managed rollout.

Unit tests of the Python helpers (`tests/test_rollout_supersession.py`,
`tests/test_rollout_failure_streak.py`) already proved those functions'
*semantics*. None of them proved that the *shell/CLI orchestration* embedded
in the workflow YAML is actually valid, or that a script path resolves under
the job's real multi-checkout layout -- that gap is exactly what let a green
Platform CI coexist with a rollout job that could never have succeeded.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLOUT_WORKFLOW = ROOT / ".github" / "workflows" / "rollout.yml"
RECONCILE_WORKFLOW = ROOT / ".github" / "workflows" / "reconcile-stale-rollouts.yml"

# Every root-level platform-owned script that a workflow might invoke.
PLATFORM_SCRIPT_NAMES = sorted(p.name for p in (ROOT / "scripts").glob("*.py"))

BARE_SCRIPT_REF_RE = re.compile(r"(?<!platform/)\bscripts/[A-Za-z_]+\.py\b")


def job_body(workflow_text: str, job_name: str) -> str:
    """Return the text of one top-level job, up to the next 2-space-indented key or EOF."""
    marker = f"\n  {job_name}:\n"
    if marker not in workflow_text:
        raise AssertionError(f"job not found: {job_name}")
    remainder = workflow_text.split(marker, 1)[1]
    match = re.search(r"\n  [A-Za-z_-]+:\n", remainder)
    return remainder[: match.start()] if match else remainder


class NoFragileGhJqArgPatternTests(unittest.TestCase):
    """Regression for defect 1: `gh ... --jq <expr> --arg ...` is not valid `gh` usage."""

    def test_no_workflow_combines_jq_flag_with_a_following_arg_flag(self) -> None:
        for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"--jq\s+--arg\b", f"{workflow.name} still passes --arg directly to gh's --jq flag")

    def test_pending_pr_detection_uses_the_structured_helper(self) -> None:
        text = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
        block = job_body(text, "rollout")
        self.assertIn("rollout_supersession.py find-pending", block)
        self.assertNotIn("gh pr list", block)


class RolloutJobScriptPathTests(unittest.TestCase):
    """Regression for defect 2: the `rollout` job has no plain root checkout.

    `platform/` = immutable release checkout, `target/` = downstream checkout.
    Every platform-owned root-level script invoked from this job must resolve
    under `platform/`, proven here rather than only by a passing run.
    """

    def test_every_script_reference_in_the_rollout_job_is_platform_prefixed(self) -> None:
        text = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
        block = job_body(text, "rollout")
        bare_references = BARE_SCRIPT_REF_RE.findall(block)
        self.assertEqual(bare_references, [], f"bare (non-platform/-prefixed) script references in the rollout job: {bare_references}")

    def test_rollout_job_actually_references_every_expected_platform_helper(self) -> None:
        # Guards against the check above passing merely because a step was
        # deleted rather than fixed.
        text = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
        block = job_body(text, "rollout")
        for name in ("rollout_project.py", "rollout_diagnostic.py", "rollout_failure_streak.py", "rollout_supersession.py"):
            with self.subTest(script=name):
                self.assertIn(f"platform/scripts/{name}", block)

    def test_plan_job_correctly_keeps_bare_paths_for_its_own_root_checkout(self) -> None:
        # The `plan` job has a plain root checkout (no platform/target split),
        # so a bare reference there is correct and must not be flagged.
        text = ROLLOUT_WORKFLOW.read_text(encoding="utf-8")
        block = job_body(text, "plan")
        self.assertIn("scripts/managed_projects.py", block)
        self.assertNotIn("platform/scripts/managed_projects.py", block)


class ReconcileStaleRolloutsWorkflowTests(unittest.TestCase):
    """The maintenance workflow has its own single plain checkout at the job root."""

    def test_reconcile_workflow_uses_bare_path_with_new_subcommand(self) -> None:
        text = RECONCILE_WORKFLOW.read_text(encoding="utf-8")
        block = job_body(text, "reconcile")
        self.assertIn("scripts/rollout_supersession.py reconcile", block)
        self.assertNotIn("platform/scripts/rollout_supersession.py", block)


if __name__ == "__main__":
    unittest.main()
