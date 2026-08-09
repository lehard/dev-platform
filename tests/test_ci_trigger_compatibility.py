from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CiTriggerCompatibilityTests(unittest.TestCase):
    def test_direct_mode_keeps_pr_compatibility_and_main_push(self) -> None:
        workflow = (ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("on:\n  pull_request:\n    branches:\n      - {{ main_branch }}", workflow)
        self.assertIn("{% if publish_mode == 'direct' %}\n  push:\n    branches:\n      - {{ main_branch }}\n{% endif %}", workflow)
        self.assertNotIn("{% if publish_mode == 'pr' %}", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("cancel-in-progress: true", workflow)

    def test_generated_guidance_explains_required_pr_compatibility(self) -> None:
        readme = (ROOT / "template" / "README.md.jinja").read_text(encoding="utf-8")
        agent_workflow = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        self.assertIn("pull-request `platform-ci` compatibility gate", readme)
        self.assertIn("pull-request `platform-ci` gate", agent_workflow)
        self.assertIn("published main state", readme)
        self.assertIn("published main state", agent_workflow)


if __name__ == "__main__":
    unittest.main()
