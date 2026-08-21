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


class TaskStartContractTests(unittest.TestCase):
    """File-presence alone let a stale rendered start_task.py pass doctor while

    still crashing managed intake before package discovery (dev-platform#298).
    check_task_start_contract must actually import the rendered module and
    probe the callable surface scripts/start_managed_task.py depends on.
    """

    TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"

    def setUp(self) -> None:
        self.module = load_module()

    def _write_compatible_start_task(self, scripts_dir: Path) -> None:
        for name in ("start_task.py", "_platform_common.py", "rollout_preflight.py", "start_worktree.py"):
            (scripts_dir / name).write_text((self.TEMPLATE_SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")

    def test_skips_when_harness_is_not_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "start_task.py").write_text("raise SystemExit(2)\n", encoding="utf-8")
            failures = [0]
            self.module.check_task_start_contract(root, {}, "project", failures)
        self.assertEqual(failures, [0])

    def test_skips_the_self_hosted_source_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "start_task.py").write_text("raise SystemExit(2)\n", encoding="utf-8")
            failures = [0]
            self.module.check_task_start_contract(root, {"platform_version": "source"}, "platform", failures)
        self.assertEqual(failures, [0])

    def test_passes_for_a_compatible_rendered_start_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            self._write_compatible_start_task(scripts)
            failures = [0]
            self.module.check_task_start_contract(root, {"platform_version": "1.4.37"}, "platform", failures)
        self.assertEqual(failures, [0])

    def test_fails_when_the_rendered_module_is_missing_the_managed_intake_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "start_task.py").write_text("def start_task():\n    pass\n", encoding="utf-8")
            failures = [0]
            self.module.check_task_start_contract(root, {"platform_version": "1.4.37"}, "platform", failures)
        self.assertEqual(failures, [1])

    def test_repeated_in_process_probes_do_not_leak_between_project_roots(self) -> None:
        # start_task.py's own transitive imports (_platform_common,
        # rollout_preflight, start_worktree) must be reimported fresh from
        # each root's scripts/ dir, not silently reused from whatever a
        # prior probe -- or the module under test's own top-level imports --
        # already cached under those generic module names.
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            root1 = Path(tmp1)
            (root1 / "scripts").mkdir()
            self._write_compatible_start_task(root1 / "scripts")

            root2 = Path(tmp2)
            (root2 / "scripts").mkdir()
            (root2 / "scripts" / "start_task.py").write_text(
                "from _platform_common import totally_missing_helper\n\n"
                "class StartedTask:\n    pass\n\n"
                "def start_task():\n    pass\n\n"
                "def cleanup_started_task():\n    pass\n\n"
                "def admit_task():\n    pass\n\n"
                "def admission_reason():\n    pass\n",
                encoding="utf-8",
            )
            (root2 / "scripts" / "_platform_common.py").write_text("# does not define totally_missing_helper\n", encoding="utf-8")

            failures1 = [0]
            self.module.check_task_start_contract(root1, {"platform_version": "1.4.37"}, "platform", failures1)
            failures2 = [0]
            self.module.check_task_start_contract(root2, {"platform_version": "1.4.37"}, "platform", failures2)
            failures1_again = [0]
            self.module.check_task_start_contract(root1, {"platform_version": "1.4.37"}, "platform", failures1_again)

        self.assertEqual(failures1, [0])
        self.assertEqual(failures2, [1])
        self.assertEqual(failures1_again, [0])

    def test_fails_closed_when_the_rendered_module_cannot_be_imported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "start_task.py").write_text("import this_module_does_not_exist\n", encoding="utf-8")
            failures = [0]
            self.module.check_task_start_contract(root, {"platform_version": "1.4.37"}, "platform", failures)
        self.assertEqual(failures, [1])


if __name__ == "__main__":
    unittest.main()
