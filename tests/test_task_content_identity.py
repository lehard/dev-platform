from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
from task_content_identity import content_identity, equivalent_proofs, review_content_identity  # noqa: E402


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


class ReviewContentIdentityBaseTests(unittest.TestCase):
    """The review base is origin/main, a contribution head, or a legacy predecessor head."""

    CHANGE = "dependent-child"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        self.commit("base")
        git(self.root, "branch", "origin/main")
        git(self.root, "switch", "-c", "agent/dependent")
        (self.root / "predecessor.txt").write_text("predecessor\n", encoding="utf-8")
        self.commit("predecessor")
        self.predecessor_head = git(self.root, "rev-parse", "HEAD")
        (self.root / "own.txt").write_text("own\n", encoding="utf-8")
        self.commit("own")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit(self, message: str) -> None:
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", message)

    def write_context(self, payload: dict) -> None:
        path = self.root / ".claude" / "requirement-child-context" / f"{self.CHANGE}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def dependency(self, head: object) -> dict:
        return {"source_issue": "o/r#2", "change": "predecessor", "head": head, "receipt_digest": "d"}

    def test_no_context_uses_origin_main(self) -> None:
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"predecessor.txt", "own.txt"})
        self.assertEqual(proof["base"], git(self.root, "rev-parse", "origin/main"))

    def test_legacy_dependent_child_excludes_predecessor_content(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"own.txt"})
        self.assertEqual(proof["base"], self.predecessor_head)

    def test_empty_dependencies_use_origin_main(self) -> None:
        self.write_context({"dependencies": []})
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"predecessor.txt", "own.txt"})

    def test_contribution_wins_over_dependencies(self) -> None:
        contribution_head = git(self.root, "rev-parse", "HEAD")
        (self.root / "after.txt").write_text("after\n", encoding="utf-8")
        self.commit("after contribution")
        self.write_context({
            "contribution": {"head": contribution_head},
            "dependencies": [self.dependency(self.predecessor_head)],
        })
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"after.txt"})
        self.assertEqual(proof["base"], contribution_head)

    def test_multiple_dependencies_without_contribution_fail(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)] * 2})
        with self.assertRaisesRegex(ValueError, "2 dependencies without a contribution"):
            review_content_identity(self.root, self.CHANGE)

    def test_dependency_without_head_fails(self) -> None:
        for bad in (None, "", 7):
            with self.subTest(head=bad):
                self.write_context({"dependencies": [self.dependency(bad)]})
                with self.assertRaisesRegex(ValueError, "no non-empty string 'head'"):
                    review_content_identity(self.root, self.CHANGE)
        self.write_context({"dependencies": [{"source_issue": "o/r#2"}]})
        with self.assertRaisesRegex(ValueError, "no non-empty string 'head'"):
            review_content_identity(self.root, self.CHANGE)

    def test_explicit_base_ref_ignores_context(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        proof = review_content_identity(self.root, self.CHANGE, "origin/main")
        # origin/main is the default sentinel: context still applies; an explicit other ref does not.
        self.assertEqual(set(proof["paths"]), {"own.txt"})
        explicit = review_content_identity(self.root, self.CHANGE, "HEAD~2")
        self.assertEqual(set(explicit["paths"]), {"predecessor.txt", "own.txt"})


if __name__ == "__main__":
    unittest.main()
