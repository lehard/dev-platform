from __future__ import annotations

import importlib.util
import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("platform_doctor", SCRIPTS / "platform_doctor.py")
assert SPEC and SPEC.loader
platform_doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_doctor)


class RenderedWorkflowModeTests(unittest.TestCase):
    def _root(self, workflow: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        path = root / ".github" / "workflows"
        path.mkdir(parents=True)
        (path / "dev-platform.yml").write_text(workflow, encoding="utf-8")
        return root, tmp

    def test_pr_mode_rejects_stale_push_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  push:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "pr"}, failures)
        self.assertEqual(failures[0], 1)

    def test_pr_mode_accepts_pr_only_render(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "pr"}, failures)
        self.assertEqual(failures[0], 0)

    def test_direct_mode_requires_push_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "direct"}, failures)
        self.assertEqual(failures[0], 1)

    def test_direct_mode_accepts_push_health_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  push:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "direct"}, failures)
        self.assertEqual(failures[0], 0)

    def test_backlog_config_allows_legacy_renders_but_rejects_partial_authoring_contract(self) -> None:
        failures = [0]
        platform_doctor.check_development_backlog_config({}, failures)
        self.assertEqual(failures[0], 0)
        platform_doctor.check_development_backlog_config(
            {"development_backlog": {"repository": "invalid", "project_label": "dev-platform", "default_priority": "P9"}}, failures
        )
        self.assertEqual(failures[0], 5)


GITHUB_HOSTED_WORKFLOW = "jobs:\n  platform-ci:\n    runs-on: ubuntu-latest\n    timeout-minutes: 90\n    steps:\n      - run: true\n"
REPAIR_STEP = (
    "      - name: Repair shared-workspace permissions on self-hosted runners\n"
    "        run: python3 scripts/shared_workspace.py fix\n"
)


DOCTOR_STEP = "      - run: python3 scripts/platform_doctor.py\n"


def self_hosted_workflow(runs_on: str, repair: bool = True) -> str:
    return (
        f"jobs:\n  platform-ci:\n    runs-on: {runs_on}\n    timeout-minutes: 90\n    steps:\n      - run: true\n"
        + (REPAIR_STEP if repair else "")
        + DOCTOR_STEP
        + "  other:\n    runs-on: ubuntu-latest\n"
    )


