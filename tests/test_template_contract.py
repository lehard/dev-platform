from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTests(unittest.TestCase):
    def test_required_template_files_exist(self) -> None:
        required = [
            "copier.yml",
            "template/AGENTS.md.jinja",
            "template/CLAUDE.md.jinja",
            "template/.dev-platform.toml.jinja",
            "template/dev-platform/checks.toml",
            "template/scripts/agent_board.py",
            "template/scripts/start_worktree.py",
            "template/scripts/select_checks.py",
            "template/scripts/merge_to_main.py",
            "template/scripts/agent_friction.py",
            "template/scripts/platform_bootstrap.py",
            "template/scripts/platform_doctor.py",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).exists(), relative)

    def test_platform_does_not_vendor_openspec_generated_skills(self) -> None:
        self.assertFalse((ROOT / "template" / ".agents" / "skills").exists())
        self.assertFalse((ROOT / "template" / ".claude" / "skills").exists())

    def test_generic_openspec_template_has_no_finance_domain_contract(self) -> None:
        text = (ROOT / "template" / "openspec" / "config.yaml.jinja").read_text(encoding="utf-8").lower()
        for term in ("p&l", "dds", "payroll", "cash canonical", "bank canonical"):
            self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
