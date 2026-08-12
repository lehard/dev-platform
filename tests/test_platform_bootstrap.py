from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
MODULE_PATH = SCRIPT_ROOT / "platform_bootstrap.py"
# platform_bootstrap imports the bare top-level `_platform_common`; without this
# the module only loads when another test module happened to run first and left
# template/scripts on sys.path, which made this test order-dependent.
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
SPEC = importlib.util.spec_from_file_location("template_platform_bootstrap", MODULE_PATH)
assert SPEC and SPEC.loader
platform_bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_bootstrap)


class PlatformBootstrapTests(unittest.TestCase):
    def test_sync_platform_version_from_stable_copier_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".copier-answers.yml").write_text(
                "_commit: v1.2.1\n_src_path: gh:lehard/dev-platform\n", encoding="utf-8"
            )
            config = root / ".dev-platform.toml"
            config.write_text(
                'schema_version = 2\nplatform_version = "1.0.2"\nproject_name = "Test"\n', encoding="utf-8"
            )
            platform_bootstrap.sync_platform_version(root)
            self.assertIn('platform_version = "1.2.1"', config.read_text(encoding="utf-8"))

    def test_non_semver_copier_commit_does_not_rewrite_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".copier-answers.yml").write_text("_commit: deadbeef\n", encoding="utf-8")
            config = root / ".dev-platform.toml"
            original = 'schema_version = 2\nplatform_version = "1.0.2"\n'
            config.write_text(original, encoding="utf-8")
            platform_bootstrap.sync_platform_version(root)
            self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_development_backlog_migration_adds_only_the_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".dev-platform.toml"
            config.write_text('project_slug = "existing-project"\ncustom_value = "preserve"\n', encoding="utf-8")
            platform_bootstrap.sync_development_backlog_config(root)
            text = config.read_text(encoding="utf-8")
            self.assertIn('custom_value = "preserve"', text)
            self.assertIn('[development_backlog]', text)
            self.assertIn('project_label = "project:existing-project"', text)
            self.assertIn('project_owner = "lehard"', text)
            self.assertIn('project_number = 1', text)
            platform_bootstrap.sync_development_backlog_config(root)
            self.assertEqual(text, config.read_text(encoding="utf-8"))

    def test_development_backlog_migration_adds_locator_inside_existing_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".dev-platform.toml"
            config.write_text(
                'project_slug = "existing-project"\n\n'
                '[development_backlog]\nrepository = "lehard/development-backlog"\n'
                'project_label = "project:existing-project"\ndefault_priority = "P2"\n\n'
                '[paths]\nchecks = "dev-platform/checks.toml"\n',
                encoding="utf-8",
            )
            platform_bootstrap.sync_development_backlog_config(root)
            loaded = platform_bootstrap.load_config(root)
            self.assertEqual(loaded["development_backlog"]["project_owner"], "lehard")
            self.assertEqual(loaded["development_backlog"]["project_number"], 1)
            self.assertNotIn("project_owner", loaded["paths"])

    def test_development_backlog_migration_uses_copier_locator_answers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".copier-answers.yml").write_text(
                "development_backlog_project_owner: example-owner\n"
                "development_backlog_project_number: 42\n",
                encoding="utf-8",
            )
            config = root / ".dev-platform.toml"
            config.write_text('project_slug = "existing-project"\n', encoding="utf-8")
            platform_bootstrap.sync_development_backlog_config(root)
            loaded = platform_bootstrap.load_config(root)
            self.assertEqual(loaded["development_backlog"]["project_owner"], "example-owner")
            self.assertEqual(loaded["development_backlog"]["project_number"], 42)


if __name__ == "__main__":
    unittest.main()
