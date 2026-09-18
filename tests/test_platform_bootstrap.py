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

    def test_bootstrap_does_not_add_operator_configuration(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("sync_development_backlog_config", source)
        self.assertNotIn("sync_process_health_config", source)

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
