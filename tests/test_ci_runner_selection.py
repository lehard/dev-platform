from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("platform_doctor_runner", SCRIPTS / "platform_doctor.py")
assert SPEC and SPEC.loader
platform_doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_doctor)

REPAIR_NAME = "Repair shared-workspace permissions on self-hosted runners"
BASE_DATA = {
    "project_name": "Runner Render",
    "project_slug": "runner-render",
    "project_description": "CI runner render",
    "workflow_profile": "standard",
    "publish_mode": "pr",
}


def copy_source(destination: Path) -> Path:
    # Copier resolves a Git source at a committed ref; render the working tree instead.
    shutil.copytree(
        ROOT, destination,
        ignore=shutil.ignore_patterns(".git", ".claude", "__pycache__", ".venv", "node_modules"),
    )
    return destination


def copier_copy(source: Path, target: Path, extra: dict[str, str], *, vcs_ref: str | None = None) -> None:
    data = {**BASE_DATA, **extra}
    command = ["copier", "copy", "--trust", "--defaults", "--skip-tasks"]
    if vcs_ref:
        command += ["--vcs-ref", vcs_ref]
    for key, value in data.items():
        command += ["--data", f"{key}={value}"]
    subprocess.run([*command, str(source), str(target)], check=True, capture_output=True, text=True)


def load_jobs(target: Path, name: str) -> dict:
    return yaml.safe_load((target / ".github" / "workflows" / name).read_text(encoding="utf-8"))["jobs"]


def step_names(job: dict) -> list[str]:
    return [step.get("name", "") for step in job["steps"]]


