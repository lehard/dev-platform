from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DirectMainHealthTests(unittest.TestCase):
    def test_generated_platform_ci_runs_selected_on_pr_and_full_only_manually(self) -> None:
        workflow = (ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("if: github.event_name == 'pull_request'", workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", workflow)
        self.assertNotIn("if: github.event_name != 'pull_request'", workflow)
        self.assertIn("python3 scripts/select_checks.py --full --execute", workflow)

    def test_generated_guidance_calls_direct_main_health_lightweight(self) -> None:
        readme = (ROOT / "template" / "README.md.jinja").read_text(encoding="utf-8")
        workflow_doc = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        for text in (readme, workflow_doc):
            self.assertIn("deliberately lightweight", text)
            self.assertIn("without repeating the full project check set", text)
            self.assertIn("Manual", text)


if __name__ == "__main__":
    unittest.main()
