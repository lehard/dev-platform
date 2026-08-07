from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "template" / "scripts" / "platform_doctor.py"


def load_module():
    import sys
    sys.path.insert(0, str(ROOT / "template" / "scripts"))
    spec = importlib.util.spec_from_file_location("platform_doctor_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ConflictGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_rej_file_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            (root / "update.rej").write_text("rejected hunk\n", encoding="utf-8")
            issues = self.module.find_update_conflicts(root)
            self.assertIn("update.rej", issues)

    def test_inline_git_conflict_marker_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
            path = root / "sample.txt"
            path.write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "sample.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
            path.write_text("<<<<<<< ours\na\n=======\nb\n>>>>>>> theirs\n", encoding="utf-8")
            issues = self.module.find_update_conflicts(root)
            self.assertTrue(any("leftover conflict marker" in issue.lower() for issue in issues))

    def test_clean_repo_has_no_conflict_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            self.assertEqual([], self.module.find_update_conflicts(root))


if __name__ == "__main__":
    unittest.main()
