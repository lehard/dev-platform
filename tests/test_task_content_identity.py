from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from _platform_config import write_platform_config  # noqa: E402
from _platform_common import TaskFreshnessError  # noqa: E402
from task_content_identity import (  # noqa: E402
    CHECKPOINT_SCOPE,
    IntegrationProofError,
    REVIEW_SCOPE,
    checkpoint_content_identity,
    content_identity,
    equivalent_proofs,
    main_only_integration,
    review_content_identity,
    review_exclusion,
    review_path_partition,
)


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
        (self.root / "dev-platform").mkdir()
        (self.root / "dev-platform/checks.toml").write_text("# no generated files\n", encoding="utf-8")
        write_platform_config(self.root)
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
        (self.root / "dev-platform").mkdir()
        (self.root / "dev-platform/checks.toml").write_text("# no generated files\n", encoding="utf-8")
        write_platform_config(self.root)
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

    def advance_main_and_merge(self) -> None:
        """Main moves past the predecessor's fork and the child merges it."""
        git(self.root, "switch", "main")
        (self.root / "main-only.txt").write_text("main\n", encoding="utf-8")
        (self.root / "base.txt").write_text("base from main\n", encoding="utf-8")
        self.commit("main advance")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/dependent")
        git(self.root, "merge", "main", "--no-edit")

    def reviewed_paths(self, proof: dict) -> list[str]:
        reviewed, lifecycle = review_path_partition(self.root, self.CHANGE, "origin/main", str(proof["base"]))
        # Main-delivered paths are neither reviewed nor reported as lifecycle evidence.
        self.assertEqual(lifecycle, [])
        return reviewed

    def merge_main_over_predecessor_edit(self, main_change: str) -> None:
        """Predecessor and main both touch base.txt; the child resolves in main's favour."""
        git(self.root, "switch", "-C", "agent/dependent", "origin/main")
        (self.root / "base.txt").write_text("predecessor\n", encoding="utf-8")
        self.commit("predecessor edits base")
        self.predecessor_head = git(self.root, "rev-parse", "HEAD")
        (self.root / "own.txt").write_text("own\n", encoding="utf-8")
        self.commit("own")
        git(self.root, "switch", "main")
        if main_change == "modify":
            (self.root / "base.txt").write_text("base from main\n", encoding="utf-8")
        else:
            (self.root / "base.txt").unlink()
        self.commit("main advance")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/dependent")
        merge = subprocess.run(["git", "merge", "main", "--no-edit"], cwd=self.root, text=True, capture_output=True)
        self.assertNotEqual(merge.returncode, 0, "the fixture must produce a merge conflict")
        if main_change == "modify":
            git(self.root, "checkout", "--theirs", "base.txt")
            git(self.root, "add", "base.txt")
        else:
            git(self.root, "rm", "-q", "base.txt")
        git(self.root, "commit", "--no-edit")
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})

    def test_legacy_dependent_child_excludes_main_delivered_paths(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        self.advance_main_and_merge()
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"own.txt"})
        self.assertEqual(proof["base"], self.predecessor_head)
        self.assertEqual(self.reviewed_paths(proof), sorted(proof["paths"]))

    def test_legacy_dependent_child_keeps_its_edit_of_a_main_changed_path(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        self.advance_main_and_merge()
        (self.root / "base.txt").write_text("base from child\n", encoding="utf-8")
        self.commit("child edits a main-changed file")
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"own.txt", "base.txt"})
        self.assertEqual(self.reviewed_paths(proof), sorted(proof["paths"]))

    def test_predecessor_path_resolved_in_mains_favour_stays_bound(self) -> None:
        self.merge_main_over_predecessor_edit("modify")
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"own.txt", "base.txt"})
        self.assertEqual(self.reviewed_paths(proof), sorted(proof["paths"]))

    def test_predecessor_path_deleted_by_main_merge_stays_bound(self) -> None:
        self.merge_main_over_predecessor_edit("delete")
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(proof["paths"], {"own.txt": git(self.root, "rev-parse", "HEAD:own.txt"), "base.txt": None})
        self.assertEqual(self.reviewed_paths(proof), sorted(proof["paths"]))

    def test_legacy_dependent_child_without_main_merge_keeps_predecessor_diff_digest(self) -> None:
        # A child that reverts predecessor content still owns that path.
        (self.root / "predecessor.txt").unlink()
        self.commit("child removes predecessor file")
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        plain = content_identity(
            self.root, self.CHANGE, self.predecessor_head,
            exclude=review_exclusion(self.root, self.CHANGE, self.predecessor_head), scope=REVIEW_SCOPE,
        )
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(plain["paths"]), {"own.txt", "predecessor.txt"})
        self.assertEqual(proof, plain)
        self.assertEqual(self.reviewed_paths(proof), sorted(plain["paths"]))

    def test_legacy_dependent_child_without_main_merge_base_fails(self) -> None:
        self.write_context({"dependencies": [self.dependency(self.predecessor_head)]})
        git(self.root, "branch", "-D", "origin/main")
        with self.assertRaisesRegex(ValueError, r"cannot compute merge-base\(HEAD, origin/main\)"):
            review_content_identity(self.root, self.CHANGE)
        with self.assertRaisesRegex(ValueError, r"cannot compute merge-base\(HEAD, origin/main\)"):
            review_path_partition(self.root, self.CHANGE, "origin/main", self.predecessor_head)

    def test_main_merge_without_context_keeps_origin_main_behavior(self) -> None:
        self.advance_main_and_merge()
        proof = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(set(proof["paths"]), {"predecessor.txt", "own.txt"})
        plain = content_identity(
            self.root, self.CHANGE, exclude=review_exclusion(self.root, self.CHANGE), scope=REVIEW_SCOPE,
        )
        self.assertEqual(proof, plain)


