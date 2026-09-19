"""Contract evidence for the selectively loaded project-context surface."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jinja2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import platform_bootstrap  # noqa: E402


class ProjectContextTests(unittest.TestCase):
    def test_fresh_template_has_one_bounded_context_map_not_empty_topic_ceremony(self) -> None:
        index = platform_bootstrap.PROJECT_CONTEXT_MAP
        self.assertLessEqual(len(index.splitlines()), 60)
        for marker in (
            "product.md",
            "domain.md",
            "architecture.md",
            "anti-patterns.md",
            "examples.md",
            "optional conventions",
            "not mandatory empty",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, index)
        self.assertFalse((ROOT / "template" / "docs" / "context" / "README.md").exists())

    def test_root_pointer_is_reached_concern_only_and_adapters_remain_thin(self) -> None:
        agents = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        context = platform_bootstrap.PROJECT_CONTEXT_MAP
        claude = (ROOT / "template" / "CLAUDE.md.jinja").read_text(encoding="utf-8")

        self.assertIn(
            "[docs/context/README.md](docs/context/README.md) when that concern is reached",
            agents,
        )
        self.assertIn("not an always-on prompt", context)
        self.assertIn("Do not load the entire context pack", (ROOT / "template" / "docs" / "engineering" / "openspec-workflow.md").read_text(encoding="utf-8"))
        self.assertNotIn("docs/context", claude)

        central_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("[docs/context/README.md](docs/context/README.md) when that concern is reached", central_agents)
        self.assertTrue((ROOT / "docs" / "context" / "README.md").is_file())

    def test_bootstrap_is_evidence_first_and_preserves_uncertainty(self) -> None:
        context = platform_bootstrap.PROJECT_CONTEXT_MAP
        for marker in (
            "Preserve any non-empty reviewed context",
            "README, project rules, OpenSpec",
            "relevant code and\nchecks",
            "one bounded human question at a time",
            "TODO` or `Unknown",
            "temporary machine-local input",
            "Do not commit it",
            "owner` and `last-reviewed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, context)

    def test_bootstrap_inventory_uses_present_evidence_and_question_never_writes(self) -> None:
        script = ROOT / "template" / "scripts" / "project_context.py"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            for relative in ("README.md", "docs/engineering/project-rules.md", "dev-platform/checks.toml", "openspec/specs/demo/spec.md"):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("repository evidence", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "inventory", "--json"], cwd=project, text=True, capture_output=True, check=True
            )
            inventory = json.loads(result.stdout)
            self.assertEqual(inventory["evidence"], ["README.md", "docs/engineering/project-rules.md", "dev-platform/checks.toml", "openspec/specs", "docs"])
            self.assertIn("TODO or Unknown", inventory["drafting_rule"])

            question = subprocess.run(
                [sys.executable, str(script), "question", "domain"], cwd=project, text=True, capture_output=True, check=True
            )
            self.assertEqual(question.stdout.strip().count("?"), 1)
            self.assertEqual(list((project / "docs" / "context").glob("*")) if (project / "docs" / "context").exists() else [], [])

    def test_openspec_routes_context_by_artifact(self) -> None:
        source = (ROOT / "template" / "openspec" / "config.yaml.jinja").read_text(encoding="utf-8")
        rendered = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(source).render(
            project_name="Context test", project_description="Targeted routing"
        )
        workflow = (ROOT / "template" / "docs" / "engineering" / "openspec-workflow.md").read_text(encoding="utf-8")
        for marker in (
            "do not ingest the whole context pack by default",
            "project goals, users, key scenarios, domain meaning, or product invariants",
            "project architecture invariant or prior decision",
            "recorded anti-pattern or representative example",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rendered)
        self.assertIn("## Project-context routing", workflow)
        self.assertIn("For a proposal", workflow)
        self.assertIn("design, load focused architecture context", workflow)
        self.assertIn("For tasks and implementation", workflow)

    def test_bootstrap_creates_context_once_and_guarded_rollout_preserves_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            platform_bootstrap.ensure_project_context_map(project)
            context_map = project / "docs" / "context" / "README.md"
            self.assertEqual(context_map.read_text(encoding="utf-8"), platform_bootstrap.PROJECT_CONTEXT_MAP)
            context_map.write_text("# Reviewed context\\n", encoding="utf-8")
            platform_bootstrap.ensure_project_context_map(project)
            self.assertEqual(context_map.read_text(encoding="utf-8"), "# Reviewed context\\n")

        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        rollout = (ROOT / "scripts" / "rollout_project.py").read_text(encoding="utf-8")
        self.assertNotIn("docs/context", copier)
        self.assertIn('"docs/context",', rollout)
        self.assertIn('return ("dir", digest.hexdigest())', rollout)


if __name__ == "__main__":
    unittest.main()
