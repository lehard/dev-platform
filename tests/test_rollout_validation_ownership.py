from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
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

    def test_harness_validation_retains_platform_checks_and_defers_product_verification(self) -> None:
        for harness in ("platform", "project"):
            with self.subTest(harness_mode=harness):
                root, tmp = self._fixture(harness)
                self.addCleanup(tmp.cleanup)
                selector = root / "scripts" / "select_checks.py"
                selector.write_text("raise SystemExit('must not run')\n", encoding="utf-8")
                commands: list[list[str]] = []

                def fake_run(command: list[str], cwd: Path, **_: object):
                    commands.append(command)
                    return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

                output = StringIO()
                with patch.object(rollout_project, "run", side_effect=fake_run), redirect_stdout(output):
                    rollout_project.run_project_validation(root, "main")

                self.assertEqual(
                    commands,
                    [
                        ["git", "diff", "--check", "--"],
                        ["python3", str(root / "scripts" / "platform_doctor.py")],
                    ],
                )
                self.assertFalse(any("select_checks.py" in " ".join(command) for command in commands))
                self.assertIn("downstream rollout PR CI verifies product behavior", output.getvalue())


if __name__ == "__main__":
    unittest.main()
