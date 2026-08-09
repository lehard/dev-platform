from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "template" / "scripts" / "platform_bootstrap.py"
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


if __name__ == "__main__":
    unittest.main()
