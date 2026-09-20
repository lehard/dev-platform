from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rollout_project  # noqa: E402


class RolloutValidationOwnershipTests(unittest.TestCase):
    def _fixture(self, harness: str) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / ".dev-platform.toml").write_text(
            f'platform_version = "1.4.7"\nharness_mode = "{harness}"\n',
            encoding="utf-8",
        )
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "platform_doctor.py").write_text("print('ok')\n", encoding="utf-8")
        return root, tmp

    def test_project_harness_does_not_invoke_project_owned_selector(self) -> None:
        root, tmp = self._fixture("project")
        self.addCleanup(tmp.cleanup)
        commands: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path, **_: object):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(rollout_project, "run", side_effect=fake_run):
            rollout_project.run_project_validation(root, "main")

        self.assertIn(["git", "diff", "--check", "--"], commands)
        self.assertIn(["python3", str(root / "scripts" / "platform_doctor.py")], commands)
        self.assertFalse(any("select_checks.py" in " ".join(command) for command in commands))

    def test_platform_harness_keeps_platform_selector_execution(self) -> None:
        root, tmp = self._fixture("platform")
        self.addCleanup(tmp.cleanup)
        selector = root / "scripts" / "select_checks.py"
        selector.write_text("print('checks')\n", encoding="utf-8")
        commands: list[list[str]] = []

        def fake_run(command: list[str], cwd: Path, **_: object):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(rollout_project, "run", side_effect=fake_run):
            rollout_project.run_project_validation(root, "main")

        self.assertIn(
            ["python3", str(selector), "--base", "origin/main", "--execute"],
            commands,
        )


if __name__ == "__main__":
    unittest.main()