@unittest.skipIf(shutil.which("copier") is None, "copier is not installed")
class CiRunnerRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._shared = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._shared.cleanup)
        cls.source = copy_source(Path(cls._shared.name) / "template-source")

    def render(self, name: str, extra: dict[str, str]) -> Path:
        target = Path(self._shared.name) / name
        copier_copy(self.source, target, extra)
        return target

    def test_github_hosted_default_matches_explicit_answer_and_is_unchanged(self) -> None:
        default = self.render("default", {})
        explicit = self.render("explicit", {"ci_runner": "github-hosted"})
        workflow = default / ".github" / "workflows" / "dev-platform.yml"
        self.assertEqual(workflow.read_bytes(), (explicit / ".github" / "workflows" / "dev-platform.yml").read_bytes())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("  platform-ci:\n    runs-on: ubuntu-latest\n    timeout-minutes: 90\n", text)
        self.assertNotIn(REPAIR_NAME, text)
        self.assertEqual(load_jobs(default, "process-health-labels.yml")["provision"]["runs-on"], "ubuntu-latest")

    def test_self_hosted_differs_from_github_hosted_only_by_runner_and_repair_step(self) -> None:
        hosted = (self.render("hosted", {}) / ".github" / "workflows" / "dev-platform.yml").read_text(encoding="utf-8")
        target = self.render("single", {"ci_runner": "self-hosted", "ci_runner_labels": "alters"})
        text = (target / ".github" / "workflows" / "dev-platform.yml").read_text(encoding="utf-8")
        repair = f"      - name: {REPAIR_NAME}\n        run: python3 scripts/shared_workspace.py fix\n\n"
        # A plain-safe single label renders plain: the same bytes as a hand-written `runs-on: alters`.
        self.assertEqual(text.replace(repair, "").replace("runs-on: alters\n", "runs-on: ubuntu-latest\n"), hosted)
        jobs = load_jobs(target, "dev-platform.yml")
        self.assertEqual(jobs["platform-ci"]["runs-on"], "alters")
        names = step_names(jobs["platform-ci"])
        self.assertEqual(names.index(REPAIR_NAME), names.index("Materialize selected capability surfaces") + 1)
        self.assertEqual(names.index("Validate platform contract"), names.index(REPAIR_NAME) + 1)
        self.assertEqual(load_jobs(target, "process-health-labels.yml")["provision"]["runs-on"], "alters")
        self.assertEqual(self.doctor_failures(target), 0)

    def test_self_hosted_multiple_labels_render_flow_list(self) -> None:
        target = self.render("multi", {"ci_runner": "self-hosted", "ci_runner_labels": " self-hosted , linux "})
        self.assertIn('    runs-on: ["self-hosted", "linux"]\n', (target / ".github" / "workflows" / "dev-platform.yml").read_text(encoding="utf-8"))
        self.assertEqual(load_jobs(target, "dev-platform.yml")["platform-ci"]["runs-on"], ["self-hosted", "linux"])
        self.assertEqual(load_jobs(target, "process-health-labels.yml")["provision"]["runs-on"], ["self-hosted", "linux"])

    def test_long_label_list_wrapped_by_copier_passes_the_doctor(self) -> None:
        labels = "self-hosted, linux, production-network, dedicated-platform-validation, company-build-runner"
        target = self.render("long-labels", {"ci_runner": "self-hosted", "ci_runner_labels": labels})
        recorded = (target / ".copier-answers.yml").read_text(encoding="utf-8")
        self.assertEqual(yaml.safe_load(recorded)["ci_runner_labels"], labels)
        self.assertRegex(recorded, r"ci_runner_labels: [^\n]*\n +\S")  # Copier wrapped the answer onto a second line
        self.assertEqual(self.doctor_failures(target), 0)

    def test_yaml_ambiguous_labels_render_as_strings(self) -> None:
        target = self.render("ambiguous", {"ci_runner": "self-hosted", "ci_runner_labels": "true, 123, null"})
        for name, job in (("dev-platform.yml", "platform-ci"), ("process-health-labels.yml", "provision")):
            self.assertEqual(load_jobs(target, name)[job]["runs-on"], ["true", "123", "null"])
        single = self.render("ambiguous-single", {"ci_runner": "self-hosted", "ci_runner_labels": "on"})
        self.assertEqual(load_jobs(single, "dev-platform.yml")["platform-ci"]["runs-on"], "on")
        self.assertEqual(self.doctor_failures(single), 0)

    def test_yaml_ambiguous_single_label_renders_quoted(self) -> None:
        for label in ("true", "123", "null"):
            with self.subTest(label=label):
                target = self.render(f"ambiguous-{label}", {"ci_runner": "self-hosted", "ci_runner_labels": label})
                for name, job in (("dev-platform.yml", "platform-ci"), ("process-health-labels.yml", "provision")):
                    self.assertIn(f'    runs-on: "{label}"\n', (target / ".github" / "workflows" / name).read_text(encoding="utf-8"))
                    self.assertEqual(load_jobs(target, name)[job]["runs-on"], label)
                self.assertEqual(self.doctor_failures(target), 0)

    def test_label_provisioning_uses_curl_without_gh_for_both_runner_kinds(self) -> None:
        for name, extra in (("curl-hosted", {}), ("curl-self", {"ci_runner": "self-hosted", "ci_runner_labels": "alters"})):
            with self.subTest(name=name):
                text = (self.render(name, extra) / ".github" / "workflows" / "process-health-labels.yml").read_text(encoding="utf-8")
                self.assertIn("curl -fsS", text)
                self.assertNotIn("gh api", text)
                self.assertIn("${GH_TOKEN}", text)

    def test_self_hosted_without_labels_fails_rendering(self) -> None:
        target = Path(self._shared.name) / "no-labels"
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            copier_copy(self.source, target, {"ci_runner": "self-hosted", "ci_runner_labels": " "})
        self.assertIn("ci_runner_labels", raised.exception.stderr + raised.exception.stdout)

    def doctor_failures(self, target: Path) -> int:
        failures = [0]
        platform_doctor.check_ci_runner_agreement(target, {"scm_provider": "github", "platform_version": "1.0.0"}, failures)
        return failures[0]


