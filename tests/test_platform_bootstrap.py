from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
MODULE_PATH = SCRIPT_ROOT / "platform_bootstrap.py"
# platform_bootstrap imports the bare top-level `_platform_common`; without this
# the module only loads when another test module happened to run first and left
# template/scripts on sys.path, which made this test order-dependent.
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _platform_config import platform_config_text, write_platform_config  # noqa: E402
SPEC = importlib.util.spec_from_file_location("template_platform_bootstrap", MODULE_PATH)
assert SPEC and SPEC.loader
platform_bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_bootstrap)


class RemovedDeepSeekSectionTests(unittest.TestCase):
    """BR-845: an update's bootstrap removes the shipped DeepSeek section; any other form fails on read."""

    SHIPPED = platform_bootstrap.SHIPPED_DEEPSEEK_COMMENT + platform_bootstrap.SHIPPED_DEEPSEEK_SECTION

    def config(self, root: Path, section: str) -> Path:
        return write_platform_config(root, extra="[independent_review]\nenabled = false\n\n" + section + "\n[other]\nkey = 1\n")

    def test_shipped_section_is_removed_and_the_rest_kept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.config(root, self.SHIPPED)
            platform_bootstrap.remove_shipped_deepseek_section(root)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("deepseek", text.lower())
            self.assertIn("[independent_review]\nenabled = false\n\n[other]\nkey = 1\n", text)
            platform_bootstrap.load_config(root)  # valid after the removal
            platform_bootstrap.remove_shipped_deepseek_section(root)  # idempotent
            self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_modified_section_is_kept_and_fails_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self.config(root, self.SHIPPED.replace("enabled = false", "enabled = true"))
            before = path.read_text(encoding="utf-8")
            platform_bootstrap.remove_shipped_deepseek_section(root)
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            with self.assertRaisesRegex(Exception, r"still has \[experimental_runtime\.deepseek_harness\].*delete that section"):
                platform_bootstrap.load_config(root)


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

    def test_bootstrap_adds_only_selected_generic_operator_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_platform_config(root)
            (root / ".copier-answers.yml").write_text("operator_integration: true\n", encoding="utf-8")
            platform_bootstrap.sync_operator_integration(root)
            self.assertIn('config_env = "DEV_PLATFORM_OPERATOR_CONFIG"', (root / ".dev-platform.toml").read_text(encoding="utf-8"))

    def test_bootstrap_preserves_enabled_legacy_operator_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".dev-platform.toml"
            original = platform_config_text(extra='[operator]\nenabled = true\nconfig_path = "operator.toml"')
            config.write_text(original, encoding="utf-8")
            (root / ".copier-answers.yml").write_text("operator_integration: true\n", encoding="utf-8")
            platform_bootstrap.sync_operator_integration(root)
            self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_bootstrap_rejects_conflicting_existing_operator_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".dev-platform.toml"
            original = platform_config_text(extra="[operator]\nenabled = false")
            config.write_text(original, encoding="utf-8")
            (root / ".copier-answers.yml").write_text("operator_integration: true\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "conflicts"):
                platform_bootstrap.sync_operator_integration(root)
            self.assertEqual(config.read_text(encoding="utf-8"), original)

    def test_capability_sync_runs_only_when_the_rendered_contract_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(platform_bootstrap, "run") as run:
                platform_bootstrap.sync_engineering_capabilities(root)
            run.assert_not_called()
            (root / "scripts").mkdir()
            (root / "dev-platform").mkdir()
            (root / "scripts" / "capability_manager.py").write_text("# fixture\n", encoding="utf-8")
            (root / "dev-platform" / "capabilities.toml").write_text("version = 1\nenabled = []\n", encoding="utf-8")
            result = type("Result", (), {"returncode": 0})()
            with mock.patch.object(platform_bootstrap, "run", return_value=result) as run:
                platform_bootstrap.sync_engineering_capabilities(root)
            self.assertIn("--quiet", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
