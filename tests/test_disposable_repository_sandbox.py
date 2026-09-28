from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "template" / "scripts" / "disposable_repository_sandbox.py"
SPEC = importlib.util.spec_from_file_location("disposable_repository_sandbox", SCRIPT)
assert SPEC and SPEC.loader
sandbox = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sandbox
SPEC.loader.exec_module(sandbox)


def git(path: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=path, check=True, capture_output=True, text=True)


class DisposableRepositorySandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.source = base / "source"
        self.root = base / "sandboxes"
        self.source.mkdir()
        self.root.mkdir()
        git(self.source, "init", "-q")
        git(self.source, "config", "user.name", "Sandbox Test")
        git(self.source, "config", "user.email", "sandbox@example.invalid")
        (self.source / "tracked.txt").write_text("original\n", encoding="utf-8")
        git(self.source, "add", "tracked.txt")
        git(self.source, "commit", "-qm", "initial")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def loose_source_object(self) -> Path:
        candidates = list((self.source / ".git" / "objects").glob("[0-9a-f][0-9a-f]/*"))
        self.assertTrue(candidates)
        return candidates[0]

    def marker(self, destination: Path) -> None:
        (destination / sandbox.MARKER).write_text(
            json.dumps({"version": 1, "root": str(self.root.resolve()), "destination": str(destination.resolve()), "source": str(self.source.resolve())}) + "\n",
            encoding="utf-8",
        )

    def test_create_verify_and_cleanup_make_an_independent_copy(self) -> None:
        destination = sandbox.create(str(self.source), str(self.root), "pilot")
        self.assertEqual(sandbox._verify(self.root.resolve(), "pilot"), destination)
        source_object = self.loose_source_object()
        copied = destination / ".git" / "objects" / source_object.parent.name / source_object.name
        self.assertTrue(copied.exists())
        self.assertNotEqual((source_object.stat().st_dev, source_object.stat().st_ino), (copied.stat().st_dev, copied.stat().st_ino))
        copied.chmod(0o600)
        self.assertNotEqual(stat.S_IMODE(source_object.stat().st_mode), 0o600)
        sandbox._remove_owned_tree(destination, self.root.resolve())
        self.assertFalse(destination.exists())

    def test_hardlinked_local_clone_refuses_cleanup_without_touching_source(self) -> None:
        destination = self.root / "unsafe"
        git(self.source, "clone", "--local", str(self.source), str(destination))
        self.marker(destination)
        source_object = self.loose_source_object()
        mode = stat.S_IMODE(source_object.stat().st_mode)
        content = source_object.read_bytes()
        command = subprocess.run(
            [sys.executable, str(SCRIPT), "cleanup", str(self.root), "unsafe"], text=True, capture_output=True, check=False
        )
        self.assertEqual(command.returncode, 2, command.stderr)
        self.assertRegex(command.stderr, "multiple hardlinks|inode overlaps source")
        self.assertTrue(destination.exists())
        self.assertEqual(source_object.read_bytes(), content)
        self.assertEqual(stat.S_IMODE(source_object.stat().st_mode), mode)

    def test_verify_rejects_git_indirection_alternates_and_symlink_escape(self) -> None:
        destination = sandbox.create(str(self.source), str(self.root), "pilot")
        git_dir = destination / ".git"
        moved = destination / "metadata"
        git_dir.rename(moved)
        git_dir.write_text("gitdir: metadata\n", encoding="utf-8")
        with self.assertRaisesRegex(sandbox.SandboxError, "indirection"):
            sandbox._verify(self.root.resolve(), "pilot")
        git_dir.unlink()
        moved.rename(git_dir)
        alternates = git_dir / "objects" / "info" / "alternates"
        alternates.parent.mkdir(exist_ok=True)
        alternates.write_text("/outside/objects\n", encoding="utf-8")
        with self.assertRaisesRegex(sandbox.SandboxError, "alternates"):
            sandbox._verify(self.root.resolve(), "pilot")
        alternates.unlink()
        external = Path(self.temporary.name) / "outside"
        external.mkdir()
        (destination / "escape").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(sandbox.SandboxError, "symlink escapes"):
            sandbox._verify(self.root.resolve(), "pilot")
        self.assertTrue(external.exists())

    def test_workspace_hardlink_refuses_cleanup_without_touching_source(self) -> None:
        destination = sandbox.create(str(self.source), str(self.root), "pilot")
        shared = destination / "shared.txt"
        os.link(self.source / "tracked.txt", shared)
        mode = stat.S_IMODE((self.source / "tracked.txt").stat().st_mode)
        with self.assertRaisesRegex(sandbox.SandboxError, "multiple hardlinks"):
            sandbox._verify(self.root.resolve(), "pilot")
        self.assertTrue(destination.exists())
        self.assertEqual((self.source / "tracked.txt").read_text(), "original\n")
        self.assertEqual(stat.S_IMODE((self.source / "tracked.txt").stat().st_mode), mode)

    def test_symlink_to_sibling_sandbox_refuses_cleanup(self) -> None:
        destination = sandbox.create(str(self.source), str(self.root), "pilot")
        sibling = self.root / "sibling"
        sibling.mkdir()
        (destination / "sibling-link").symlink_to(sibling, target_is_directory=True)
        with self.assertRaisesRegex(sandbox.SandboxError, "symlink escapes disposable copy"):
            sandbox._verify(self.root.resolve(), "pilot")
        self.assertTrue(sibling.exists())
