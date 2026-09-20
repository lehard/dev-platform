from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectHarnessDocOwnershipTests(unittest.TestCase):
    def test_copier_preserves_project_owned_agent_workflow_doc(self) -> None:
        text = (ROOT / "copier.yml").read_text(encoding="utf-8")
        expected = "{{ 'docs/engineering/agent-workflow.md' if harness_mode == 'project' else '.copier-managed-harness' }}"
        self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
