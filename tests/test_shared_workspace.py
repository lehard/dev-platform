from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("shared_workspace_under_test", SCRIPTS / "shared_workspace.py")
shared_workspace = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = shared_workspace
assert SPEC.loader is not None
SPEC.loader.exec_module(shared_workspace)


class SharedWorkspaceTests(unittest.TestCase):
    def init_repo(self, directory: Path) -> None:
        subprocess.run(["git", "init", "-q", str(directory)], check=True)

    def test_atomic_replacement_keeps_group_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            shared_workspace.atomic_write_text(path, '{"one": 1}\n')
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode & 0o060, 0o060)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"one": 1}\n')

    def test_fix_repairs_registered_paths_and_configures_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            state = root / ".claude" / "agents-board.json"
            state.parent.mkdir()
            state.write_text("{}\n", encoding="utf-8")
            root.chmod(0o755)
            state.chmod(0o600)
            group, findings = shared_workspace.audit(root, fix=True)
            self.assertIsNotNone(group)
            self.assertEqual(findings, [])
            self.assertEqual(root.stat().st_mode & (stat.S_IRWXG | stat.S_ISGID), stat.S_IRWXG | stat.S_ISGID)
            self.assertEqual(state.stat().st_mode & 0o060, 0o060)
            configured = subprocess.run(
                ["git", "config", "--get", "core.sharedRepository"], cwd=root, text=True, capture_output=True, check=True
            )
            self.assertEqual(configured.stdout.strip(), "group")

    def test_worktree_contents_are_not_recursively_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            application_file = root / ".claude" / "worktrees" / "task" / "application.txt"
            application_file.parent.mkdir(parents=True)
            application_file.write_text("owned by the task checkout\n", encoding="utf-8")
            application_file.chmod(0o600)
            shared_workspace.audit(root, fix=True)
            self.assertEqual(stat.S_IMODE(application_file.stat().st_mode), 0o600)

    def test_foreign_claude_symlink_is_ignored_while_owned_state_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            outside = Path(temporary) / "outside"
            outside.mkdir()
            claude = root / ".claude"
            claude.mkdir()
            foreign = claude / "tool-state"
            foreign.symlink_to(outside, target_is_directory=True)
            owned = claude / "agents-board.json"
            owned.write_text("{}\n", encoding="utf-8")
            owned.chmod(0o600)
            group, findings = shared_workspace.audit(root, fix=True)
            self.assertIsNotNone(group)
            self.assertTrue(foreign.is_symlink())
            self.assertEqual(foreign.resolve(), outside.resolve())
            self.assertFalse(any(finding.path == foreign for finding in findings))
            self.assertEqual(owned.stat().st_mode & 0o060, 0o060)

    def test_foreign_transient_cache_is_ignored_during_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            cache = root / ".claude" / "node_modules.partial.while-another-worktree-writes"
            cache.mkdir(parents=True)
            cache_file = cache / "package.json"
            cache_file.write_text('{"partial": true}\n', encoding="utf-8")
            cache_file.chmod(0o600)
            shared_workspace.audit(root, fix=True)
            self.assertEqual(stat.S_IMODE(cache_file.stat().st_mode), 0o600)

    def test_restrictive_git_metadata_is_still_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            config = root / ".git" / "config"
            config.chmod(0o600)
            group, findings = shared_workspace.audit(root, fix=True)
            self.assertIsNotNone(group)
            self.assertFalse(any(finding.path == config for finding in findings))
            self.assertEqual(config.stat().st_mode & 0o060, 0o060)

    def test_foreign_owned_path_reports_minimal_owner_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text("{}\n", encoding="utf-8")
            actual = shared_workspace.resolve_shared_group(path.parent)
            group = shared_workspace.SharedGroup(gid=actual.gid + 1, name="reviewed-group", source="test")
            with mock.patch.object(shared_workspace.os, "chown", side_effect=PermissionError("foreign owner")):
                with self.assertRaises(shared_workspace.SharedWorkspaceError) as raised:
                    shared_workspace._repair(path, group)
            self.assertIn(str(path), str(raised.exception))
            self.assertIn("owner must run: chgrp", str(raised.exception))

    def test_already_correct_path_needs_no_permission_syscall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            path.write_text("{}\n", encoding="utf-8")
            group = shared_workspace.resolve_shared_group(path.parent)
            path.chmod(0o660)
            with mock.patch.object(Path, "chmod", side_effect=AssertionError("chmod must not run for compliant path")):
                shared_workspace._repair(path, group)

    def test_unsupported_platform_is_a_non_mutating_diagnostic(self) -> None:
        with mock.patch.object(shared_workspace, "posix_available", return_value=False):
            group, findings = shared_workspace.audit(Path.cwd())
        self.assertIsNone(group)
        self.assertEqual(len(findings), 1)
        self.assertIn("unavailable", findings[0].message)


if __name__ == "__main__":
    unittest.main()
