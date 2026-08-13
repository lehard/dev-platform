from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TemplateContractTests(unittest.TestCase):
    def test_required_template_files_exist(self) -> None:
        required = ["copier.yml", "template/AGENTS.md.jinja", "template/CLAUDE.md.jinja", "template/.dev-platform.toml.jinja", "template/dev-platform/checks.toml", "template/.github/workflows/dev-platform.yml.jinja", "template/scripts/shared_workspace.py", "template/scripts/agent_board.py", "template/scripts/start_worktree.py", "template/scripts/worktree_cleanup.py", "template/scripts/start_task.py", "template/scripts/managed_task.py", "template/scripts/managed_project_status.py", "template/scripts/start_managed_task.py", "template/scripts/select_checks.py", "template/scripts/project_sync.py", "template/scripts/project_publish.py", "template/scripts/finish_task.py", "template/scripts/reconcile_task.py", "template/scripts/task_reconciliation.py", "template/scripts/openspec_lifecycle.py", "template/scripts/merge_to_main.py", "template/scripts/agent_friction.py", "template/scripts/agent_doctor.py", "template/scripts/model_routing.py", "template/scripts/platform_bootstrap.py", "template/scripts/platform_doctor.py", "template/scripts/git_hooks/pre-commit", "template/scripts/git_hooks/pre-merge-commit"]
        for relative in required:
            with self.subTest(relative=relative): self.assertTrue((ROOT / relative).exists(), relative)

    def test_platform_does_not_vendor_openspec_generated_skills(self) -> None:
        self.assertFalse((ROOT / "template" / ".agents" / "skills").exists()); self.assertFalse((ROOT / "template" / ".claude" / "skills").exists())

    def test_generic_openspec_template_has_no_finance_domain_contract(self) -> None:
        text = (ROOT / "template" / "openspec" / "config.yaml.jinja").read_text(encoding="utf-8").lower()
        for term in ("p&l", "dds", "payroll", "cash canonical", "bank canonical"): self.assertNotIn(term, text)

    def test_root_openspec_receipt_guidance_is_yaml_safe(self) -> None:
        config = (ROOT / "openspec" / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("'After material findings are resolved, record `OpenSpec-Verify: PASS`", config)

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

    def test_downstream_platform_ci_preserves_required_pr_check_and_cancels_superseded_runs(self) -> None:
        workflow = (ROOT / "template" / ".github" / "workflows" / "dev-platform.yml.jinja").read_text(encoding="utf-8")
        self.assertIn("on:\n  pull_request:\n    branches:\n      - {{ main_branch }}", workflow)
        self.assertIn("{% if publish_mode == 'direct' %}", workflow)
        self.assertIn("push:", workflow)
        self.assertNotIn("{% if publish_mode == 'pr' %}", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn('{% raw %}${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.ref }}{% endraw %}', workflow)
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
        openspec_doc = (ROOT / "template" / "docs" / "engineering" / "openspec-workflow.md").read_text(encoding="utf-8")
        lower = text.lower()
        # Root guidance keeps the always-on invariants and the entrypoints; the
        # verification/archive mechanics live in the linked canonical document.
        self.assertIn("no silent divergence", lower)
        self.assertIn("scripts/openspec_lifecycle.py archive", text)
        self.assertIn("scripts/managed_task.py", text)
        self.assertIn("docs/engineering/openspec-workflow.md", text)
        self.assertIn("/opsx:verify", openspec_doc)
        self.assertIn("OpenSpec-Verify: PASS", openspec_doc)
        self.assertIn("scripts/openspec_lifecycle.py archive", openspec_doc)

    def test_managed_task_intake_is_universal_and_quick_tasks_remain_lightweight(self) -> None:
        agents = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        workflow = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        self.assertIn("managed task", agents)
        self.assertIn("quick task", agents)
        self.assertIn("Development Backlog Project item to `In progress`", agents)
        self.assertIn("scripts/start_managed_task.py", agents)
        self.assertIn("scripts/start_managed_task.py", workflow)
        doctor = (ROOT / "template" / "scripts" / "platform_doctor.py").read_text(encoding="utf-8")
        self.assertIn("scripts/start_managed_task.py", doctor)
        self.assertIn("stops before OpenSpec apply", workflow)

    def test_goal_definition_is_selective_measurable_and_transient(self) -> None:
        root_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        agents = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        workflow = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        central_workflow = (ROOT / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        # Root guidance states that refinement is selective and creates no durable
        # state, then routes to the canonical contract; the full goal contract is
        # detailed guidance loaded when a request actually needs refining.
        for contract, text in (("root", root_agents), ("template", agents)):
            with self.subTest(contract=contract):
                self.assertIn("Goal refinement is a selective layer", text)
                self.assertIn("creates no durable goal, backlog or plan artifact", text)
                self.assertIn("docs/engineering/agent-workflow.md", text)
        for destination, text in (("central", central_workflow), ("template", workflow)):
            with self.subTest(destination=destination):
                self.assertIn("## Selective goal definition", text)
                self.assertIn("materially unclear about its intended outcome or success evidence", text)
                self.assertIn("ordinary concrete quick or implementation task", text)
                self.assertIn("quantitative or binary success threshold", text)
                self.assertIn("For an explicit goal-backed request", text)
                self.assertIn("`/goal` or runtime-native goal tools when available", text)
                self.assertIn("not implicit durable goal state", text)
                self.assertIn("never claim that `create_goal` succeeded", text)
                self.assertIn("creates no goal file, backlog entry, decision log, resume artifact, or competing implementation plan", text)
        self.assertIn("Goal definition is a selective refinement layer before this intake", workflow)
        self.assertIn("Issue/OpenSpec package is authoritative", workflow)

    def test_managed_task_authoring_is_configured_once_and_claude_keeps_the_bridge(self) -> None:
        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        config = (ROOT / "template" / ".dev-platform.toml.jinja").read_text(encoding="utf-8")
        agents = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        workflow = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        claude = (ROOT / "template" / "CLAUDE.md.jinja").read_text(encoding="utf-8")
        helper = (ROOT / "template" / "scripts" / "managed_task.py").read_text(encoding="utf-8")
        for value in ("development_backlog_repository", "development_backlog_project_label", "development_backlog_default_priority", "development_backlog_project_owner", "development_backlog_project_number"):
            self.assertIn(value, copier)
        self.assertIn("[development_backlog]", config)
        self.assertIn("create --bundle", agents)
        # The overlap-confirmation flag is authoring detail: root guidance names
        # the entrypoint, the workflow doc owns how to answer a candidate list.
        self.assertIn("--confirm-distinct", workflow)
        self.assertEqual(claude.count("managed"), 0)
        self.assertIn("Authoring stops here", helper)

    def test_managed_project_status_is_wired_to_claim_review_and_terminal_delivery(self) -> None:
        start = (ROOT / "template" / "scripts" / "start_managed_task.py").read_text(encoding="utf-8")
        publish = (ROOT / "template" / "scripts" / "project_publish.py").read_text(encoding="utf-8")
        finish = (ROOT / "template" / "scripts" / "finish_task.py").read_text(encoding="utf-8")
        helper = (ROOT / "template" / "scripts" / "managed_project_status.py").read_text(encoding="utf-8")
        self.assertIn('"In progress"', start)
        self.assertIn('"In review"', publish)
        self.assertIn('"Done"', finish)
        self.assertIn("updateProjectV2ItemFieldValue", helper)
        self.assertIn("gh auth refresh -s project", helper)

    def test_finish_task_has_openspec_hygiene_and_serialized_direct_integration(self) -> None:
        text = (ROOT / "template" / "scripts" / "finish_task.py").read_text(encoding="utf-8")
        self.assertIn("run_openspec_hygiene(work)", text)
        self.assertIn('"openspec_lifecycle.py"', text)
        self.assertIn("serialized_integration", text)
        self.assertIn("reconcile_confirmed_remote_pr_merge", text)
        self.assertIn('fetch_main(integration, "origin", main_branch)', text)
        self.assertIn("fetch_main(integration", text)
        self.assertIn("harness_mode=project", text)

    def test_publication_recovery_reconciler_and_status_are_wired_into_lifecycle(self) -> None:
        finish_text = (ROOT / "template" / "scripts" / "finish_task.py").read_text(encoding="utf-8")
        self.assertIn("--status", finish_text)
        self.assertIn("run_status", finish_text)
        self.assertIn("find_existing_exact_open_pr", finish_text)
        self.assertIn("observe_source_issue_drift", finish_text)
        publish_text = (ROOT / "template" / "scripts" / "project_publish.py").read_text(encoding="utf-8")
        self.assertIn("request_protected_merge", publish_text)
        self.assertIn("--match-head-commit", publish_text)
        state_text = (ROOT / "template" / "scripts" / "publication_state.py").read_text(encoding="utf-8")
        self.assertIn("find_exact_head_pr", state_text)
        doctor_text = (ROOT / "template" / "scripts" / "agent_doctor.py").read_text(encoding="utf-8")
        self.assertIn("report_publication_status", doctor_text)
        agents_text = (ROOT / "template" / "AGENTS.md.jinja").read_text(encoding="utf-8")
        workflow_text = (ROOT / "template" / "docs" / "engineering" / "agent-workflow.md").read_text(encoding="utf-8")
        self.assertIn("--status", agents_text)
        # Exact-head matching is publication mechanics, not always-on context.
        self.assertIn("exact validated head", workflow_text)

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
