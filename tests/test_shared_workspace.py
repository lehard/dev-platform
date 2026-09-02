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

    def test_fix_repairs_registered_paths_without_touching_git_config(self) -> None:
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
            # Permission audit no longer rewrites stable shared-repository config.
            configured = subprocess.run(
                ["git", "config", "--get", "core.sharedRepository"], cwd=root, text=True, capture_output=True
            )
            self.assertNotEqual(configured.returncode, 0)

    def test_shared_repository_grants_group_accepts_git_aliases(self) -> None:
        for value in ("group", "true", "1", "all", "0660", "0664", "2770"):
            self.assertTrue(shared_workspace.shared_repository_grants_group(value), value)
        for value in (None, "", "umask", "false", "0", "0600", "0640"):
            self.assertFalse(shared_workspace.shared_repository_grants_group(value), value)

    def test_preflight_does_not_rewrite_a_correct_shared_repository_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            (root / ".claude" / "worktrees").mkdir(parents=True)
            shared_workspace.configure_shared_repository(root)
            config = root / ".git" / "config"
            before = config.read_text(encoding="utf-8")

            def forbidden(_root: Path):  # pragma: no cover - must never run
                raise AssertionError("a correct value must not enter the serialized repair path")

            for _ in range(2):
                shared_workspace.preflight(root, serializer=forbidden)
            self.assertEqual(config.read_text(encoding="utf-8"), before)
            self.assertEqual(shared_workspace.read_shared_repository(root), "group")

    def test_preflight_repairs_missing_shared_repository_through_serializer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            (root / ".claude" / "worktrees").mkdir(parents=True)
            self.assertIsNone(shared_workspace.read_shared_repository(root))

            import contextlib

            calls: list[Path] = []

            @contextlib.contextmanager
            def serializer(target: Path):
                calls.append(target)
                yield

            shared_workspace.preflight(root, serializer=serializer)
            self.assertEqual(len(calls), 1)
            self.assertTrue(
                shared_workspace.shared_repository_grants_group(shared_workspace.read_shared_repository(root))
            )

    def test_verify_shared_repository_reports_unset_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            finding = shared_workspace.verify_shared_repository(root)
            self.assertIsNotNone(finding)
            self.assertIn("core.sharedRepository", finding.message)
            self.assertIsNone(shared_workspace.read_shared_repository(root))

    def test_preflight_readonly_mode_reports_misconfiguration_without_repairing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            (root / ".claude" / "worktrees").mkdir(parents=True)
            fake_group = shared_workspace.resolve_shared_group(root)
            with mock.patch.object(shared_workspace, "audit", return_value=(fake_group, [])):
                with self.assertRaises(shared_workspace.SharedWorkspaceError) as raised:
                    shared_workspace.preflight(root, fix=False)
            self.assertIn("core.sharedRepository", str(raised.exception))
            self.assertIsNone(shared_workspace.read_shared_repository(root))

    def test_audit_tolerates_a_registered_path_that_disappears_mid_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            ephemeral = root / ".git" / "refs" / "heads" / "in-flight.lock"
            ephemeral.parent.mkdir(parents=True, exist_ok=True)
            ephemeral.write_text("", encoding="utf-8")
            ephemeral.chmod(0o600)
            real_describe = shared_workspace._describe
            state = {"removed": False}

            def flaky_describe(path: Path, group):
                if path == ephemeral and not state["removed"]:
                    state["removed"] = True
                    ephemeral.unlink()
                    raise FileNotFoundError(str(path))
                return real_describe(path, group)

            with mock.patch.object(shared_workspace, "_describe", side_effect=flaky_describe):
                group, findings = shared_workspace.audit(root, fix=True)
            self.assertIsNotNone(group)
            self.assertFalse(any("in-flight.lock" in str(item.path) for item in findings))

    def test_audit_still_fails_closed_on_a_durable_permission_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir()
            self.init_repo(root)
            state = root / ".claude" / "agents-board.json"
            state.parent.mkdir()
            state.write_text("{}\n", encoding="utf-8")
            state.chmod(0o600)
            group, findings = shared_workspace.audit(root, fix=False)
            self.assertIsNotNone(group)
            self.assertTrue(any(item.path == state.resolve() for item in findings))

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
