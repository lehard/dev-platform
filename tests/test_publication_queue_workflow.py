"""Publication queue workflow wake-up events."""
from __future__ import annotations

import ast
import re
import sys
import tomllib
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publication-queue.yml"
# Import name -> pip distribution for third-party modules a regeneration script may import.
DISTRIBUTIONS = {"yaml": "pyyaml"}


class QueueWakeUpTests(unittest.TestCase):
    def test_contribution_ready_for_integration_wakes_the_queue(self) -> None:
        # A finalized Requirement contribution waits in contribution-integration-pending for the
        # queue to integrate it into the requirement branch; without this label the queue waited
        # for a manual dispatch (lehard/dev-platform#687).
        workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "publication-queue.yml").read_text(encoding="utf-8"))
        condition = workflow["jobs"]["publish-next"]["if"]
        for label in ("publication:queued", "lifecycle:ready", "lifecycle:contribution-integration-pending"):
            with self.subTest(label=label):
                self.assertIn(f"github.event.label.name == '{label}'", condition)


class RegenerationDependencyTests(unittest.TestCase):
    def test_queue_runner_installs_every_regeneration_import(self) -> None:
        # The queue's derived merge runs each declared generated file's regenerate command on
        # this runner; a missing third-party module left #730 in integration-repair-pending.
        declarations = tomllib.loads((ROOT / "dev-platform" / "checks.toml").read_text(encoding="utf-8"))
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        installs = " ".join(step.get("run", "") for step in workflow["jobs"]["publish-next"]["steps"]
                            if "pip install" in step.get("run", "")).lower()
        declared = declarations["generated_files"]
        self.assertTrue(declared)
        for item in declared:
            script = ROOT / next(arg for arg in item["regenerate"] if arg.endswith(".py"))
            tree = ast.parse(script.read_text(encoding="utf-8"))
            modules = {alias.name.split(".")[0] for node in tree.body if isinstance(node, ast.Import) for alias in node.names}
            modules |= {node.module.split(".")[0] for node in tree.body
                        if isinstance(node, ast.ImportFrom) and node.module and not node.level}
            third_party = {name for name in modules if name not in sys.stdlib_module_names
                           and name != "__future__" and not (script.parent / f"{name}.py").is_file()}
            for name in sorted(third_party):
                with self.subTest(script=str(script.relative_to(ROOT)), module=name):
                    self.assertIn(name, DISTRIBUTIONS, f"map {name} to its pip distribution")
                    self.assertIn(f"{DISTRIBUTIONS[name]}==", installs)


class OpenSpecCliTests(unittest.TestCase):
    def test_queue_runner_installs_the_ci_openspec_version(self) -> None:
        # A derived merge re-derives archived specs with the installed OpenSpec CLI; the hosted
        # queue lacked it and stopped #837 with an environment error (lehard/dev-platform#838).
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        versions = set(re.findall(r"@fission-ai/openspec@(\d+\.\d+\.\d+)", ci))
        self.assertEqual(len(versions), 1, versions)
        steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish-next"]["steps"]
        names = [step.get("name") for step in steps]
        install = next(index for index, step in enumerate(steps)
                       if "npm install --global" in step.get("run", ""))
        self.assertIn(f'"@fission-ai/openspec@{versions.pop()}"', steps[install]["run"])
        self.assertLess(install, names.index("Process next admitted PR"))
        self.assertTrue(any(step.get("uses", "").startswith("actions/setup-node@") for step in steps[:install]))


if __name__ == "__main__":
    unittest.main()
