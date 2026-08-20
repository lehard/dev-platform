from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_doctor_does_not_require_project_owned_selector_api(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("from select_checks import", source)

    def test_github_hosted_runner_makes_workspace_permissions_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"},
            clear=False,
        ), mock.patch.object(self.module, "audit_shared_workspace") as audit:
            failures = [0]
            self.module.check_shared_workspace(Path(tmp), failures)
        self.assertEqual(failures, [0])
        audit.assert_not_called()

    def test_self_hosted_actions_runner_keeps_workspace_permissions_strict(self) -> None:
        group = type("Group", (), {"name": "local-team", "source": "checkout owner"})()
        finding = type("Finding", (), {"path": Path("shared-state"), "message": "missing group rwx"})()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ,
            {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "self-hosted"},
            clear=False,
        ), mock.patch.object(
            self.module, "audit_shared_workspace", return_value=(group, [finding])
        ) as audit:
            failures = [0]
            self.module.check_shared_workspace(Path(tmp), failures)
        self.assertEqual(failures, [1])
        audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
