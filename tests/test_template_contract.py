from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTests(unittest.TestCase):
    def test_required_template_files_exist(self) -> None:
        required = ["copier.yml", "template/AGENTS.md.jinja", "template/CLAUDE.md.jinja", "template/.dev-platform.toml.jinja", "template/dev-platform/checks.toml", "template/.github/workflows/dev-platform.yml.jinja", "template/scripts/agent_board.py", "template/scripts/start_worktree.py", "template/scripts/worktree_cleanup.py", "template/scripts/start_task.py", "template/scripts/select_checks.py", "template/scripts/project_sync.py", "template/scripts/project_publish.py", "template/scripts/finish_task.py", "template/scripts/openspec_lifecycle.py", "template/scripts/merge_to_main.py", "template/scripts/agent_friction.py", "template/scripts/agent_doctor.py", "template/scripts/platform_bootstrap.py", "template/scripts/platform_doctor.py", "template/scripts/git_hooks/pre-commit", "template/scripts/git_hooks/pre-merge-commit"]
        for relative in required:
            with self.subTest(relative=relative): self.assertTrue((ROOT / relative).exists(), relative)

    def test_platform_does_not_vendor_openspec_generated_skills(self) -> None:
        self.assertFalse((ROOT / "template" / ".agents" / "skills").exists()); self.assertFalse((ROOT / "template" / ".claude" / "skills").exists())

    def test_generic_openspec_template_has_no_finance_domain_contract(self) -> None:
        text = (ROOT / "template" / "openspec" / "config.yaml.jinja").read_text(encoding="utf-8").lower()
        for term in ("p&l", "dds", "payroll", "cash canonical", "bank canonical"): self.assertNotIn(term, text)

    def test_downstream_platform_ci_is_self_contained_and_does_not_own_project_ci_name(self) -> None:
        workflow = (ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        agents = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        readme = (ROOT / "template" / "README.md.jinja").read_text(encoding="utf-8")
        self.assertFalse((ROOT / "template" / ".github" / "workflows" / "ci.yml.jinja").exists())
        self.assertNotIn("lehard/dev-platform/.github/workflows", workflow)
        self.assertIn("scripts/select_checks.py", workflow)
        self.assertIn("scripts/openspec_lifecycle.py check", workflow)
        self.assertIn("self-contained CI workflow", agents)
        self.assertIn("self-contained in this repository", readme)
        self.assertNotIn("Reusable CI is pinned", agents)
        self.assertNotIn("Reusable CI is pinned", readme)

    def test_downstream_platform_ci_derives_one_trigger_from_publish_mode_and_cancels_superseded_runs(self) -> None:
        workflow = (ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("{% if publish_mode == 'pr' %}", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn('{% raw %}${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}{% endraw %}', workflow)
        self.assertIn("cancel-in-progress: true", workflow)

    def test_central_ci_runs_once_per_pr_and_keeps_all_profile_smokes(self) -> None:
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", ci)
        self.assertIn("workflow_dispatch:", ci)
        self.assertNotIn("\n  push:", ci)
        self.assertNotIn("matrix:", ci)
        self.assertIn("cancel-in-progress: true", ci)
        for profile_and_mode in ("light:direct", "standard:pr", "multi-agent:pr"):
            with self.subTest(profile_and_mode=profile_and_mode):
                self.assertIn(profile_and_mode, ci)

    def test_generated_guidance_keeps_local_checks_required_and_cloud_final(self) -> None:
        readme = (ROOT / "template" / "README.md.jinja").read_text(encoding="utf-8")
        workflow = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        self.assertIn("Required selected and full checks run locally before publication", readme)
        self.assertIn("Local-heavy, cloud-final verification", workflow)

    def test_profiles_publish_modes_and_harness_modes_are_declared(self) -> None:
        text = (ROOT / "copier.yml").read_text(encoding="utf-8")
        for value in ("light", "standard", "multi-agent", "publish_mode", "harness_mode", "platform", "project", "platform_ci_ref"): self.assertIn(value, text)
        self.assertIn("legacy", text.lower())

    def test_project_owned_files_are_preserved_after_initial_render(self) -> None:
        text = (ROOT / "copier.yml").read_text(encoding="utf-8")
        for relative in (
            ".dev-platform.toml",
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
            "dev-platform/checks.toml",
            "openspec/config.yaml",
            "docs/engineering/project-rules.md",
        ):
            with self.subTest(relative=relative):
                self.assertIn(f"  - {relative}", text)

    def test_project_harness_can_preserve_mature_collision_points(self) -> None:
        text = (ROOT / "copier.yml").read_text(encoding="utf-8")
        for relative in (
            "scripts/agent_board.py",
            "scripts/agent_friction.py",
            "scripts/merge_to_main.py",
            "scripts/select_checks.py",
            "scripts/start_worktree.py",
            "scripts/worktree_cleanup.py",
        ):
            with self.subTest(relative=relative):
                self.assertIn(relative, text)
                self.assertIn("harness_mode == 'project'", text)

    def test_harness_ownership_is_recorded_in_project_config(self) -> None:
        config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        self.assertIn('harness_mode = "{{ harness_mode }}"', config)
        self.assertIn("platform_git_lifecycle", config)
        self.assertIn("main_merge_lock", config)
        self.assertIn("pending_worktrees", config)

    def test_project_specific_required_files_are_configurable(self) -> None:
        config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        doctor = (ROOT / "template" / "scripts" / "platform_doctor.py").read_text(encoding="utf-8")
        self.assertIn("project_required_files = []", config)
        self.assertIn('config.get("project_required_files", [])', doctor)
        self.assertIn("REQUIRED_MULTI_AGENT_PLATFORM", doctor)
        self.assertIn("scripts/worktree_cleanup.py", doctor)

    def test_no_silent_divergence_and_verify_are_in_agent_contract(self) -> None:
        text = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        lower = text.lower()
        self.assertIn("no silent divergence", lower)
        self.assertIn("/opsx:verify", text)
        self.assertIn("OpenSpec-Verify: PASS", text)
        self.assertIn("scripts/openspec_lifecycle.py archive", text)

    def test_finish_task_has_openspec_hygiene_and_serialized_direct_integration(self) -> None:
        text = (ROOT / "template" / "scripts" / "finish_task.py").read_text(encoding="utf-8")
        self.assertIn("run_openspec_hygiene(work)", text)
        self.assertIn('"openspec_lifecycle.py"', text)
        self.assertIn("serialized_integration", text)
        self.assertIn("fetch_main(integration", text)
        self.assertIn("harness_mode=project", text)

    def test_multi_agent_git_guards_and_hygiene_are_platform_managed(self) -> None:
        doctor = (ROOT / "template" / "scripts" / "agent_doctor.py").read_text(encoding="utf-8")
        cleanup = (ROOT / "template" / "scripts" / "worktree_cleanup.py").read_text(encoding="utf-8")
        pre_commit = (ROOT / "template" / "scripts" / "git_hooks" / "pre-commit").read_text(encoding="utf-8")
        pre_merge = (ROOT / "template" / "scripts" / "git_hooks" / "pre-merge-commit").read_text(encoding="utf-8")
        self.assertIn("ensure_git_hooks", doctor)
        self.assertIn("integration copy is dirty", doctor)
        self.assertIn("run_multi_agent_hygiene", doctor)
        self.assertIn("pending-worktrees.md", cleanup)
        self.assertIn("candidate-no-longer-safe", cleanup)
        self.assertIn("DEV_PLATFORM_ALLOW_MAIN_COMMIT", pre_commit)
        self.assertIn("DEV_PLATFORM_ALLOW_MERGE_COMMIT", pre_merge)

    def test_copier_version_is_explicitly_tested(self) -> None:
        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('_min_copier_version: "9.17.0"', copier); self.assertIn('[tools.copier]', config); self.assertIn('tested_version = "9.17.0"', config); self.assertIn('copier==9.17.0', ci)

    def test_central_github_actions_are_sha_pinned(self) -> None:
        pattern = re.compile(r"uses:\s+actions/[\w-]+@([^\s#]+)")
        for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            for ref in pattern.findall(text):
                with self.subTest(workflow=workflow.name, ref=ref): self.assertRegex(ref, r"^[0-9a-f]{40}$")

    def test_upgrade_smoke_is_part_of_ci(self) -> None:
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"); self.assertIn("tests/upgrade_smoke.py", ci); self.assertIn("fetch-depth: 0", ci)

    def test_version_release_workflow_is_guarded(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "publish-version.yml").read_text(encoding="utf-8")
        rollout = (ROOT / ".github" / "workflows" / "rollout.yml").read_text(encoding="utf-8")
        self.assertIn("paths:\n      - VERSION", workflow)
        self.assertIn("Refusing to move existing tag", workflow)
        self.assertIn('tag="v$version"', workflow)
        self.assertNotIn("cancel-in-progress: true", workflow)
        self.assertNotIn("cancel-in-progress: true", rollout)


if __name__ == "__main__": unittest.main()
