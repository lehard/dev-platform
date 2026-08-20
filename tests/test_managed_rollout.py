from __future__ import annotations

import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import managed_projects  # noqa: E402
import rollout_project  # noqa: E402


class ManagedProjectRegistryTests(unittest.TestCase):
    def test_real_registry_is_valid_comprehensive_and_has_expected_managed_projects(self) -> None:
        data = managed_projects.load_registry(ROOT / "managed-projects.json")
        matrix = managed_projects.matrix_payload(data)
        repos = {item["repository"] for item in matrix["include"]}
        self.assertEqual(repos, {"lehard/planner-agent-lab", "lehard/cuby", "lehard/Jara_Fin"})
        self.assertEqual(len(data["projects"]), 13)
        self.assertEqual(sum(1 for item in data["projects"] if item["state"] == "excluded"), 3)

    def test_non_managed_states_never_enter_matrix(self) -> None:
        data = {
            "schema_version": 1,
            "projects": [
                {"repository": "lehard/managed", "state": "managed", "default_branch": "main"},
                {"repository": "lehard/candidate", "state": "candidate", "default_branch": "main"},
                {"repository": "lehard/excluded", "state": "excluded", "default_branch": "main", "note": "intentional"},
            ],
        }
        managed_projects.validate_registry(data)
        matrix = managed_projects.matrix_payload(data)
        self.assertEqual([item["repository"] for item in matrix["include"]], ["lehard/managed"])
        for repository in ("lehard/candidate", "lehard/excluded"):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                managed_projects.matrix_payload(data, repository)

    def test_excluded_repository_requires_reason(self) -> None:
        data = {
            "schema_version": 1,
            "projects": [
                {"repository": "lehard/excluded", "state": "excluded", "default_branch": "main", "note": ""},
            ],
        }
        with self.assertRaises(ValueError):
            managed_projects.validate_registry(data)

    def test_duplicate_repository_is_invalid(self) -> None:
        data = {
            "schema_version": 1,
            "projects": [
                {"repository": "lehard/a", "state": "managed", "default_branch": "main"},
                {"repository": "lehard/a", "state": "candidate", "default_branch": "main"},
            ],
        }
        with self.assertRaises(ValueError):
            managed_projects.validate_registry(data)


