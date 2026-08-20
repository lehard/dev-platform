from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_project  # noqa: E402


class GuardedRecopyTests(unittest.TestCase):
    def make_project(self) -> Path:
        root = Path(self.tmp.name)
        (root / ".dev-platform.toml").write_text(
            'platform_version = "1.2.3"\n'
            'project_slug = "transition-smoke"\n'
            'harness_mode = "project"\n'
            'workflow_profile = "standard"\n'
            'project_required_files = ["scripts/project_helper.py"]\n',
            encoding="utf-8",
        )
        (root / ".copier-answers.yml").write_text(
            "_commit: v1.2.3\n_src_path: gh:lehard/dev-platform\n",
            encoding="utf-8",
        )
        target_common = (
            rollout_project.PLATFORM_ROOT / "template" / "scripts" / "_platform_common.py"
        ).read_text(encoding="utf-8")
        for relative, content in {
            ".gitignore": ".env\nconfig/*credentials.json\nvar/*.sqlite3\nnode_modules/\ndist/\n*.tsbuildinfo\n",
            "AGENTS.md": "project agents\n",
            "scripts/start_task.py": "print('project start')\n",
            "scripts/platform_bootstrap.py": "print('candidate bootstrap')\n",
            "scripts/project_helper.py": "print('helper')\n",
            "scripts/_platform_common.py": target_common,
            ".github/workflows/ci.yml": "name: Product CI\n",
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def use_platform_mode(self) -> None:
        config = self.root / ".dev-platform.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                'harness_mode = "project"', 'harness_mode = "platform"'
            ),
            encoding="utf-8",
        )

    def copy_target_template(self, relative: str) -> None:
        source = rollout_project.PLATFORM_ROOT / "template" / relative
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.make_project()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_platform_config_contract_ignores_only_release_version(self) -> None:
        before = rollout_project.platform_config_contract(self.root)
        path = self.root / ".dev-platform.toml"
        path.write_text(path.read_text(encoding="utf-8").replace('1.2.3', '1.3.1'), encoding="utf-8")
        after = rollout_project.platform_config_contract(self.root)
        self.assertEqual(before, after)

    def test_project_publication_conformance_accepts_exact_head_surface_without_rewriting_it(self) -> None:
        publication = self.root / "scripts" / "project_publish.py"
        original = (
            "# dev-platform:exact-head-publication-v1\n"
            "FIELDS = 'headRefOid'\n"
            "COMMAND = ['gh', 'pr', 'merge', '17', '--match-head-commit', expected_head]\n"
        )
        publication.write_text(original, encoding="utf-8")
        rollout_project.require_project_publication_safety_conformance(self.root)
        self.assertEqual(publication.read_text(encoding="utf-8"), original)

    def test_project_publication_conformance_rejects_unsafe_or_unknown_shape_without_overwrite(self) -> None:
        publication = self.root / "scripts" / "project_publish.py"
        original = "subprocess.run(['gh', 'pr', 'view', branch])\n"
        publication.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "branch-name-only PR lookup"):
            rollout_project.require_project_publication_safety_conformance(self.root)
        self.assertEqual(publication.read_text(encoding="utf-8"), original)

    def test_recognized_jara_fixture_gets_a_narrow_idempotent_exact_head_override(self) -> None:
        target = self.root / "scripts" / "merge_to_main.py"
        original = (
            "def preserve_board_worktree_and_serialized_integration():\n"
            "    return 'jara-specific-flow'\n\n"
            "def publish_branch_and_pr(worktree, branch, env):\n"
            "    return branch\n\n"
            "def wait_for_pr_checks(worktree, branch, env):\n"
            "    return branch\n\n"
            "def merge_pr(worktree, branch, env):\n"
            "    return branch\n\n"
            "if __name__ == '__main__':\n"
            "    pass\n"
        )
        target.write_text(original, encoding="utf-8")
        fingerprint = hashlib.sha256(original.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "JARA_MERGE_TO_MAIN_SHA256", fingerprint):
            self.assertTrue(
                rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin")
            )
            self.assertFalse(
                rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin")
            )

        migrated = target.read_text(encoding="utf-8")
        self.assertIn("preserve_board_worktree_and_serialized_integration", migrated)
        self.assertIn("from exact_head_safety import exact_pr", migrated)
        self.assertLess(migrated.index("merge_exact_pr(worktree, pr, head, env)"), migrated.index("delete_remote_branch(worktree, branch)"))
        self.assertEqual(
            (self.root / "scripts" / "exact_head_safety.py").read_text(encoding="utf-8"),
            rollout_project.EXACT_HEAD_HELPER,
        )
        rollout_project.require_project_publication_safety_conformance(self.root)

    def test_recognized_planner_fixture_preserves_its_standalone_clone_entrypoint(self) -> None:
        target = self.root / "scripts" / "project_publish.py"
        original = (
            "def push_feature_branch(root, remote, main_branch):\n"
            "    return 'planner-specific-clone-flow'\n\n"
            "def publish_pr(root, remote, main_branch, title, body, merge_mode):\n"
            "    return 0\n\n"
            "if __name__ == '__main__':\n"
            "    pass\n"
        )
        target.write_text(original, encoding="utf-8")
        fingerprint = hashlib.sha256(original.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "PLANNER_PROJECT_PUBLISH_SHA256", fingerprint):
            self.assertTrue(
                rollout_project.migrate_project_publication_safety(
                    self.root, "lehard/planner-agent-lab"
                )
            )
            self.assertFalse(
                rollout_project.migrate_project_publication_safety(
                    self.root, "lehard/planner-agent-lab"
                )
            )

        migrated = target.read_text(encoding="utf-8")
        self.assertIn("push_feature_branch(root, remote, main_branch)", migrated)
        self.assertIn("ensure_exact_pr(root, current, main_branch", migrated)
        self.assertIn("merge_exact_pr(root, pr, head, env)", migrated)
        rollout_project.require_project_publication_safety_conformance(self.root)

    def write_stale_pr_tools(self) -> dict[str, str]:
        """Make CLI fixtures see old merged PR A while the branch resolves to B."""
        tools = self.root / "fake-tools"
        tools.mkdir()
        head_a = "a" * 40
        head_b = "b" * 40
        (tools / "git").write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' '{head_b}'\n",
            encoding="utf-8",
        )
        (tools / "gh").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"list\" ]; then\n"
            "  printf '%s\\n' '"
            f"[{{\"number\":41,\"url\":\"https://example.test/pr/41\",\"state\":\"MERGED\",\"headRefOid\":\"{head_a}\",\"baseRefName\":\"main\",\"headRefName\":\"task\"}}]"
            "'\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        for command in (tools / "git", tools / "gh"):
            command.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(tools) + os.pathsep + env.get("PATH", "")
        return env

    def test_jara_cli_activates_exact_head_override_before_guard(self) -> None:
        target = self.root / "scripts" / "merge_to_main.py"
        source = '''class MergeError(RuntimeError):
    pass

def preserve_board_worktree_and_serialized_integration():
    print("board-worktree-serialized")

def run_git(*args):
    return type("Result", (), {"stdout": "fixture title\\n"})()

def delete_remote_branch(worktree, branch):
    print("remote-cleanup")

def publish_branch_and_pr(worktree, branch, env):
    print("legacy-publish")

def wait_for_pr_checks(worktree, branch, env):
    print("legacy-check")

def merge_pr(worktree, branch, env):
    print("legacy-merge")

def main():
    preserve_board_worktree_and_serialized_integration()
    publish_branch_and_pr(".", "task", {})
    wait_for_pr_checks(".", "task", {})
    merge_pr(".", "task", {})
    print("terminal-success")

if __name__ == "__main__":
    main()
'''
        target.write_text(source, encoding="utf-8")
        fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "JARA_MERGE_TO_MAIN_SHA256", fingerprint):
            self.assertTrue(rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin"))

        migrated = target.read_text(encoding="utf-8")
        self.assertLess(
            migrated.index(rollout_project.EXACT_HEAD_MARKER),
            migrated.index('if __name__ == "__main__":'),
        )
        result = subprocess.run(
            [sys.executable, str(target)],
            text=True,
            capture_output=True,
            env=self.write_stale_pr_tools(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("board-worktree-serialized", result.stdout)
        self.assertNotIn("legacy-publish", result.stdout)
        self.assertNotIn("remote-cleanup", result.stdout)
        self.assertNotIn("terminal-success", result.stdout)

    def test_planner_cli_activates_exact_head_override_before_guard(self) -> None:
        target = self.root / "scripts" / "project_publish.py"
        source = '''def require_gh_env(root):
    return {}

def push_feature_branch(root, remote, main_branch):
    print("standalone-integration-clone")
    return "task"

def run_git(*args, **kwargs):
    return type("Result", (), {"stdout": "fixture title\\n"})()

def publish_pr(root, remote, main_branch, title, body, merge_mode):
    print("legacy-publish")
    return 0

def main():
    publish_pr(".", "origin", "main", None, None, "auto")
    print("terminal-success")

if __name__ == "__main__":
    main()
'''
        target.write_text(source, encoding="utf-8")
        fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "PLANNER_PROJECT_PUBLISH_SHA256", fingerprint):
            self.assertTrue(
                rollout_project.migrate_project_publication_safety(
                    self.root, "lehard/planner-agent-lab"
                )
            )

        migrated = target.read_text(encoding="utf-8")
        self.assertLess(
            migrated.index(rollout_project.EXACT_HEAD_MARKER),
            migrated.index('if __name__ == "__main__":'),
        )
        result = subprocess.run(
            [sys.executable, str(target)],
            text=True,
            capture_output=True,
            env=self.write_stale_pr_tools(),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("standalone-integration-clone", result.stdout)
        self.assertNotIn("legacy-publish", result.stdout)
        self.assertNotIn("terminal-success", result.stdout)

    def test_v1_4_34_append_is_relocated_only_when_its_legacy_bytes_are_reviewed(self) -> None:
        target = self.root / "scripts" / "merge_to_main.py"
        source = "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n"
        target.write_text(source.rstrip("\n") + rollout_project.JARA_OVERRIDE, encoding="utf-8")
        helper = self.root / "scripts" / "exact_head_safety.py"
        helper.write_text(rollout_project.EXACT_HEAD_HELPER, encoding="utf-8")
        fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "JARA_MERGE_TO_MAIN_SHA256", fingerprint):
            self.assertTrue(rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin"))
            self.assertFalse(rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin"))

        migrated = target.read_text(encoding="utf-8")
        self.assertLess(migrated.index(rollout_project.EXACT_HEAD_MARKER), migrated.index("if __name__"))

    def test_recognized_source_without_a_unique_cli_guard_fails_closed(self) -> None:
        target = self.root / "scripts" / "merge_to_main.py"
        source = "def publish_branch_and_pr(worktree, branch, env):\n    return branch\n"
        target.write_text(source, encoding="utf-8")
        fingerprint = hashlib.sha256(source.encode("utf-8")).hexdigest()

        with patch.object(rollout_project, "JARA_MERGE_TO_MAIN_SHA256", fingerprint), self.assertRaisesRegex(
            ValueError, "no unique top-level CLI guard"
        ):
            rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin")

        self.assertEqual(target.read_text(encoding="utf-8"), source)
        self.assertFalse((self.root / "scripts" / "exact_head_safety.py").exists())

    def test_drifted_recognized_harness_fails_closed_without_writing_a_helper(self) -> None:
        target = self.root / "scripts" / "merge_to_main.py"
        original = "def downstream_change():\n    return True\n"
        target.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "unrecognized harness bytes"):
            rollout_project.migrate_project_publication_safety(self.root, "lehard/Jara_Fin")

        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertFalse((self.root / "scripts" / "exact_head_safety.py").exists())

    def test_platform_config_contract_allows_only_the_expected_backlog_migration(self) -> None:
        before = rollout_project.platform_config_contract(self.root)
        self.root.joinpath(".dev-platform.toml").write_text(
            self.root.joinpath(".dev-platform.toml").read_text(encoding="utf-8")
            + '\n[development_backlog]\nrepository = "lehard/development-backlog"\nproject_label = "project:transition-smoke"\ndefault_priority = "P2"\nproject_owner = "lehard"\nproject_number = 1\n',
            encoding="utf-8",
        )
        after = rollout_project.platform_config_contract(self.root)
        rollout_project.require_platform_config_contract(before, after)
        after["development_backlog"]["default_priority"] = "P1"
        with self.assertRaisesRegex(ValueError, "beyond platform_version"):
            rollout_project.require_platform_config_contract(before, after)

    def test_platform_config_contract_allows_missing_project_locator_migration(self) -> None:
        before = rollout_project.platform_config_contract(self.root)
        before["development_backlog"] = {
            "repository": "lehard/development-backlog",
            "project_label": "project:transition-smoke",
            "default_priority": "P2",
        }
        after = rollout_project.expected_development_backlog_migration(before)
        assert after is not None
        rollout_project.require_platform_config_contract(before, after)
        after["development_backlog"]["project_number"] = 2
        with self.assertRaisesRegex(ValueError, "beyond platform_version"):
            rollout_project.require_platform_config_contract(before, after)

    def test_platform_config_contract_allows_process_health_migration_only_when_missing(self) -> None:
        before = rollout_project.platform_config_contract(self.root)
        after = rollout_project.expected_process_health_migration(before)
        assert after is not None
        rollout_project.require_platform_config_contract(before, after)
        after["process_health"]["managed_label"] = "custom"
        with self.assertRaisesRegex(ValueError, "bounded platform migrations"):
            rollout_project.require_platform_config_contract(before, after)

    def test_platform_config_contract_uses_reviewed_copier_locator_answers(self) -> None:
        before = rollout_project.platform_config_contract(self.root)
        after = rollout_project.expected_development_backlog_migration(
            before,
            project_owner="example-owner",
            project_number=42,
        )
        assert after is not None
        rollout_project.require_platform_config_contract(
            before,
            after,
            project_owner="example-owner",
            project_number=42,
        )
        with self.assertRaisesRegex(ValueError, "beyond platform_version"):
            rollout_project.require_platform_config_contract(before, after)

    def test_snapshot_covers_dynamic_required_files_and_product_ci(self) -> None:
        snapshot = rollout_project.snapshot_existing_project_owned(self.root)
        self.assertIn("scripts/project_helper.py", snapshot)
        self.assertIn(".github/workflows/ci.yml", snapshot)
        self.assertIn("scripts/start_task.py", snapshot)

    def test_platform_snapshot_excludes_platform_harness_scripts(self) -> None:
        self.use_platform_mode()
        snapshot = rollout_project.snapshot_existing_project_owned(self.root)
        self.assertIn(".gitignore", snapshot)
        self.assertIn("AGENTS.md", snapshot)
        self.assertIn("scripts/project_helper.py", snapshot)
        self.assertIn(".github/workflows/ci.yml", snapshot)
        self.assertNotIn("scripts/start_task.py", snapshot)

    def test_ignore_coverage_guard_detects_only_lost_previously_ignored_paths(self) -> None:
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True, text=True)
        coverage = rollout_project.snapshot_effective_ignore_coverage(self.root)
        self.assertEqual(coverage, set(rollout_project.REPRESENTATIVE_IGNORE_PATHS))
        self.assertFalse(any((self.root / relative).exists() for relative in coverage))

        (self.root / ".gitignore").write_text("# coverage was accidentally removed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "managed rendering removed effective ignore coverage") as error:
            rollout_project.require_effective_ignore_coverage(self.root, coverage)
        self.assertIn(".env (environment secrets)", str(error.exception))

        # The read-only guard does not stage or materialize any of the paths it checks.
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(staged.returncode, 0)
        self.assertFalse(any((self.root / relative).exists() for relative in coverage))

    def test_snapshot_preserves_symlink_identity(self) -> None:
        agents = self.root / "AGENTS.md"
        claude = self.root / "CLAUDE.md"
        claude.symlink_to("AGENTS.md")
        snapshot = rollout_project.snapshot_existing_project_owned(self.root)
        self.assertEqual(snapshot["CLAUDE.md"], ("symlink", "AGENTS.md"))
        claude.unlink()
        claude.write_text(agents.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "project-owned files changed"):
            rollout_project.require_project_owned_snapshot(self.root, snapshot)

    def test_cuby_task_intake_migration_is_the_only_allowed_agents_change(self) -> None:
        self.root.joinpath(".dev-platform.toml").write_text(
            self.root.joinpath(".dev-platform.toml").read_text(encoding="utf-8")
            + '\n[development_backlog]\nrepository = "lehard/development-backlog"\n',
            encoding="utf-8",
        )
        contract = self.root / rollout_project.TASK_INTAKE_REFERENCE
        contract.parent.mkdir(parents=True)
        contract.write_text("# task intake\n", encoding="utf-8")
        before = rollout_project.snapshot_existing_project_owned(self.root)
        agents_before = (self.root / "AGENTS.md").read_text(encoding="utf-8")

        self.assertTrue(rollout_project.reconcile_task_intake_reference(self.root))
        rollout_project.require_project_owned_snapshot(
            self.root,
            before,
            permitted_fingerprints=rollout_project.permitted_task_intake_migration(
                self.root, agents_before
            ),
        )
        self.assertFalse(rollout_project.reconcile_task_intake_reference(self.root))

        (self.root / "AGENTS.md").write_text(
            (self.root / "AGENTS.md").read_text(encoding="utf-8") + "\nproject drift\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "project-owned files changed"):
            rollout_project.require_project_owned_snapshot(
                self.root,
                before,
                permitted_fingerprints=rollout_project.permitted_task_intake_migration(
                    self.root, agents_before
                ),
            )

    def test_cuby_guarded_recopy_accepts_the_task_intake_migration(self) -> None:
        self.root.joinpath(".dev-platform.toml").write_text(
            self.root.joinpath(".dev-platform.toml").read_text(encoding="utf-8")
            + '\n[development_backlog]\nrepository = "lehard/development-backlog"\n',
            encoding="utf-8",
        )
        contract = self.root / rollout_project.TASK_INTAKE_REFERENCE
        contract.parent.mkdir(parents=True)
        contract.write_text("# task intake\n", encoding="utf-8")

        with (
            patch.object(
                rollout_project,
                "run",
                return_value=type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[["scripts/start_task.py.rej"], []],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
        ):
            strategy = rollout_project.copier_update_with_guarded_recopy(
                self.root, "v1.4.31", env=os.environ.copy()
            )

        self.assertEqual(strategy, "guarded-recopy")
        migrated = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(migrated.count(rollout_project.TASK_INTAKE_REFERENCE_MARKER), 1)
        self.assertIn("project agents", migrated)

    def test_task_intake_migration_rejects_duplicate_marker(self) -> None:
        text = (
            "project agents\n"
            + rollout_project.TASK_INTAKE_REFERENCE_MARKER
            + "\n"
            + rollout_project.TASK_INTAKE_REFERENCE_MARKER
        )
        with self.assertRaisesRegex(ValueError, "duplicate task-intake"):
            rollout_project.canonical_task_intake_reference_text(text)

    def test_baseline_equivalence_accepts_unchanged_and_missing_paths_only(self) -> None:
        downstream = {
            "scripts/finish_task.py": ("file", "same"),
            "tests/test_git_lifecycle.py": ("missing", ""),
            "src/runtime.py": ("file", "downstream-change"),
        }
        baseline = {
            "scripts/finish_task.py": ("file", "same"),
            "tests/test_git_lifecycle.py": ("missing", ""),
            "src/runtime.py": ("missing", ""),
        }

        def fake_git_tree(root, treeish, relative, *, normalize_baseline=False):
            self.assertEqual(treeish, "HEAD")
            self.assertTrue(normalize_baseline)
            return downstream[relative]

        def fake_baseline(tag, answers_text, relatives, *, env, baseline_equivalence=False):
            self.assertEqual(tag, "v1.2.3")
            self.assertIn("_commit: v1.2.3", answers_text)
            self.assertEqual(relatives, set(downstream))
            self.assertTrue(baseline_equivalence)
            return baseline

        with (
            patch.object(rollout_project, "git_tree_path_fingerprint", side_effect=fake_git_tree),
            patch.object(rollout_project, "rendered_template_fingerprints", side_effect=fake_baseline),
        ):
            proven = rollout_project.baseline_equivalent_conflict_paths(
                self.root,
                "v1.2.3",
                set(downstream),
                env=os.environ.copy(),
                answers_text=(self.root / ".copier-answers.yml").read_text(encoding="utf-8"),
            )
        self.assertEqual(
            proven,
            {"scripts/finish_task.py", "tests/test_git_lifecycle.py"},
        )

    def test_baseline_format_equivalence_allows_only_redundant_workflow_blank_lines(self) -> None:
        relative = ".github/workflows/dev-platform.yml"
        rendered = self.root / "rendered.yml"
        downstream = self.root / "downstream.yml"
        rendered.write_text("jobs:\n\n\n  platform-ci:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
        downstream.write_text("jobs:\n\n  platform-ci:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
        self.assertEqual(
            rollout_project.baseline_path_fingerprint(rendered, relative),
            rollout_project.baseline_path_fingerprint(downstream, relative),
        )

        comment_changed = self.root / "comment-changed.yml"
        comment_changed.write_text(
            "jobs:\n\n  # downstream customization\n  platform-ci:\n    runs-on: ubuntu-latest\n",
            encoding="utf-8",
        )
        self.assertNotEqual(
            rollout_project.baseline_path_fingerprint(rendered, relative),
            rollout_project.baseline_path_fingerprint(comment_changed, relative),
        )
        self.assertNotEqual(
            rollout_project.baseline_path_fingerprint(rendered, ".github/workflows/ci.yml"),
            rollout_project.baseline_path_fingerprint(downstream, ".github/workflows/ci.yml"),
        )

    def test_baseline_format_equivalence_does_not_normalize_yaml_block_scalars(self) -> None:
        relative = ".github/workflows/dev-platform.yml"
        with_extra_blank = self.root / "with-extra-blank.yml"
        with_extra_blank.write_text("jobs:\n  run: |\n    first\n\n\n    second\n", encoding="utf-8")
        without_extra_blank = self.root / "without-extra-blank.yml"
        without_extra_blank.write_text("jobs:\n  run: |\n    first\n\n    second\n", encoding="utf-8")
        self.assertNotEqual(
            rollout_project.baseline_path_fingerprint(with_extra_blank, relative),
            rollout_project.baseline_path_fingerprint(without_extra_blank, relative),
        )

    def test_baseline_renderer_uses_isolated_task_free_copier_copy(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            rendered = Path(command[-1])
            path = rendered / ".github" / "workflows" / "dev-platform.yml"
            path.parent.mkdir(parents=True)
            path.write_text("rendered baseline\n", encoding="utf-8")
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "ensure_platform_tag_available"),
            patch.object(rollout_project, "run", side_effect=fake_run),
        ):
            fingerprints = rollout_project.rendered_template_fingerprints(
                "v1.2.3",
                "_commit: v1.2.3\nproject_name: Test\n",
                {".github/workflows/dev-platform.yml"},
                env=os.environ.copy(),
            )
        self.assertEqual(
            fingerprints,
            {
                ".github/workflows/dev-platform.yml": (
                    "file",
                    hashlib.sha256(b"rendered baseline\n").hexdigest(),
                )
            },
        )
        self.assertEqual(commands[0][:7], ["copier", "copy", "--trust", "--defaults", "--skip-tasks", "--vcs-ref", "v1.2.3"])
        self.assertIn("--data-file", commands[0])

    def test_failed_prepare_command_is_a_structured_blocker(self) -> None:
        result = type("Result", (), {"returncode": 2, "stdout": None, "stderr": None})()
        with patch.object(rollout_project.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, r"command failed \(exit 2\): git diff --cached --check --"):
                rollout_project.run(["git", "diff", "--cached", "--check", "--"], self.root)

    def test_stage_rollout_changes_excludes_later_validation_artifacts(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            returncode = 1 if command == ["git", "diff", "--cached", "--quiet", "--"] else 0
            return type("Result", (), {"returncode": returncode, "stdout": "", "stderr": ""})()

        with patch.object(rollout_project, "run", side_effect=fake_run):
            rollout_project.stage_rollout_changes(self.root)
        self.assertEqual(
            commands,
            [
                ["git", "add", "-A"],
                ["git", "diff", "--cached", "--quiet", "--"],
                ["git", "diff", "--cached", "--check", "--"],
            ],
        )

    def test_stage_rollout_changes_blocks_empty_or_uninspectable_index(self) -> None:
        empty = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch.object(rollout_project, "run", return_value=empty):
            with self.assertRaisesRegex(ValueError, "produced no repository diff"):
                rollout_project.stage_rollout_changes(self.root)

        broken = type("Result", (), {"returncode": 2, "stdout": "", "stderr": "broken index"})()

        def fake_run(command, cwd, **kwargs):
            return broken if command == ["git", "diff", "--cached", "--quiet", "--"] else empty

        with patch.object(rollout_project, "run", side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, "could not inspect staged rollout changes: broken index"):
                rollout_project.stage_rollout_changes(self.root)

    def test_guarded_recopy_runs_only_for_project_owned_rejects(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[["scripts/start_task.py.rej"], []],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
        ):
            strategy = rollout_project.copier_update_with_guarded_recopy(
                self.root,
                "v1.3.1",
                env=os.environ.copy(),
            )
        self.assertEqual(strategy, "guarded-recopy")
        self.assertTrue(any(command[:2] == ["copier", "update"] for command in commands))
        self.assertTrue(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_reclaimed_platform_conflict_allows_recopy_when_already_on_target(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[["scripts/_platform_common.py.rej"], []],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
        ):
            strategy = rollout_project.copier_update_with_guarded_recopy(
                self.root,
                "v1.3.1",
                env=os.environ.copy(),
            )
        self.assertEqual(strategy, "guarded-recopy")
        self.assertTrue(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_platform_mode_reclaimed_project_publish_allows_guarded_recopy(self) -> None:
        self.use_platform_mode()
        self.copy_target_template("scripts/project_publish.py")
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[["scripts/project_publish.py.rej"], []],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
            patch.object(rollout_project, "baseline_equivalent_conflict_paths", return_value=set()),
        ):
            strategy = rollout_project.copier_update_with_guarded_recopy(
                self.root,
                "v1.4.14",
                env=os.environ.copy(),
            )
        self.assertEqual(strategy, "guarded-recopy")
        self.assertTrue(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_platform_mode_recovers_cuby_shaped_mixed_historical_rejects(self) -> None:
        self.use_platform_mode()
        self.copy_target_template("scripts/project_publish.py")
        (self.root / "scripts" / "finish_task.py").write_text(
            "# exact recorded-baseline bytes in the real Cuby reproduction\n",
            encoding="utf-8",
        )
        commands: list[list[str]] = []
        baseline = {"scripts/finish_task.py", "tests/test_git_lifecycle.py"}

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[
                    [
                        "scripts/finish_task.py.rej",
                        "scripts/project_publish.py.rej",
                        "tests/test_git_lifecycle.py.rej",
                    ],
                    [],
                ],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
            patch.object(
                rollout_project,
                "baseline_equivalent_conflict_paths",
                return_value=baseline,
            ),
            patch.object(rollout_project, "require_paths_match_rendered_template"),
        ):
            strategy = rollout_project.copier_update_with_guarded_recopy(
                self.root,
                "v1.4.15",
                env=os.environ.copy(),
            )
        self.assertEqual(strategy, "guarded-recopy")
        self.assertTrue(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_platform_mode_reclaimed_project_publish_blocks_if_divergent(self) -> None:
        self.use_platform_mode()
        project_publish = self.root / "scripts" / "project_publish.py"
        project_publish.write_text("# downstream override still differs\n", encoding="utf-8")
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                return_value=["scripts/project_publish.py.rej"],
            ),
            patch.object(rollout_project, "baseline_equivalent_conflict_paths", return_value=set()),
        ):
            with self.assertRaisesRegex(ValueError, "non-recoverable conflicts"):
                rollout_project.copier_update_with_guarded_recopy(
                    self.root,
                    "v1.4.15",
                    env=os.environ.copy(),
                )
        self.assertFalse(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_reclaimed_platform_conflict_blocks_if_downstream_differs(self) -> None:
        common = self.root / "scripts" / "_platform_common.py"
        common.write_text("# downstream customization still present\n", encoding="utf-8")
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                return_value=["scripts/_platform_common.py.rej"],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "non-recoverable conflicts"):
                rollout_project.copier_update_with_guarded_recopy(
                    self.root,
                    "v1.3.1",
                    env=os.environ.copy(),
                )
        self.assertFalse(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_non_project_owned_conflict_blocks_without_recopy(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command, cwd, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                return_value=["src/runtime.py.rej"],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "non-recoverable conflicts"):
                rollout_project.copier_update_with_guarded_recopy(
                    self.root,
                    "v1.3.1",
                    env=os.environ.copy(),
                )
        self.assertFalse(any(command[:2] == ["copier", "recopy"] for command in commands))

    def test_recopy_is_blocked_if_protected_file_changes(self) -> None:
        def fake_run(command, cwd, **kwargs):
            if command[:2] == ["copier", "recopy"]:
                (self.root / "scripts/start_task.py").write_text("changed by recopy\n", encoding="utf-8")
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with (
            patch.object(rollout_project, "run", side_effect=fake_run),
            patch.object(
                rollout_project,
                "find_reject_files",
                side_effect=[["scripts/start_task.py.rej"], []],
            ),
            patch.object(rollout_project, "reset_failed_copier_update"),
        ):
            with self.assertRaisesRegex(ValueError, "project-owned files changed"):
                rollout_project.copier_update_with_guarded_recopy(
                    self.root,
                    "v1.3.1",
                    env=os.environ.copy(),
                )

    def test_platform_mode_blocks_real_divergence_even_with_baseline_recovery(self) -> None:
        self.use_platform_mode()
        with (
            patch.object(
                rollout_project,
                "run",
                return_value=type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            ),
            patch.object(
                rollout_project,
                "find_reject_files",
                return_value=["scripts/start_task.py.rej"],
            ),
            patch.object(rollout_project, "baseline_equivalent_conflict_paths", return_value=set()),
        ):
            with self.assertRaisesRegex(ValueError, "Copier left unresolved"):
                rollout_project.copier_update_with_guarded_recopy(
                    self.root,
                    "v1.4.15",
                    env=os.environ.copy(),
                )


if __name__ == "__main__":
    unittest.main()
