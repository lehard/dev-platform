from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("platform_doctor", SCRIPTS / "platform_doctor.py")
assert SPEC and SPEC.loader
platform_doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(platform_doctor)


class RenderedWorkflowModeTests(unittest.TestCase):
    def _root(self, workflow: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        path = root / ".github" / "workflows"
        path.mkdir(parents=True)
        (path / "dev-platform.yml").write_text(workflow, encoding="utf-8")
        return root, tmp

    def test_pr_mode_rejects_stale_push_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  push:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "pr"}, failures)
        self.assertEqual(failures[0], 1)

    def test_pr_mode_accepts_pr_only_render(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "pr"}, failures)
        self.assertEqual(failures[0], 0)

    def test_direct_mode_requires_push_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "direct"}, failures)
        self.assertEqual(failures[0], 1)

    def test_direct_mode_accepts_push_health_trigger(self) -> None:
        root, tmp = self._root("on:\n  pull_request:\n  push:\n  workflow_dispatch:\n")
        self.addCleanup(tmp.cleanup)
        failures = [0]
        platform_doctor.check_rendered_workflow_mode(root, {"publish_mode": "direct"}, failures)
        self.assertEqual(failures[0], 0)

    def test_backlog_config_allows_legacy_renders_but_rejects_partial_authoring_contract(self) -> None:
        failures = [0]
        platform_doctor.check_development_backlog_config({}, failures)
        self.assertEqual(failures[0], 0)
        platform_doctor.check_development_backlog_config(
            {"development_backlog": {"repository": "invalid", "project_label": "dev-platform", "default_priority": "P9"}}, failures
        )
        self.assertEqual(failures[0], 3)


if __name__ == "__main__":
    unittest.main()