SETTINGS = '[settings]\nfull_commands = ["verify-gen"]\n'
DECLARATION = '[[generated_files]]\npath = "gen.txt"\nregenerate = ["regen", "{tree}"]\ncheck = ["verify-gen"]\n'


class GeneratedFileExclusionTests(unittest.TestCase):
    """Declared generated files leave review identity; the declaration is read at the main merge base."""

    CHANGE = "archived-change"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        (self.root / "dev-platform").mkdir()
        write_platform_config(self.root)
        self.write_checks(SETTINGS + DECLARATION)
        (self.root / "gen.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        (self.root / "feature.txt").write_text("a\nb\nc\nd\ne\nf\ng\n", encoding="utf-8")
        self.commit("base")
        git(self.root, "branch", "origin/main")
        git(self.root, "switch", "-c", "agent/task")
        archive = self.root / "openspec/changes/archive/2026-10-22-archived-change"
        archive.mkdir(parents=True)
        (archive / "proposal.md").write_text("proposal\n", encoding="utf-8")
        (self.root / "gen.txt").write_text("ONE\ntwo\nthree\n", encoding="utf-8")
        (self.root / "own.txt").write_text("own\n", encoding="utf-8")
        self.commit("task")

    def write_checks(self, text: str) -> None:
        (self.root / "dev-platform/checks.toml").write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", message)

    def advance_main(self, files: dict[str, str]) -> None:
        git(self.root, "switch", "main")
        for name, text in files.items():
            (self.root / name).write_text(text, encoding="utf-8")
        self.commit("main advances")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/task")

    def merge_main(self, regenerated: str) -> None:
        subprocess.run(["git", "merge", "--no-commit", "--no-ff", "main"], cwd=self.root, text=True, capture_output=True, check=False)
        (self.root / "gen.txt").write_text(regenerated, encoding="utf-8")
        self.commit("merge main with regenerated file")

    def paths(self) -> set[str]:
        return set(review_content_identity(self.root, self.CHANGE)["paths"])

    def test_declared_generated_file_is_not_task_content_but_every_other_path_is(self) -> None:
        self.assertEqual(self.paths(), {"own.txt", "openspec/changes/archived-change/proposal.md"})

    def test_regenerating_only_the_manifest_keeps_the_identity_and_the_proof_equivalent(self) -> None:
        before = review_content_identity(self.root, self.CHANGE)
        self.advance_main({"gen.txt": "one\ntwo\nTHREE\n"})
        self.merge_main("ONE\ntwo\nTHREE\n")
        after = review_content_identity(self.root, self.CHANGE)
        self.assertEqual(before["digest"], after["digest"])
        self.assertTrue(equivalent_proofs(self.root, before, after))

    def test_an_ordinary_task_path_changing_with_the_manifest_changes_the_identity(self) -> None:
        (self.root / "feature.txt").write_text("A\nb\nc\nd\ne\nf\ng\n", encoding="utf-8")
        self.commit("task edits feature")
        before = review_content_identity(self.root, self.CHANGE)
        self.advance_main({"gen.txt": "one\ntwo\nTHREE\n", "feature.txt": "a\nb\nc\nd\ne\nf\nG\n"})
        self.merge_main("ONE\ntwo\nTHREE\n")
        after = review_content_identity(self.root, self.CHANGE)
        self.assertNotEqual(before["digest"], after["digest"])
        self.assertFalse(equivalent_proofs(self.root, before, after))

    def test_checkpoint_proof_survives_a_merge_only_reconcile_that_changes_only_a_generated_file(self) -> None:
        # BR-940: the friction checkpoint proof drops declared generated files; the full proof would go stale.
        before = checkpoint_content_identity(self.root, self.CHANGE)
        full_before = content_identity(self.root, self.CHANGE)
        self.assertEqual(before["scope"], CHECKPOINT_SCOPE)
        self.assertNotIn("gen.txt", before["paths"])
        self.advance_main({"gen.txt": "one\ntwo\nTHREE\n"})
        self.merge_main("ONE\ntwo\nTHREE\n")
        self.assertTrue(equivalent_proofs(self.root, before, checkpoint_content_identity(self.root, self.CHANGE)))
        self.assertFalse(equivalent_proofs(self.root, full_before, content_identity(self.root, self.CHANGE)))

    def test_checkpoint_proof_goes_stale_when_a_task_owned_file_changes(self) -> None:
        before = checkpoint_content_identity(self.root, self.CHANGE)
        (self.root / "own.txt").write_text("own, edited after the checkpoint\n", encoding="utf-8")
        self.commit("task edits its own file")
        self.assertFalse(equivalent_proofs(self.root, before, checkpoint_content_identity(self.root, self.CHANGE)))

    def test_a_declaration_only_in_the_candidate_is_ignored(self) -> None:
        # Main never declared gen.txt; the candidate adds the declaration itself.
        git(self.root, "switch", "main")
        self.write_checks("# no generated files\n")
        self.commit("main declares nothing")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "-c", "other-task")
        self.write_checks(SETTINGS + DECLARATION)
        (self.root / "gen.txt").write_text("changed by the candidate\n", encoding="utf-8")
        self.commit("candidate declares its own generated file")
        self.assertIn("gen.txt", self.paths())

    def test_a_declaration_whose_check_is_not_a_full_command_fails_explicitly(self) -> None:
        git(self.root, "switch", "main")
        self.write_checks('[settings]\nfull_commands = ["other"]\n' + DECLARATION)
        self.commit("main declares an unchecked file")
        git(self.root, "branch", "-f", "origin/main", "main")
        git(self.root, "switch", "agent/task")
        git(self.root, "merge", "main")
        with self.assertRaisesRegex(TaskFreshnessError, "generated file gen.txt is not in .settings..full_commands"):
            review_content_identity(self.root, self.CHANGE)

    def test_an_unreadable_merge_base_fails_explicitly(self) -> None:
        git(self.root, "branch", "-D", "origin/main")
        with self.assertRaisesRegex(TaskFreshnessError, "no merge base of HEAD and origin/main"):
            review_content_identity(self.root, self.CHANGE)


