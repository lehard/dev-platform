from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "template" / "scripts" / "_platform_common.py"
SPEC = importlib.util.spec_from_file_location("operator_config_common", MODULE_PATH)
assert SPEC and SPEC.loader
platform_common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_common)


class OperatorConfigTests(unittest.TestCase):
    def test_external_operator_config_augments_explicitly_opted_in_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "operator.toml"
            operator.write_text('[development_backlog]\nrepository = "example/backlog"\n', encoding="utf-8")
            (root / ".dev-platform.toml").write_text(
                '[operator]\nconfig_path = "operator.toml"\n\n[paths]\nchecks = "dev-platform/checks.toml"\n',
                encoding="utf-8",
            )
            config = platform_common.read_platform_config(root)
            self.assertEqual(config["development_backlog"]["repository"], "example/backlog")

    def test_portable_project_does_not_require_operator_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('project_slug = "portable"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(platform_common.read_platform_config(root)["project_slug"], "portable")


if __name__ == "__main__":
    unittest.main()
