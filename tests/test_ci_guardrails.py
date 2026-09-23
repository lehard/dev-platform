from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RUFF_COMMAND = "python3 -m ruff check scripts template/scripts tests"
WORKFLOW_TIMEOUTS = {
    "adopt-project.yml": {"adopt": 30},
    "ci.yml": {"validate": 45},
    "platform-health-review.yml": {"publish-report": 10, "notify": 5},
    "project-ci.yml": {"checks": 45},
    "publish-version.yml": {"publish": 15},
    "reconcile-stale-rollouts.yml": {"plan": 10, "reconcile": 25},
    "rollout.yml": {"plan": 15, "rollout": 35},
}


class CiGuardrailTests(unittest.TestCase):
    def test_ruff_gate_is_narrow_and_locally_selectable(self) -> None:
        config = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["lint"]["select"], ["E9", "F811", "F821", "F822", "F823"])
        self.assertNotIn("per-file-ignores", config["lint"])

        checks = tomllib.loads((ROOT / "dev-platform" / "checks.toml").read_text(encoding="utf-8"))
        self.assertIn(RUFF_COMMAND, checks["settings"]["full_commands"])
        self.assertIn(RUFF_COMMAND, checks["checks"]["python"]["commands"])

        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('python3 -m pip install "ruff==0.11.13"', ci)
        self.assertIn(RUFF_COMMAND, ci)

    def test_ruff_reports_undefined_name_with_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "broken.py"
            source.write_text("print(missing_name)\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "ruff.toml"), str(source)],
                capture_output=True, text=True, check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("F821", result.stdout)
        self.assertIn("broken.py:1:7", result.stdout)

    def test_authored_workflows_have_explicit_permissions_and_deadlines(self) -> None:
        workflows = ROOT / ".github" / "workflows"
        for filename, expected_timeouts in WORKFLOW_TIMEOUTS.items():
            with self.subTest(workflow=filename):
                workflow = yaml.safe_load((workflows / filename).read_text(encoding="utf-8"))
                self.assertIsInstance(workflow.get("permissions"), dict)
                if filename in {"ci.yml", "project-ci.yml"}:
                    self.assertEqual(workflow["permissions"], {"contents": "read"})
                if filename == "reconcile-stale-rollouts.yml":
                    self.assertEqual(workflow["jobs"]["reconcile"]["permissions"], {"contents": "read", "issues": "write"})
                for job_name, expected_timeout in expected_timeouts.items():
                    with self.subTest(job=job_name):
                        job = workflow["jobs"][job_name]
                        self.assertEqual(job.get("timeout-minutes"), expected_timeout)
                        self.assertLess(expected_timeout, 360)

    def test_generated_workflows_keep_token_and_timeout_bounds(self) -> None:
        generated = ROOT / "template" / ".github" / "workflows"
        project_ci = (generated / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", project_ci)
        self.assertIn("  platform-ci:\n    runs-on: ubuntu-latest\n    timeout-minutes: 90", project_ci)

        labels = (generated / "process-health-labels.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  issues: write", labels)
        self.assertIn("  provision:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5", labels)

    def test_agentic_sources_keep_declared_permissions_and_time_limits(self) -> None:
        for name in (
            "process-issue-triage",
            "weekly-process-backlog-review",
            "architecture-health-review",
        ):
            with self.subTest(workflow=name):
                source = (ROOT / ".github" / "workflows" / f"{name}.md").read_text(encoding="utf-8")
                frontmatter = source.split("---", 2)[1]
                workflow = yaml.safe_load(frontmatter)
                self.assertIsInstance(workflow.get("permissions"), dict)
                self.assertIsInstance(workflow.get("timeout-minutes"), int)
                self.assertLess(workflow["timeout-minutes"], 360)


if __name__ == "__main__":
    unittest.main()
