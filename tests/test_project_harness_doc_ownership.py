from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectHarnessDocOwnershipTests(unittest.TestCase):
    def test_project_harness_preserves_agent_workflow_documentation(self) -> None:
        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        self.assertIn(
            "{{ 'docs/engineering/agent-workflow.md' if harness_mode == 'project' else '.copier-managed-harness' }}",
            copier,
        )


if __name__ == "__main__":
    unittest.main()
