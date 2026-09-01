from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "adopt_project.py"
SPEC = importlib.util.spec_from_file_location("adopt_project", MODULE_PATH)
assert SPEC and SPEC.loader
adopt_project = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adopt_project)


class AdoptProjectTests(unittest.TestCase):
    def test_docs_only_repository_is_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "concepts").mkdir()
            (root / "concepts" / "idea.md").write_text("idea\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "fresh")
            self.assertEqual(reasons, [])
            self.assertEqual(
                adopt_project.plan_adoption(root, kind, reasons),
                {
                    "workflow_profile": "standard",
                    "harness_mode": "platform",
                    "publish_mode": "direct",
                    "reasons": [],
                    "blockers": [],
                    "project_required_files": [],
                },
            )

    def test_process_marker_forces_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            self.assertTrue(any(".github/workflows" in reason for reason in reasons))
            plan = adopt_project.plan_adoption(root, kind, reasons)
            self.assertEqual(plan["workflow_profile"], "standard")
            self.assertEqual(plan["harness_mode"], "platform")
            self.assertEqual(plan["publish_mode"], "pr")
            self.assertEqual(plan["blockers"], [])

    def test_platform_metadata_is_already_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('platform_version = "1.4.0"\n', encoding="utf-8")
            kind, _ = adopt_project.classify_repository(root)
            self.assertEqual(kind, "adopted")

    def test_large_codebase_is_existing_but_does_not_imply_project_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(adopt_project.FRESH_MAX_CODE_FILES + 1):
                (root / f"module_{index}.py").write_text("pass\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            self.assertTrue(any("code files" in reason for reason in reasons))
            plan = adopt_project.plan_adoption(root, kind, reasons)
            self.assertEqual(plan["harness_mode"], "platform")
            self.assertEqual(plan["workflow_profile"], "standard")

    def test_mature_standard_project_harness_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in ("scripts/select_checks.py", "scripts/merge_to_main.py"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# project owned\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            plan = adopt_project.plan_adoption(root, kind, reasons)
            self.assertEqual(plan["harness_mode"], "project")
            self.assertEqual(plan["workflow_profile"], "standard")
            self.assertEqual(plan["publish_mode"], "pr")
            self.assertEqual(plan["blockers"], [])
            self.assertEqual(plan["project_required_files"], ["scripts/merge_to_main.py", "scripts/select_checks.py"])

    def test_jara_like_harness_selects_multi_agent_project_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                "AGENTS.md",
                "openspec/config.yaml",
                ".github/workflows/ci.yml",
                "scripts/select_checks.py",
                "scripts/merge_to_main.py",
                "scripts/agent_board.py",
                "scripts/worktree_cleanup.py",
                "docs/engineering/openspec-workflow.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# project owned\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            plan = adopt_project.plan_adoption(root, kind, reasons)
            self.assertEqual(plan["harness_mode"], "project")
            self.assertEqual(plan["workflow_profile"], "multi-agent")
            self.assertEqual(plan["publish_mode"], "pr")
            self.assertEqual(plan["blockers"], [])
            self.assertTrue(any("coherent project-owned harness" in reason for reason in plan["reasons"]))
            self.assertTrue(any("multi-agent coordination" in reason for reason in plan["reasons"]))

    def test_partial_harness_collision_blocks_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "scripts" / "select_checks.py"
            path.parent.mkdir(parents=True)
            path.write_text("# incompatible selector\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            plan = adopt_project.plan_adoption(root, kind, reasons)
            self.assertEqual(plan["harness_mode"], "platform")
            self.assertTrue(any("ambiguous lifecycle ownership" in blocker for blocker in plan["blockers"]))

    def test_existing_platform_owned_path_without_metadata_blocks(self) -> None:
        for relative in ("scripts/platform_doctor.py", "scripts/independent_review.py"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text("# unknown owner\n", encoding="utf-8")
                kind, reasons = adopt_project.classify_repository(root)
                plan = adopt_project.plan_adoption(root, kind, reasons)
                self.assertTrue(any("platform-owned path" in blocker for blocker in plan["blockers"]))

    def test_defaults_hide_platform_choices_from_human(self) -> None:
        self.assertEqual(
            adopt_project.adoption_defaults("fresh"),
            {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "direct"},
        )
        self.assertEqual(
            adopt_project.adoption_defaults("existing"),
            {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "pr"},
        )

    def test_project_mode_validation_does_not_call_project_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(adopt_project, "run") as run_mock, patch.object(
            adopt_project.shutil, "which", return_value=None
        ):
            adopt_project.validate_project(Path(tmp), "main", "project")
            commands = [call.args[0] for call in run_mock.call_args_list]
            self.assertFalse(any("scripts/select_checks.py" in command for command in commands))

    def test_platform_mode_validation_keeps_selector_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(adopt_project, "run") as run_mock, patch.object(
            adopt_project.shutil, "which", return_value=None
        ):
            adopt_project.validate_project(Path(tmp), "main", "platform")
            commands = [call.args[0] for call in run_mock.call_args_list]
            self.assertIn(
                ["python3", "scripts/select_checks.py", "--base", "origin/main", "--execute"],
                commands,
            )

    def test_configure_project_required_files_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".dev-platform.toml"
            config.write_text('schema_version = 2\nproject_required_files = []\n', encoding="utf-8")
            adopt_project.configure_project_required_files(
                root, ["scripts/select_checks.py", "scripts/merge_to_main.py", "scripts/select_checks.py"]
            )
            text = config.read_text(encoding="utf-8")
            self.assertIn(
                'project_required_files = ["scripts/merge_to_main.py", "scripts/select_checks.py"]',
                text,
            )

    def test_adoption_branch_requires_stable_version(self) -> None:
        self.assertEqual(adopt_project.adoption_branch("v1.4.0"), "dev-platform/adopt-v1.4.0")
        with self.assertRaises(ValueError):
            adopt_project.adoption_branch("main")


if __name__ == "__main__":
    unittest.main()
