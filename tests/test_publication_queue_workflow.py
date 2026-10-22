"""Publication queue workflow wake-up events."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
