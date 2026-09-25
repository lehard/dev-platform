from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from task_content_identity import content_identity, equivalent_proofs  # noqa: E402


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


class TaskContentIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "base")
        git(self.root, "branch", "origin/main")
        git(self.root, "switch", "-c", "agent/task")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit(self, message: str) -> None:
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", message)

    def test_archive_move_preserves_identity(self) -> None:
        active = self.root / "openspec" / "changes" / "content-aware"
        active.mkdir(parents=True)
        (active / "proposal.md").write_text("proposal\n", encoding="utf-8")
        self.commit("task")
        before = content_identity(self.root, "content-aware")
        archive = self.root / "openspec" / "changes" / "archive" / "2026-09-25-content-aware"
        archive.parent.mkdir(parents=True, exist_ok=True)
        active.rename(archive)
        self.commit("archive")
        self.assertEqual(before["digest"], content_identity(self.root, "content-aware")["digest"])

    def test_task_mutation_changes_identity(self) -> None:
        (self.root / "feature.txt").write_text("one\n", encoding="utf-8")
        self.commit("task")
        before = content_identity(self.root, "content-aware")
        (self.root / "feature.txt").write_text("two\n", encoding="utf-8")
        self.commit("mutation")
        self.assertNotEqual(before["digest"], content_identity(self.root, "content-aware")["digest"])

    def test_irrelevant_base_advance_can_reuse_identity(self) -> None:
        (self.root / "feature.txt").write_text("one\n", encoding="utf-8")
        self.commit("task")
        before = content_identity(self.root, "content-aware")
        git(self.root, "switch", "main")
        (self.root / "unrelated.txt").write_text("new\n", encoding="utf-8")
        self.commit("unrelated base")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/task")
        git(self.root, "merge", "main", "--no-edit")
        after = content_identity(self.root, "content-aware")
        self.assertEqual(before["digest"], after["digest"])
        self.assertTrue(equivalent_proofs(self.root, before, after))

    def test_overlapping_base_advance_rejects_reuse(self) -> None:
        (self.root / "feature.txt").write_text("one\n", encoding="utf-8")
        self.commit("task")
        before = content_identity(self.root, "content-aware")
        git(self.root, "switch", "main")
        (self.root / "feature.txt").write_text("one\n", encoding="utf-8")
        self.commit("overlapping base")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/task")
        git(self.root, "merge", "main", "--no-edit")
        after = content_identity(self.root, "content-aware")
        self.assertFalse(equivalent_proofs(self.root, before, after))


if __name__ == "__main__":
    unittest.main()