class MainOnlyIntegrationTests(unittest.TestCase):
    """BR-969: a coordinator merge that only brought main keeps the gated receipt."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        self.write("checks.toml", "[a]\none\n\n[b]\ntwo\n")
        self.write("manifest.json", "v0\n")
        self.base = self.commit("base")
        git(self.root, "switch", "-q", "-c", "task")
        self.write("checks.toml", "[a]\none\ntask\n\n[b]\ntwo\n")
        self.write("manifest.json", "task\n")
        self.old_head = self.commit("task")
        git(self.root, "switch", "-q", "main")
        self.write("checks.toml", "[a]\none\n\n[b]\ntwo\nmain\n")
        self.write("manifest.json", "main\n")
        self.new_base = self.commit("main")
        git(self.root, "switch", "-q", "task")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, name: str, text: str) -> None:
        (self.root / name).write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", message)
        return git(self.root, "rev-parse", "HEAD")

    def merge_main(self, manifest: str = "merged\n") -> str:
        subprocess.run(["git", "merge", "-q", "--no-edit", self.new_base], cwd=self.root, capture_output=True)
        self.write("manifest.json", manifest)  # regenerated by its own declared command
        return self.commit("merge main")

    def test_main_merge_touching_a_task_path_is_proven(self) -> None:
        head = self.merge_main()
        self.assertIsNone(main_only_integration(self.root, self.old_head, self.new_base, head, {"manifest.json"}))

    def test_own_content_change_is_not_proven(self) -> None:
        self.merge_main()
        self.write("checks.toml", "[a]\none\ntask\nextra\n\n[b]\ntwo\nmain\n")
        head = self.commit("edit")
        reason = main_only_integration(self.root, self.old_head, self.new_base, head, {"manifest.json"})
        self.assertIn("differs from the merge", reason)
        self.assertIn("checks.toml", reason)

    def test_generated_exclusion_comes_only_from_the_given_declaration(self) -> None:
        head = self.merge_main()
        reason = main_only_integration(self.root, self.old_head, self.new_base, head, set())
        self.assertIn("manifest.json", reason)

    def test_untrusted_or_missing_heads_are_not_proven_and_git_failure_raises(self) -> None:
        head = self.merge_main()
        self.assertIn("old head", main_only_integration(self.root, None, self.new_base, head, set()))
        self.assertIn("new base", main_only_integration(self.root, self.old_head, "main", head, set()))
        with self.assertRaises(IntegrationProofError):
            main_only_integration(self.root, "f" * 40, self.new_base, head, {"manifest.json"})


if __name__ == "__main__":
    unittest.main()