class CiRunnerAgreementTests(unittest.TestCase):
    def _check(self, answers: str | None, workflow: str, config: dict | None = None, provision: str | None = "same") -> int:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "dev-platform.yml").write_text(workflow, encoding="utf-8")
            ci_match = platform_doctor.PLATFORM_CI_RUNS_ON_RE.search(workflow)
            if provision is not None and ci_match is not None:
                # "same" mirrors the platform-ci runner so a test isolates the platform-ci comparison.
                runner = ci_match.group(1) if provision == "same" else provision
                (root / ".github" / "workflows" / "process-health-labels.yml").write_text(
                    f"jobs:\n  provision:\n    runs-on: {runner}\n    timeout-minutes: 5\n", encoding="utf-8")
            if answers is not None:
                (root / ".copier-answers.yml").write_text(answers, encoding="utf-8")
            failures = [0]
            platform_doctor.check_ci_runner_agreement(root, config or {"scm_provider": "github", "platform_version": "1.0.0"}, failures)
            return failures[0]

    def test_github_hosted_agreement(self) -> None:
        self.assertEqual(self._check("ci_runner: github-hosted\n", GITHUB_HOSTED_WORKFLOW), 0)

    def test_missing_answer_fails(self) -> None:
        self.assertEqual(self._check("_commit: v1.0.0\n", GITHUB_HOSTED_WORKFLOW), 1)
        self.assertEqual(self._check(None, GITHUB_HOSTED_WORKFLOW), 1)

    def test_unknown_answer_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: shared\n", GITHUB_HOSTED_WORKFLOW), 1)

    def test_self_hosted_single_and_multiple_labels_agree(self) -> None:
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", self_hosted_workflow("alters")), 0)
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: a, b\n", self_hosted_workflow('["a", "b"]')), 0)

    def test_runner_mismatch_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", self_hosted_workflow("ubuntu-latest"), provision="alters"), 1)
        self.assertEqual(self._check("ci_runner: github-hosted\n", self_hosted_workflow("alters", repair=False), provision="ubuntu-latest"), 1)

    def test_invalid_labels_fail_naming_ci_runner_labels(self) -> None:
        for labels in ("''", "'a,,b'", "'a b'", "'a,a'", "'a;b'"):
            with self.subTest(labels=labels):
                self.assertEqual(self._check(f"ci_runner: self-hosted\nci_runner_labels: {labels}\n", self_hosted_workflow("a")), 1)
        self.assertEqual(self._check("ci_runner: self-hosted\n", self_hosted_workflow("a")), 1)

    def test_provision_runner_mismatch_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", self_hosted_workflow("alters"), provision="ubuntu-latest"), 1)
        self.assertEqual(self._check("ci_runner: github-hosted\n", GITHUB_HOSTED_WORKFLOW, provision="alters"), 1)

    def test_missing_provision_workflow_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: github-hosted\n", GITHUB_HOSTED_WORKFLOW, provision=None), 1)

    def test_repair_step_with_another_command_or_a_condition_fails(self) -> None:
        answers = "ci_runner: self-hosted\nci_runner_labels: alters\n"
        for changed in (REPAIR_STEP.replace("python3 scripts/shared_workspace.py fix", "echo skipped"),
                        REPAIR_STEP + "        if: false\n",
                        REPAIR_STEP + "        continue-on-error: true\n"):
            with self.subTest(step=changed):
                self.assertEqual(self._check(answers, self_hosted_workflow("alters").replace(REPAIR_STEP, changed)), 1)

    def test_wrapped_label_answer_is_read_whole(self) -> None:
        labels = ["runner-label-0", "runner-label-1", "runner-label-2"]
        workflow = self_hosted_workflow(json.dumps(labels))
        for answers in ("ci_runner: self-hosted\nci_runner_labels: runner-label-0, runner-label-1,\n  runner-label-2\n",
                        "ci_runner: self-hosted\nci_runner_labels: 'runner-label-0, runner-label-1,\n  runner-label-2'\n"):
            with self.subTest(answers=answers):
                self.assertEqual(self._check(answers, workflow), 0)

    def test_block_scalar_answer_fails_explicitly(self) -> None:
        with self.assertRaisesRegex(SystemExit, "block scalar"):
            self._check("ci_runner: self-hosted\nci_runner_labels: |\n  alters\n", self_hosted_workflow("alters"))

    def test_label_must_keep_its_rendered_form(self) -> None:
        # A plain-safe single label renders plain; an ambiguous one renders quoted. Only the rendered form agrees.
        answers = "ci_runner: self-hosted\nci_runner_labels: alters\n"
        self.assertEqual(self._check(answers, self_hosted_workflow('"alters"'), provision="alters"), 1)
        self.assertEqual(self._check(answers, self_hosted_workflow("alters"), provision='"alters"'), 1)
        for label, rendered in (("true", '"true"'), ("Yes", '"Yes"'), ("123", '"123"'), ("null", '"null"'), ("1linux", '"1linux"'),
                                ("self-hosted", "self-hosted"), ("macOS_arm.64", "macOS_arm.64")):
            with self.subTest(label=label):
                labelled = f"ci_runner: self-hosted\nci_runner_labels: '{label}'\n"
                self.assertEqual(self._check(labelled, self_hosted_workflow(rendered), provision=rendered), 0)
                other = rendered.strip('"') if rendered.startswith('"') else f'"{rendered}"'
                self.assertEqual(self._check(labelled, self_hosted_workflow(other), provision=other), 2)

    def test_repair_step_after_platform_doctor_fails(self) -> None:
        workflow = self_hosted_workflow("alters", repair=False).replace(DOCTOR_STEP, DOCTOR_STEP + REPAIR_STEP)
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", workflow), 1)

    def test_repair_step_outside_platform_ci_does_not_count(self) -> None:
        workflow = self_hosted_workflow("alters", repair=False) + "    steps:\n" + REPAIR_STEP
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", workflow), 1)
        self.assertEqual(self._check("ci_runner: github-hosted\n", GITHUB_HOSTED_WORKFLOW + "  other:\n    steps:\n" + REPAIR_STEP), 0)

    def test_self_hosted_without_repair_step_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", self_hosted_workflow("alters", repair=False)), 1)

    def test_github_hosted_with_repair_step_fails(self) -> None:
        self.assertEqual(self._check("ci_runner: github-hosted\n", self_hosted_workflow("ubuntu-latest")), 1)

    def test_runs_on_of_other_jobs_is_not_compared(self) -> None:
        self.assertEqual(self._check("ci_runner: self-hosted\nci_runner_labels: alters\n", self_hosted_workflow("alters")), 0)

    def test_gitlab_and_source_are_unaffected(self) -> None:
        self.assertEqual(self._check(None, "", {"scm_provider": "gitlab", "platform_version": "1.0.0"}), 0)
        self.assertEqual(self._check(None, GITHUB_HOSTED_WORKFLOW, {"scm_provider": "github", "platform_version": "source"}), 0)


if __name__ == "__main__":
    unittest.main()
