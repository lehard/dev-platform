"""Regression coverage for requirement-first intake semantics."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RequirementFirstIntakeContractTests(unittest.TestCase):
    def test_generic_fixation_is_requirement_only_across_key_surfaces(self) -> None:
        required_routes = {
            "AGENTS.md": "Fixation creates no OpenSpec package",
            "template/AGENTS.md.jinja": "Fixation creates no managed OpenSpec package",
            "docs/engineering/task-intake.md": "Fixation\n  does **not** author OpenSpec",
            "template/docs/engineering/task-intake.md.jinja": "Fixation\n  does **not** author OpenSpec",
            "docs/engineering/agent-instructions.md": "Generic fixation creates or reuses one",
            "template/docs/engineering/agent-instructions.md": "Generic fixation creates or reuses one",
            "openspec/specs/agent-instructions/spec.md": "Generic fixation SHALL create or reuse one",
            "openspec/specs/managed-task-intake/spec.md": "SHALL create or reuse one human-facing `type:requirement`",
        }
        for relative, route in required_routes.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("Business Requirement", text)
                self.assertIn(route, text)

        intake = (ROOT / "openspec/specs/managed-task-intake/spec.md").read_text(encoding="utf-8")
        fixation = intake[
            intake.index("The platform SHALL distinguish discussion from explicit fixation"):
            intake.index("### Requirement: Managed-task authoring uses")
        ]
        self.assertIn("SHALL NOT create a managed OpenSpec package", fixation)
        self.assertNotIn("SHALL create the managed task and its OpenSpec package", fixation)

    def test_old_generic_fixation_claims_do_not_return(self) -> None:
        stale_claims = {
            "docs/engineering/agent-instructions.md": (
                "A fixation is one Development Backlog\nIssue with one active",
            ),
            "template/docs/engineering/agent-instructions.md": (
                "A fixation is one Development Backlog\nIssue with one active",
            ),
            "openspec/specs/agent-instructions/spec.md": (
                "record an accepted non-trivial change\n- **THEN** ChatGPT can create or update exactly one Development Backlog Issue and one valid managed OpenSpec package",
                "record an accepted non-trivial change\n- **THEN** the agent uses the supported deterministic `managed_task.py create",
            ),
            "openspec/specs/managed-task-intake/spec.md": (
                "SHALL create the managed task and its OpenSpec package, then stop",
                "Successful fixation SHALL mean that the exact Issue has the configured target and priority labels plus exactly one active supported",
            ),
            "openspec/specs/agentic-maintenance/spec.md": (
                "fixation request is required before the existing managed-task authoring path",
            ),
            "openspec/specs/platform-lifecycle/spec.md": (
                "fixation through the managed-task authoring path",
            ),
        }
        for relative, phrases in stale_claims.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_explicit_direct_technical_path_remains_available(self) -> None:
        surfaces = (
            "AGENTS.md",
            "template/AGENTS.md.jinja",
            "docs/engineering/task-intake.md",
            "template/docs/engineering/task-intake.md.jinja",
            "docs/engineering/chatgpt-project-protocol.md",
            "template/docs/engineering/chatgpt-project-protocol.md",
            "openspec/specs/managed-task-intake/spec.md",
        )
        for relative in surfaces:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("direct technical", text.lower())
                self.assertIn("managed", text.lower())


if __name__ == "__main__":
    unittest.main()
