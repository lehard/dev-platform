from __future__ import annotations

import os
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

    def test_snapshot_covers_dynamic_required_files_and_product_ci(self) -> None:
        snapshot = rollout_project.snapshot_existing_project_owned(self.root)
        self.assertIn("scripts/project_helper.py", snapshot)
        self.assertIn(".github/workflows/ci.yml", snapshot)
        self.assertIn("scripts/start_task.py", snapshot)

    def test_platform_snapshot_excludes_platform_harness_scripts(self) -> None:
        self.use_platform_mode()
        snapshot = rollout_project.snapshot_existing_project_owned(self.root)
        self.assertIn("AGENTS.md", snapshot)
        self.assertIn("scripts/project_helper.py", snapshot)
        self.assertIn(".github/workflows/ci.yml", snapshot)
        self.assertNotIn("scripts/start_task.py", snapshot)

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

        def fake_git_tree(root, treeish, relative):
            self.assertEqual(treeish, "HEAD")
            return downstream[relative]

        def fake_baseline(tag, relative, *, env):
            self.assertEqual(tag, "v1.2.3")
            return baseline[relative]

        with (
            patch.object(rollout_project, "git_tree_path_fingerprint", side_effect=fake_git_tree),
            patch.object(rollout_project, "baseline_template_fingerprint", side_effect=fake_baseline),
        ):
            proven = rollout_project.baseline_equivalent_conflict_paths(
                self.root,
                "v1.2.3",
                set(downstream),
                env=os.environ.copy(),
            )
        self.assertEqual(
            proven,
            {"scripts/finish_task.py", "tests/test_git_lifecycle.py"},
        )

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
            patch.object(rollout_project, "require_paths_match_target_template"),
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