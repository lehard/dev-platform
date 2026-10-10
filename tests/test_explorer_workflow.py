"""Contract tests for the Explorer publication workflow (.github/workflows/explorer.yml)."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "explorer.yml"
BUILD_COMMAND = "python3 scripts/build_explorer.py build --out build/explorer"
PINNED_USES = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+(\.\d+)*$")
EXPECTED_PR_PATHS = {
    "explorer/**",
    "scripts/build_explorer.py",
    "scripts/public_distribution.py",
    "AGENTS.md",
    "README.md",
    "docs/**",
    "openspec/specs/**",
    "dev-platform/capabilities/**",
    "VERSION",
    ".github/workflows/explorer.yml",
}


def load_workflow() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1 parses the bare key `on` as boolean True.
    triggers = workflow.pop(True, None)
    if triggers is None:
        raise AssertionError("explorer.yml has no `on` triggers")
    workflow["on"] = triggers
    return workflow


class ExplorerWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = load_workflow()
        cls.build = cls.workflow["jobs"]["build"]
        cls.deploy = cls.workflow["jobs"]["deploy"]

    def test_jobs_are_exactly_build_and_deploy(self) -> None:
        self.assertEqual(set(self.workflow["jobs"]), {"build", "deploy"})
        self.assertEqual(self.deploy["needs"], "build")

    def test_triggers(self) -> None:
        triggers = self.workflow["on"]
        self.assertEqual(set(triggers), {"pull_request", "push", "workflow_dispatch"})
        self.assertEqual(set(triggers["pull_request"]["paths"]), EXPECTED_PR_PATHS)
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertNotIn("paths", triggers["push"])
        self.assertNotIn("pull_request_target", self.text)

    def test_permissions_are_least_privilege(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertNotIn("permissions", self.build)
        self.assertEqual(
            self.deploy["permissions"], {"contents": "read", "pages": "write", "id-token": "write"}
        )
        self.assertEqual(self.deploy["environment"]["name"], "github-pages")
        self.assertEqual(self.deploy["environment"]["url"], "${{ steps.deployment.outputs.page_url }}")

    def test_every_action_is_sha_pinned_with_version_comment(self) -> None:
        uses_lines = [
            line.split("uses:", 1)[1].strip()
            for line in self.text.splitlines()
            if re.match(r"^\s*(-\s+)?uses:", line)
        ]
        self.assertGreaterEqual(len(uses_lines), 5)
        for entry in uses_lines:
            with self.subTest(uses=entry):
                self.assertRegex(entry, PINNED_USES)
        for job in (self.build, self.deploy):
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")

    def test_deploy_runs_only_for_default_branch_push_or_dispatch(self) -> None:
        condition = self.deploy["if"]
        self.assertIn("github.ref == 'refs/heads/main'", condition)
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("github.event_name == 'workflow_dispatch'", condition)
        self.assertNotIn("pull_request", condition)
        self.assertNotIn("if", self.build)

    def test_pages_artifact_is_uploaded_only_outside_pull_requests(self) -> None:
        uploads = [s for s in self.build["steps"] if s.get("uses", "").startswith("actions/upload-pages-artifact@")]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0]["if"], "github.event_name != 'pull_request'")
        self.assertEqual(uploads[0]["with"]["path"], "build/explorer")

    def test_pages_must_already_be_enabled(self) -> None:
        self.assertNotIn("enablement", self.text)
        configure = [s for s in self.deploy["steps"] if s.get("uses", "").startswith("actions/configure-pages@")]
        self.assertEqual(len(configure), 1)
        self.assertNotIn("with", configure[0])
        deploy_steps = [s for s in self.deploy["steps"] if s.get("uses", "").startswith("actions/deploy-pages@")]
        self.assertEqual(len(deploy_steps), 1)
        self.assertEqual(deploy_steps[0]["id"], "deployment")

    def test_concurrency_never_cancels_a_deploy(self) -> None:
        self.assertEqual(self.deploy["concurrency"], {"group": "pages", "cancel-in-progress": False})
        build_concurrency = self.build["concurrency"]
        self.assertIn("github.event.pull_request.number || github.ref", build_concurrency["group"])
        self.assertEqual(
            build_concurrency["cancel-in-progress"], "${{ github.event_name == 'pull_request' }}"
        )

    def test_build_uses_repository_entrypoint_without_inlined_logic(self) -> None:
        checkout = self.build["steps"][0]
        self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["fetch-depth"], 0)
        python = self.build["steps"][1]
        self.assertTrue(python["uses"].startswith("actions/setup-python@"))
        self.assertEqual(python["with"]["python-version"], "3.11")

        run_steps = [s["run"] for job in (self.build, self.deploy) for s in job["steps"] if "run" in s]
        self.assertEqual(run_steps, [BUILD_COMMAND])
        self.assertTrue((ROOT / "scripts" / "build_explorer.py").is_file())
        for forbidden in ("|", "&&", ";", "pip install", "npm ", "git "):
            self.assertNotIn(forbidden, BUILD_COMMAND)

    def test_workflow_is_platform_only_and_not_rendered_downstream(self) -> None:
        template = ROOT / "template"
        offenders = [
            str(path.relative_to(ROOT))
            for path in template.rglob("*")
            if path.is_file()
            and (
                "explorer" in path.name.lower()
                or ("explorer" in path.read_text(encoding="utf-8", errors="ignore").lower()
                    and ".github" in path.parts)
            )
        ]
        self.assertEqual(offenders, [])
        self.assertNotIn("dev-platform@main", self.text)


if __name__ == "__main__":
    unittest.main()
