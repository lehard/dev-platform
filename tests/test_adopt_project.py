from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

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

    def test_process_marker_forces_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            self.assertTrue(any(".github/workflows" in reason for reason in reasons))

    def test_platform_metadata_is_already_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('platform_version = "1.4.0"\n', encoding="utf-8")
            kind, _ = adopt_project.classify_repository(root)
            self.assertEqual(kind, "adopted")

    def test_large_codebase_is_not_fast_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index in range(adopt_project.FRESH_MAX_CODE_FILES + 1):
                (root / f"module_{index}.py").write_text("pass\n", encoding="utf-8")
            kind, reasons = adopt_project.classify_repository(root)
            self.assertEqual(kind, "existing")
            self.assertTrue(any("code files" in reason for reason in reasons))

    def test_defaults_hide_platform_choices_from_human(self) -> None:
        self.assertEqual(
            adopt_project.adoption_defaults("fresh"),
            {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "direct"},
        )
        self.assertEqual(
            adopt_project.adoption_defaults("existing"),
            {"workflow_profile": "standard", "harness_mode": "platform", "publish_mode": "pr"},
        )

    def test_adoption_branch_requires_stable_version(self) -> None:
        self.assertEqual(adopt_project.adoption_branch("v1.4.0"), "dev-platform/adopt-v1.4.0")
        with self.assertRaises(ValueError):
            adopt_project.adoption_branch("main")


if __name__ == "__main__":
    unittest.main()