class RolloutProjectTests(unittest.TestCase):
    def test_jara_fin_style_guidance_migration_preserves_project_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text(
                'project_name = "Jara_Fin"\n\n[development_backlog]\nrepository = "lehard/development-backlog"\n',
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                "# Agent Notes\n\n- `frontend/AGENTS.md` — Next.js rules.\n"
                "- `backend/AGENTS.md` — FastAPI/SQLite rules.\n",
                encoding="utf-8",
            )
            contract = root / "docs" / "engineering" / "task-intake.md"
            contract.parent.mkdir(parents=True)
            contract.write_text("# Intake\n", encoding="utf-8")
            self.assertTrue(rollout_project.reconcile_task_intake_reference(root))
            migrated = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("`frontend/AGENTS.md` — Next.js rules.", migrated)
            self.assertIn("`backend/AGENTS.md` — FastAPI/SQLite rules.", migrated)
            self.assertIn(rollout_project.TASK_INTAKE_REFERENCE_MARKER, migrated)
            self.assertFalse(rollout_project.reconcile_task_intake_reference(root))
            self.assertEqual(migrated, (root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_candidate_guidance_is_not_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text("platform_version = '1.0.0'\n", encoding="utf-8")
            agents = root / "AGENTS.md"
            agents.write_text("# Candidate local rules\n", encoding="utf-8")
            self.assertFalse(rollout_project.reconcile_task_intake_reference(root))
            self.assertEqual(agents.read_text(encoding="utf-8"), "# Candidate local rules\n")

    def test_rollout_skips_historical_copier_tasks_then_runs_candidate_bootstrap(self) -> None:
        source = inspect.getsource(rollout_project.copier_update_with_guarded_recopy)
        bootstrap = inspect.getsource(rollout_project.run_rendered_platform_bootstrap)
        self.assertEqual(source.count('"--skip-tasks"'), 2)
        self.assertIn("run_rendered_platform_bootstrap(project_root, env=env)", source)
        self.assertIn('project_root / "scripts" / "platform_bootstrap.py"', bootstrap)
        self.assertIn("updated project is missing scripts/platform_bootstrap.py", bootstrap)

    def test_answers_metadata_is_parsed(self) -> None:
        answers = rollout_project.parse_answers(
            "# managed by Copier\n_commit: v1.0.2\n_src_path: gh:lehard/dev-platform\nproject_name: Test\n"
        )
        self.assertEqual(answers["_commit"], "v1.0.2")
        self.assertEqual(answers["_src_path"], "gh:lehard/dev-platform")

    def test_normalize_copier_answers_removes_only_trailing_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".copier-answers.yml"
            original_body = "_commit: v1.2.3\n_src_path: gh:lehard/dev-platform"
            path.write_text(original_body + "\n\n\n", encoding="utf-8")
            rollout_project.normalize_copier_answers(root)
            self.assertEqual(path.read_text(encoding="utf-8"), original_body + "\n")

    def test_normalize_copier_answers_requires_metadata_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                rollout_project.normalize_copier_answers(Path(tmp))

    def test_stable_versions_and_branch_are_deterministic(self) -> None:
        self.assertEqual(rollout_project.parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(rollout_project.rollout_branch("v1.2.3"), "dev-platform/rollout-v1.2.3")
        for invalid in ("1.2.3", "v1.2", "main", "v1.2.3-rc1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                rollout_project.parse_version(invalid)

    def test_reject_files_ignore_machine_local_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "real.rej").write_text("conflict", encoding="utf-8")
            (root / ".claude").mkdir()
            (root / ".claude" / "ignored.rej").write_text("machine local", encoding="utf-8")
            self.assertEqual(rollout_project.find_reject_files(root), ["real.rej"])

    def test_load_answers_requires_platform_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".copier-answers.yml").write_text(
                "_commit: v1.0.0\n_src_path: gh:someone/other-template\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                rollout_project.load_answers(root)

    def test_platform_version_metadata_must_match_copier_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('platform_version = "1.2.1"\n', encoding="utf-8")
            rollout_project.require_version_coherence(root, "v1.2.1")
            with self.assertRaises(ValueError):
                rollout_project.require_version_coherence(root, "v1.2.2")

    def test_private_source_git_env_is_process_only_and_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                rollout_project.private_source_git_env()
        with patch.dict(os.environ, {"DEV_PLATFORM_SOURCE_TOKEN": "test-token"}, clear=True):
            env = rollout_project.private_source_git_env()
            self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
            self.assertEqual(env["GIT_CONFIG_VALUE_0"], "https://github.com/")
            self.assertIn("x-access-token:test-token@github.com", env["GIT_CONFIG_KEY_0"])


class RolloutWorkflowContractTests(unittest.TestCase):
    def test_rollout_workflow_uses_split_app_tokens_and_is_pr_only(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "rollout.yml").read_text(encoding="utf-8")
        pin = "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1"
        self.assertEqual(workflow.count(pin), 2)
        self.assertIn("id: source-token", workflow)
        self.assertIn("repositories: dev-platform", workflow)
        self.assertIn("permission-contents: read", workflow)
        self.assertIn("id: target-token", workflow)
        self.assertIn("repositories: ${{ matrix.repo_name }}", workflow)
        self.assertIn("permission-contents: write", workflow)
        self.assertIn("permission-pull-requests: write", workflow)
        self.assertIn("permission-workflows: write", workflow)
        self.assertIn("DEV_PLATFORM_SOURCE_TOKEN: ${{ steps.source-token.outputs.token }}", workflow)
        self.assertIn("token: ${{ steps.target-token.outputs.token }}", workflow)
        self.assertIn("gh pr create", workflow)
        self.assertNotIn("gh pr merge", workflow)
        self.assertNotIn("--auto-merge", workflow)

    def test_rollout_requires_an_immutable_published_release(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "rollout.yml").read_text(encoding="utf-8")
        self.assertIn("releases/tags/$version", workflow)
        self.assertIn(".immutable // false", workflow)
        self.assertIn("must be an existing immutable published platform release", workflow)

    def test_rollout_executes_tooling_from_requested_release(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "rollout.yml").read_text(encoding="utf-8")
        self.assertIn("Checkout platform tooling from requested immutable release", workflow)
        self.assertIn("ref: ${{ needs.plan.outputs.version }}", workflow)
        self.assertIn("python3 platform/scripts/rollout_project.py", workflow)

    def test_release_dispatches_exact_rollout_workflow(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "publish-version.yml").read_text(encoding="utf-8")
        self.assertIn("actions: write", workflow)
        self.assertIn("gh workflow run rollout.yml", workflow)
        self.assertIn('version=$TAG', workflow)

    def test_rollout_helper_pins_exact_copier_ref_and_keeps_strict_diff_check(self) -> None:
        source = inspect.getsource(rollout_project.copier_update_with_guarded_recopy)
        self.assertIn('"update"', source)
        self.assertIn('"recopy"', source)
        self.assertEqual(source.count('"--vcs-ref"'), 2)
        # Copier 9.17 exposes --conflict on update, but not on recopy.
        self.assertEqual(source.count('"--conflict"'), 1)
        self.assertEqual(source.count('"rej"'), 1)
        script = (ROOT / "scripts" / "rollout_project.py").read_text(encoding="utf-8")
        self.assertIn("normalize_copier_answers(project_root)", script)
        self.assertIn('["git", "diff", "--check", "--"]', script)
        self.assertIn("require_version_coherence", script)
        self.assertNotIn("--force", script.lower())

    def test_copier_preserves_existing_gitignore_for_every_harness_mode(self) -> None:
        copier = (ROOT / "copier.yml").read_text(encoding="utf-8")
        self.assertIn("  - .gitignore\n", copier)
        self.assertNotIn("{{ '.gitignore' if harness_mode == 'project'", copier)
        self.assertIn('".gitignore",', inspect.getsource(rollout_project))


if __name__ == "__main__":
    unittest.main()
