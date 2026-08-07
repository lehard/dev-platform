from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTests(unittest.TestCase):
    def test_required_template_files_exist(self) -> None:
        required = ["copier.yml", "template/AGENTS.md.jinja", "template/CLAUDE.md.jinja", "template/.dev-platform.toml.jinja", "template/dev-platform/checks.toml", "template/scripts/agent_board.py", "template/scripts/start_worktree.py", "template/scripts/start_task.py", "template/scripts/select_checks.py", "template/scripts/project_sync.py", "template/scripts/project_publish.py", "template/scripts/finish_task.py", "template/scripts/merge_to_main.py", "template/scripts/agent_friction.py", "template/scripts/agent_doctor.py", "template/scripts/platform_bootstrap.py", "template/scripts/platform_doctor.py"]
        for relative in required:
            with self.subTest(relative=relative): self.assertTrue((ROOT / relative).exists(), relative)

    def test_platform_does_not_vendor_openspec_generated_skills(self) -> None:
        self.assertFalse((ROOT / "template" / ".agents" / "skills").exists()); self.assertFalse((ROOT / "template" / ".claude" / "skills").exists())

    def test_generic_openspec_template_has_no_finance_domain_contract(self) -> None:
        text = (ROOT / "template" / "openspec" / "config.yaml.jinja").read_text(encoding="utf-8").lower()
        for term in ("p&l", "dds", "payroll", "cash canonical", "bank canonical"): self.assertNotIn(term, text)

    def test_downstream_ci_is_self_contained_and_reviewed(self) -> None:
        text = (ROOT / "template" / ".github" / "workflows" / "ci.yml.jinja").read_text(encoding="utf-8")
        self.assertNotIn("lehard/dev-platform/.github/workflows", text)
        self.assertIn("scripts/select_checks.py", text)
        self.assertIn("actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803", text)
        self.assertIn("actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1", text)

    def test_profiles_and_publish_modes_are_declared(self) -> None:
        text = (ROOT / "copier.yml").read_text(encoding="utf-8")
        for value in ("light", "standard", "multi-agent", "publish_mode", "platform_ci_ref"): self.assertIn(value, text)

    def test_no_silent_divergence_and_verify_are_in_agent_contract(self) -> None:
        text = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8").lower(); self.assertIn("no silent divergence", text); self.assertIn("/opsx:verify", text)

    def test_copier_version_is_explicitly_tested(self) -> None:
        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('_min_copier_version: "9.17.0"', copier)
        self.assertIn('[tools.copier]', config)
        self.assertIn('tested_version = "9.17.0"', config)
        self.assertIn('copier==9.17.0', ci)

    def test_central_github_actions_are_sha_pinned(self) -> None:
        pattern = re.compile(r"uses:\s+actions/[\w-]+@([^\s#]+)")
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            for ref in pattern.findall(text):
                with self.subTest(workflow=workflow.name, ref=ref): self.assertRegex(ref, r"^[0-9a-f]{40}$")

    def test_upgrade_smoke_is_part_of_ci(self) -> None:
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests/upgrade_smoke.py", ci); self.assertIn("fetch-depth: 0", ci)

    def test_version_release_workflow_is_guarded(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "publish-version.yml").read_text(encoding="utf-8")
        self.assertIn("paths:\n      - VERSION", workflow); self.assertIn("Refusing to move existing tag", workflow); self.assertIn('tag="v$version"', workflow)


if __name__ == "__main__": unittest.main()