@unittest.skipIf(shutil.which("copier") is None or shutil.which("git") is None, "copier or git is not installed")
class CiRunnerUpdateTests(unittest.TestCase):
    def test_copier_update_preserves_self_hosted_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            source = copy_source(tmp_path / "source")

            def git(cwd: Path, *args: str) -> None:
                subprocess.run(
                    ["git", "-c", "user.name=ci-runner-test", "-c", "user.email=ci-runner-test@example.invalid", *args],
                    cwd=cwd, check=True, capture_output=True, text=True,
                )

            git(source, "init", "-q")
            git(source, "add", "-A")
            git(source, "commit", "-q", "-m", "template v1")
            git(source, "tag", "v1.0.0")
            target = tmp_path / "project"
            copier_copy(source, target, {"ci_runner": "self-hosted", "ci_runner_labels": "alters"}, vcs_ref="v1.0.0")
            git(target, "init", "-q")
            git(target, "add", "-A")
            git(target, "commit", "-q", "-m", "baseline")

            template_file = source / "template" / ".github" / "workflows" / "dev-platform.yml.jinja"
            text = template_file.read_text(encoding="utf-8")
            self.assertIn("timeout-minutes: 90", text)
            template_file.write_text(text.replace("timeout-minutes: 90", "timeout-minutes: 80"), encoding="utf-8")
            git(source, "add", "-A")
            git(source, "commit", "-q", "-m", "template v2")
            git(source, "tag", "v1.0.1")

            subprocess.run(
                ["copier", "update", "--trust", "--defaults", "--skip-tasks", "--vcs-ref", "v1.0.1", "--conflict", "inline", str(target)],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(load_jobs(target, "dev-platform.yml")["platform-ci"]["timeout-minutes"], 80)
            answers = yaml.safe_load((target / ".copier-answers.yml").read_text(encoding="utf-8"))
            self.assertEqual(answers["ci_runner"], "self-hosted")
            self.assertEqual(answers["ci_runner_labels"], "alters")
            for name, job in (("dev-platform.yml", "platform-ci"), ("process-health-labels.yml", "provision")):
                self.assertEqual(load_jobs(target, name)[job]["runs-on"], "alters")
            self.assertIn(REPAIR_NAME, step_names(load_jobs(target, "dev-platform.yml")["platform-ci"]))


def strip_runner_support(source: Path) -> None:
    """Turn a template copy into the pre-feature revision: no runner questions, plain ubuntu-latest."""
    copier_yml = source / "copier.yml"
    text = copier_yml.read_text(encoding="utf-8")
    start = text.index("\nci_runner:\n")
    end = text.index("\nagent_tools:\n")
    copier_yml.write_text(text[:start] + text[end:], encoding="utf-8")
    runs_on = re.compile(r"^(\s+runs-on: )\{\{ .*\}\}$", re.MULTILINE)
    for name in ("dev-platform.yml.jinja", "process-health-labels.yml.jinja"):
        path = source / "template" / ".github" / "workflows" / name
        body = path.read_text(encoding="utf-8")
        # The pre-feature templates: process-health-labels had no first line, dev-platform kept its `{% if %}` line.
        body = re.sub(r"\{% set runner_labels = [^\n]*?-%\}\n|\{% set runner_labels = [^\n]*%\}", "", body)
        body = runs_on.sub(r"\1ubuntu-latest", body)
        body = re.sub(r"\{%- if ci_runner == 'self-hosted' %\}.*?\{%- endif %\}", "", body, flags=re.DOTALL)
        path.write_text(body, encoding="utf-8")
        assert "ci_runner" not in body, name


@unittest.skipIf(shutil.which("copier") is None or shutil.which("git") is None, "copier or git is not installed")
class CiRunnerMigrationTests(unittest.TestCase):
    """Rollout path: a project rendered before the runner questions existed is updated with the rollout's Copier flags."""

    def migrate(self, preseed: dict[str, str] | None, hand_edit: Callable[[Path], None] | None = None) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmp_path = Path(tmp.name).resolve()
        source = copy_source(tmp_path / "source")
        current_copier = (source / "copier.yml").read_text(encoding="utf-8")
        current_workflows = {
            name: (source / "template" / ".github" / "workflows" / name).read_text(encoding="utf-8")
            for name in ("dev-platform.yml.jinja", "process-health-labels.yml.jinja")
        }
        strip_runner_support(source)

        def git(cwd: Path, *args: str) -> None:
            subprocess.run(
                ["git", "-c", "user.name=ci-runner-test", "-c", "user.email=ci-runner-test@example.invalid", *args],
                cwd=cwd, check=True, capture_output=True, text=True,
            )

        git(source, "init", "-q")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "template before runner questions")
        git(source, "tag", "v1.0.0")
        target = tmp_path / "project"
        copier_copy(source, target, {}, vcs_ref="v1.0.0")
        self.assertNotIn("ci_runner", (target / ".copier-answers.yml").read_text(encoding="utf-8"))
        if preseed:
            with (target / ".copier-answers.yml").open("a", encoding="utf-8") as handle:
                for key, value in preseed.items():
                    handle.write(f"{key}: {value}\n")
        git(target, "init", "-q")
        git(target, "add", "-A")
        git(target, "commit", "-q", "-m", "baseline")
        if hand_edit:
            hand_edit(target)
            git(target, "add", "-A")
            git(target, "commit", "-q", "-m", "hand edit")

        (source / "copier.yml").write_text(current_copier, encoding="utf-8")
        for name, body in current_workflows.items():
            (source / "template" / ".github" / "workflows" / name).write_text(body, encoding="utf-8")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "template with runner questions")
        git(source, "tag", "v1.0.1")
        # Same flags as scripts/rollout_project.py copier_update_with_guarded_recopy.
        subprocess.run(
            ["copier", "update", "--trust", "--defaults", "--skip-tasks", "--vcs-ref", "v1.0.1", "--conflict", "rej", str(target)],
            check=True, capture_output=True, text=True,
        )
        return target

    def doctor_failures(self, target: Path) -> int:
        failures = [0]
        platform_doctor.check_ci_runner_agreement(target, {"scm_provider": "github", "platform_version": "1.0.1"}, failures)
        return failures[0]

    def test_update_records_github_hosted_default_for_pre_feature_project(self) -> None:
        target = self.migrate(None)
        answers = yaml.safe_load((target / ".copier-answers.yml").read_text(encoding="utf-8"))
        self.assertEqual(answers["ci_runner"], "github-hosted")
        self.assertEqual(load_jobs(target, "dev-platform.yml")["platform-ci"]["runs-on"], "ubuntu-latest")
        self.assertNotIn(REPAIR_NAME, step_names(load_jobs(target, "dev-platform.yml")["platform-ci"]))
        self.assertEqual(self.doctor_failures(target), 0)

    def test_hand_edited_runner_already_matches_the_target_render(self) -> None:
        """The downstream hand edit plus equivalent answers is byte-identical to the target render.

        Copier still rejects the replayed `ubuntu-latest -> alters` hunks (the target already changed those
        lines), so guarded rollout recovers these paths only through the target-equivalence proof, whose
        precondition is exactly this byte identity of the committed workflows.
        """
        edited: dict[str, str] = {}

        def hand_edit(target: Path) -> None:
            for name in ("dev-platform.yml", "process-health-labels.yml"):
                path = target / ".github" / "workflows" / name
                text = path.read_text(encoding="utf-8")
                self.assertEqual(text.count("runs-on: ubuntu-latest\n"), 1)
                text = text.replace("runs-on: ubuntu-latest\n", "runs-on: alters\n")
                if name == "dev-platform.yml":
                    # As in the downstream edit: the step replaces the redundant blank separator before the doctor.
                    doctor = "\n\n\n      - name: Validate platform contract\n"
                    self.assertEqual(text.count(doctor), 1)
                    text = text.replace(doctor, f"\n\n      - name: {REPAIR_NAME}\n        run: python3 scripts/shared_workspace.py fix\n"
                                        + doctor[2:])
                path.write_text(text, encoding="utf-8")
                edited[name] = text

        target = self.migrate({"ci_runner": "self-hosted", "ci_runner_labels": "alters"}, hand_edit)
        for name, text in edited.items():
            with self.subTest(workflow=name):
                self.assertEqual((target / ".github" / "workflows" / name).read_text(encoding="utf-8"), text)
                self.assertTrue((target / ".github" / "workflows" / f"{name}.rej").exists())
        self.assertEqual(self.doctor_failures(target), 0)

    def test_preseeded_self_hosted_answer_renders_on_update(self) -> None:
        target = self.migrate({"ci_runner": "self-hosted", "ci_runner_labels": "alters"})
        self.assertEqual(load_jobs(target, "dev-platform.yml")["platform-ci"]["runs-on"], "alters")
        self.assertEqual(load_jobs(target, "process-health-labels.yml")["provision"]["runs-on"], "alters")
        self.assertIn(REPAIR_NAME, step_names(load_jobs(target, "dev-platform.yml")["platform-ci"]))
        self.assertEqual(self.doctor_failures(target), 0)


if __name__ == "__main__":
    unittest.main()
