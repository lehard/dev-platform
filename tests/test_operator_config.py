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
MANAGED_PROJECTS_SPEC = importlib.util.spec_from_file_location("operator_config_managed_projects", ROOT / "scripts" / "managed_projects.py")
assert MANAGED_PROJECTS_SPEC and MANAGED_PROJECTS_SPEC.loader
managed_projects = importlib.util.module_from_spec(MANAGED_PROJECTS_SPEC)
MANAGED_PROJECTS_SPEC.loader.exec_module(managed_projects)


class OperatorConfigTests(unittest.TestCase):
    def test_external_operator_config_augments_explicitly_opted_in_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "operator.toml"
            operator.write_text('[promotion]\nrepo = "example/dev-platform"\n', encoding="utf-8")
            (root / ".dev-platform.toml").write_text(
                '[operator]\nenabled = true\nconfig_path = "operator.toml"\n\n[paths]\nchecks = "dev-platform/checks.toml"\n',
                encoding="utf-8",
            )
            # This fixture exercises the explicit project-local path. It must
            # not inherit an operator's live environment binding from the
            # process that runs the platform suite.
            with mock.patch.dict(os.environ, {}, clear=True):
                config = platform_common.read_platform_config(root)
            self.assertEqual(config["promotion"]["repo"], "example/dev-platform")

    def test_portable_project_does_not_require_operator_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".dev-platform.toml").write_text('project_slug = "portable"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(platform_common.read_platform_config(root)["project_slug"], "portable")

    def test_global_operator_environment_does_not_enable_portable_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "operator.toml"
            external.write_text('[development_backlog]\nrepository = "example/backlog"\n', encoding="utf-8")
            (root / ".dev-platform.toml").write_text('project_slug = "portable"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"DEV_PLATFORM_OPERATOR_CONFIG": str(external)}, clear=True):
                config = platform_common.read_platform_config(root)
                self.assertNotIn("development_backlog", config)

    def test_global_operator_environment_works_after_explicit_enablement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "operator.toml"
            external.write_text('[promotion]\nrepo = "example/dev-platform"\n', encoding="utf-8")
            (root / ".dev-platform.toml").write_text('[operator]\nenabled = true\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {"DEV_PLATFORM_OPERATOR_CONFIG": str(external)}, clear=True):
                self.assertEqual(platform_common.read_platform_config(root)["promotion"]["repo"], "example/dev-platform")

    def test_operator_config_never_relabels_an_opted_in_project(self) -> None:
        project = (
            '[operator]\nenabled = true\nconfig_path = "operator.toml"\n\n'
            '[development_backlog]\nrepository = "example/backlog"\nproject_label = "project:terrazzo_mvp"\n'
        )
        for operator, message in (
            ('[development_backlog]\nproject_label = "project:dev-platform"\n',
             "development_backlog.project_label = 'project:dev-platform'.*has 'project:terrazzo_mvp'"),
            ('[development_backlog]\nproject_number = 1\n', "development_backlog.project_number = 1.*has absent"),
            ('development_backlog = "x"\n', "must be a TOML table"),
        ):
            with self.subTest(operator=operator), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "operator.toml").write_text(operator, encoding="utf-8")
                (root / ".dev-platform.toml").write_text(project, encoding="utf-8")
                with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, message):
                    platform_common.read_platform_config(root)

    def test_operator_config_may_repeat_but_not_supply_project_backlog_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "operator.toml").write_text('[development_backlog]\nproject_label = "project:self"\n', encoding="utf-8")
            (root / ".dev-platform.toml").write_text(
                '[operator]\nenabled = true\nconfig_path = "operator.toml"\n\n[development_backlog]\nproject_label = "project:self"\n',
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(platform_common.read_platform_config(root)["development_backlog"], {"project_label": "project:self"})
            (root / ".dev-platform.toml").write_text('[operator]\nenabled = true\nconfig_path = "operator.toml"\n', encoding="utf-8")
            with mock.patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, "has absent"):
                platform_common.read_platform_config(root)

    def test_registry_resolution_requires_opt_in_and_uses_external_operator_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "operator.toml"
            registry = root / "managed-projects.json"
            registry.write_text('{"projects": []}\n', encoding="utf-8")
            operator.write_text(
                f'[rollout]\nregistry_path = "{registry}"\n',
                encoding="utf-8",
            )
            (root / ".dev-platform.toml").write_text('[operator]\nenabled = true\nconfig_path = "operator.toml"\n', encoding="utf-8")
            self.assertEqual(managed_projects.configured_registry(root=root), registry)
            (root / ".dev-platform.toml").write_text('[operator]\nenabled = false\nconfig_path = "operator.toml"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "explicitly enable"):
                managed_projects.configured_registry(root=root)

    def test_operator_toml_rejects_project_backlog_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "operator.toml").write_text(
                '[rollout]\nregistry_path = "/secure/registry.json"\n\n[development_backlog]\nproject_label = "project:x"\n',
                encoding="utf-8",
            )
            (root / ".dev-platform.toml").write_text('[operator]\nenabled = true\nconfig_path = "operator.toml"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must not contain \\[development_backlog\\]"):
                managed_projects.configured_operator_toml(root=root)


if __name__ == "__main__":
    unittest.main()
