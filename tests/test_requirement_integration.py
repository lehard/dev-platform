from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "template" / "scripts" / "requirement_integration.py"
sys.path.insert(0, str(HELPER.parent))
SPEC = importlib.util.spec_from_file_location("requirement_integration", HELPER)
assert SPEC and SPEC.loader
integration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = integration
SPEC.loader.exec_module(integration)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True).stdout.strip()


class RequirementIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Test")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def child(self, name: str, path: str, *, base_ref: str | None = None) -> tuple[str, Path]:
        git(self.root, "switch", "-c", name, base_ref or self.base)
        (self.root / path).write_text(name + "\n", encoding="utf-8")
        archive = self.root / "openspec" / "changes" / "archive" / f"2026-09-23-{name}"
        archive.mkdir(parents=True)
        verification = archive / "verification.md"
        verification.write_text("OpenSpec-Verify: PASS\nVerification-Method: test\n", encoding="utf-8")
        (archive / ".managed-task.json").write_text(
            json.dumps({"source_issue": f"acme/backlog#{8 if name == 'one' else 9}", "change": name}), encoding="utf-8"
        )
        (archive / "tasks.md").write_text("- [x] Verified child task\n", encoding="utf-8")
        (archive / "automated-checks.json").write_text(
            json.dumps({"outcome": "success", "executed_commands": [{"outcome": "success", "command": "test"}]}),
            encoding="utf-8",
        )
        git(self.root, "add", path, str(archive.relative_to(self.root)))
        git(self.root, "commit", "-m", name)
        head = git(self.root, "rev-parse", "HEAD")
        (self.root / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": f"acme/backlog#{8 if name == 'one' else 9}", "change": name}), encoding="utf-8"
        )
        payload = integration.create_receipt(
            self.root, requirement="acme/backlog#7", source_issue=f"acme/backlog#{8 if name == 'one' else 9}",
            change=name, archived_contract=archive, verification_receipt=verification,
        )
        receipt = self.root / "receipts" / f"{name}.json"
        integration.write_receipt(receipt, payload)
        (self.root / ".managed-task-state.json").unlink()
        git(self.root, "switch", "main")
        return head, receipt

    def test_receipt_is_nonterminal_and_content_bound(self) -> None:
        head, receipt_path = self.child("one", "one.txt")
        receipt = integration.read_receipt(receipt_path)
        self.assertEqual(receipt.head, head)
        self.assertFalse((self.root / ".managed-task-state.json").exists())
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["head"] = "f" * 40
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "digest"):
            integration.read_receipt(receipt_path)

    def test_assembly_binds_ordered_heads_and_rejects_overlap(self) -> None:
        one, one_receipt = self.child("one", "one.txt")
        two, two_receipt = self.child("two", "two.txt")
        candidate = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                   receipt_paths=[one_receipt, two_receipt])
        self.assertEqual([child["head"] for child in candidate["children"]], [one, two])
        _, overlap_receipt = self.child("overlap", "one.txt")
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "overlap"):
            integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                           receipt_paths=[one_receipt, overlap_receipt])

    def test_assembly_rejects_child_not_based_on_bound_base(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "exact resolvable"):
            integration.assemble_candidate(self.root, requirement="acme/backlog#7", base="f" * 40,
                                           receipt_paths=[one_receipt, two_receipt])

    def test_assembly_rejects_changed_child_branch(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        git(self.root, "switch", "one")
        (self.root / "later.txt").write_text("later\n", encoding="utf-8")
        git(self.root, "add", "later.txt")
        git(self.root, "commit", "-m", "later")
        git(self.root, "switch", "main")
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "branch changed"):
            integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                           receipt_paths=[one_receipt, two_receipt])

    def test_handoff_rejects_uncommitted_verification_edit(self) -> None:
        _, receipt = self.child("one", "one.txt")
        self.assertTrue(receipt.exists())
        git(self.root, "switch", "one")
        verification = self.root / "openspec/changes/archive/2026-09-23-one/verification.md"
        verification.write_text("OpenSpec-Verify: PASS\nVerification-Method: forged\n", encoding="utf-8")
        (self.root / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "acme/backlog#8", "change": "one"}), encoding="utf-8"
        )
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "differs from the exact committed"):
            integration.create_receipt(
                self.root, requirement="acme/backlog#7", source_issue="acme/backlog#8", change="one",
                archived_contract=verification.parent, verification_receipt=verification,
            )

    def test_compose_creates_one_isolated_candidate_and_resumes_exactly(self) -> None:
        one, one_receipt = self.child("one", "one.txt")
        two, two_receipt = self.child("two", "two.txt")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        kwargs = {"manifest": manifest, "receipt_paths": receipts, "worktree": candidate,
                  "branch": "agent/" + slug}
        first = integration.compose_candidate(self.root, **kwargs)
        self.assertFalse(first["resumed"])
        self.assertEqual(git(candidate, "rev-list", "--count", f"{self.base}..HEAD"), "3")
        self.assertEqual((candidate / "one.txt").read_text(encoding="utf-8"), "one\n")
        self.assertEqual((candidate / "two.txt").read_text(encoding="utf-8"), "two\n")
        self.assertEqual(integration.compose_candidate(self.root, **kwargs)["head"], first["head"])
        self.assertEqual(git(self.root, "rev-parse", "one"), one)
        self.assertEqual(git(self.root, "rev-parse", "two"), two)

    def test_compose_rejects_stale_main_before_worktree_creation(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        (self.root / "later.txt").write_text("later\n", encoding="utf-8")
        git(self.root, "add", "later.txt")
        git(self.root, "commit", "-m", "main advanced")
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "authoritative main changed"):
            integration.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts,
                                          worktree=candidate, branch="agent/" + slug)
        self.assertFalse(candidate.exists())

    def test_moved_main_uses_distinct_generation_and_preserves_prior_candidate(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        receipts = [one_receipt, two_receipt]
        original = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        old_slug = integration._candidate_slug("acme/backlog#7")
        old_candidate = self.root / ".claude/worktrees" / old_slug
        old = integration.compose_candidate(self.root, manifest=original, receipt_paths=receipts,
                                            worktree=old_candidate, branch="agent/" + old_slug)
        (self.root / "unrelated.txt").write_text("main advanced\n", encoding="utf-8")
        git(self.root, "add", "unrelated.txt")
        git(self.root, "commit", "-m", "unrelated main change")
        new_base = git(self.root, "rev-parse", "HEAD")
        recovered = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=new_base,
                                                   receipt_paths=receipts)
        self.assertEqual(recovered["generation"], new_base[:12])
        self.assertEqual([child["delta_base"] for child in recovered["children"]], [self.base, self.base])
        new_slug = integration._candidate_slug("acme/backlog#7", recovered["generation"])
        new_candidate = self.root / ".claude/worktrees" / new_slug
        result = integration.compose_candidate(self.root, manifest=recovered, receipt_paths=receipts,
                                               worktree=new_candidate, branch="agent/" + new_slug)
        self.assertTrue((new_candidate / "unrelated.txt").is_file())
        self.assertTrue((new_candidate / "one.txt").is_file())
        self.assertTrue((new_candidate / "two.txt").is_file())
        self.assertEqual(integration.compose_candidate(self.root, manifest=recovered, receipt_paths=receipts,
                                                       worktree=new_candidate, branch="agent/" + new_slug)["head"], result["head"])
        self.assertEqual(git(old_candidate, "rev-parse", "HEAD"), old["head"])

    def test_recovery_rejects_patch_conflict_without_touching_child(self) -> None:
        one, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        (self.root / "one.txt").write_text("conflicting main\n", encoding="utf-8")
        git(self.root, "add", "one.txt")
        git(self.root, "commit", "-m", "conflicting main")
        base = git(self.root, "rev-parse", "HEAD")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=base,
                                                  receipt_paths=receipts)
        slug = integration._candidate_slug("acme/backlog#7", manifest["generation"])
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "candidate application failed"):
            integration.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts,
                                          worktree=self.root / ".claude/worktrees" / slug, branch="agent/" + slug)
        self.assertEqual(git(self.root, "rev-parse", "one"), one)

    def test_ignored_local_contract_is_copied_and_mismatch_blocks(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        (self.root / ".git/info/exclude").write_text(".dev-platform.toml\n", encoding="utf-8")
        (self.root / ".dev-platform.toml").write_text('main_branch = "main"\n', encoding="utf-8")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        kwargs = {"manifest": manifest, "receipt_paths": receipts, "worktree": candidate, "branch": "agent/" + slug}
        integration.compose_candidate(self.root, **kwargs)
        self.assertEqual((candidate / ".dev-platform.toml").read_bytes(), (self.root / ".dev-platform.toml").read_bytes())
        (candidate / ".dev-platform.toml").write_text('main_branch = "other"\n', encoding="utf-8")
        with self.assertRaisesRegex(integration.RequirementIntegrationError, "local source contract differs"):
            integration.compose_candidate(self.root, **kwargs)

    def test_merged_candidate_recovery_skips_stale_inputs_and_checks(self) -> None:
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=[one_receipt, two_receipt])
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        integration.compose_candidate(self.root, manifest=manifest, receipt_paths=[one_receipt, two_receipt],
                                      worktree=candidate, branch="agent/" + slug)
        merged = {"status": "merged-and-reconciled", "pr": "https://example.invalid/pr/1"}
        with mock.patch.object(integration, "_reconcile_exact_merged", return_value=merged) as reconcile, \
                mock.patch.object(integration, "_run_full_checks") as checks, \
                mock.patch.object(integration, "compose_candidate") as compose:
            self.assertEqual(integration.publish_candidate(candidate, manifest=manifest, receipt_paths=[]), merged)
        reconcile.assert_called_once()
        checks.assert_not_called()
        compose.assert_not_called()

    def test_terminal_children_wait_for_exact_merged_pr_and_local_sync(self) -> None:
        import _platform_common
        import finish_task
        import integration_state
        import managed_project_status
        import publication_state

        manifest = {"requirement": "acme/backlog#7", "children": [
            {"source_issue": "acme/backlog#8"}, {"source_issue": "acme/backlog#9"},
        ]}
        base_patches = [
            mock.patch.object(_platform_common, "read_platform_config", return_value={"main_branch": "main"}),
            mock.patch.object(_platform_common, "github_cli_env", return_value={"GH_TOKEN": "test"}),
            mock.patch.object(integration_state, "serialized_integration", return_value=nullcontext()),
        ]
        with base_patches[0], base_patches[1], base_patches[2], \
                mock.patch.object(finish_task, "sync_after_remote_pr_merge") as sync, \
                mock.patch.object(managed_project_status, "reconcile") as statuses, \
                mock.patch.object(integration, "_verify_parent_links") as links, \
                mock.patch.object(publication_state, "find_exact_head_pr") as lookup:
            lookup.return_value = SimpleNamespace(available=True, exact_merged=None)
            self.assertIsNone(integration._reconcile_exact_merged(self.root, self.root, manifest, "branch", "f" * 40))
            sync.assert_not_called()
            statuses.assert_not_called()
            lookup.return_value = SimpleNamespace(available=True, exact_merged={"url": "https://example.invalid/pr/1"})
            result = integration._reconcile_exact_merged(self.root, self.root, manifest, "branch", "f" * 40)
            self.assertEqual(result["status"], "merged-and-reconciled")
            sync.assert_called_once()
            links.assert_called_once()
            self.assertEqual([call.kwargs["source_issue"] for call in statuses.call_args_list],
                             ["acme/backlog#8", "acme/backlog#9"])

    def test_bare_remote_main_is_authoritative_for_candidate(self) -> None:
        remote = self.root / "remote.git"
        git(self.root, "init", "--bare", "--initial-branch=main", str(remote))
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-u", "origin", "main")
        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        integration.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts,
                                      worktree=candidate, branch="agent/" + slug)
        self.assertEqual(git(self.root, "rev-parse", "origin/main"), self.base)
        self.assertEqual(git(self.root, "rev-parse", "main"), self.base)
        self.assertNotEqual(git(candidate, "rev-parse", "HEAD"), self.base)

    def test_bare_remote_two_child_cli_rehearsal(self) -> None:
        remote = self.root / "remote.git"
        git(self.root, "init", "--bare", "--initial-branch=main", str(remote))
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-u", "origin", "main")
        _, first = self.child("one", "one.txt")
        _, second = self.child("two", "two.txt")
        manifest_path = self.root / "candidate.json"
        assembled = subprocess.run(
            [sys.executable, str(HELPER), "assemble", "--requirement", "acme/backlog#7",
             "--base", self.base, "--receipt", str(first), "--receipt", str(second),
             "--out", str(manifest_path)], cwd=self.root, capture_output=True, text=True, check=True,
        )
        manifest = json.loads(assembled.stdout)
        self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8")), manifest)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        command = [sys.executable, str(HELPER), "compose", "--manifest", str(manifest_path),
                   "--worktree", str(candidate), "--branch", "agent/" + slug,
                   "--receipt", str(first), "--receipt", str(second)]
        composed = json.loads(subprocess.run(command, cwd=self.root, capture_output=True,
                                             text=True, check=True).stdout)
        resumed = json.loads(subprocess.run(command, cwd=self.root, capture_output=True,
                                            text=True, check=True).stdout)
        self.assertFalse(composed["resumed"])
        self.assertTrue(resumed["resumed"])
        self.assertEqual(composed["head"], resumed["head"])
        self.assertEqual(git(self.root, "rev-parse", "origin/main"), self.base)
        self.assertEqual(git(self.root, "rev-parse", "main"), self.base)
        self.assertEqual((candidate / "one.txt").read_text(encoding="utf-8"), "one\n")
        self.assertEqual((candidate / "two.txt").read_text(encoding="utf-8"), "two\n")

    def test_sequential_child_can_intentionally_edit_prior_child_path(self) -> None:
        one, one_receipt = self.child("one", "one.txt")
        two, two_receipt = self.child("two", "one.txt", base_ref="one")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        self.assertEqual(manifest["children"][1]["delta_base"], one)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        integration.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts,
                                      worktree=candidate, branch="agent/" + slug)
        self.assertEqual((candidate / "one.txt").read_text(encoding="utf-8"), "two\n")
        self.assertEqual(git(self.root, "rev-parse", "two"), two)

    def test_dependent_managed_start_fast_forwards_before_package_import(self) -> None:
        import start_managed_task

        head, receipt_path = self.child("one", "one.txt")
        receipt = integration.read_receipt(receipt_path)
        package = SimpleNamespace(change="two", source_issue="acme/backlog#9", revision="r1")
        started = start_managed_task.StartedTask(profile="multi-agent", branch="agent/two", task_root=self.root)
        events: list[str] = []

        def run_git(args, **kwargs):
            events.append("git " + args[0])
            return SimpleNamespace(stdout=head + "\n", returncode=0)

        def imported(*args, **kwargs):
            events.append("import")
            return package, self.base, False

        with mock.patch.object(start_managed_task, "start_task", return_value=started), \
                mock.patch.object(start_managed_task, "run_git", side_effect=run_git), \
                mock.patch.object(start_managed_task, "import_task", side_effect=imported), \
                mock.patch.object(start_managed_task, "admit_task", return_value={"decision": "RUN"}), \
                mock.patch.object(start_managed_task, "reconcile", return_value=SimpleNamespace(changed=True)):
            start_managed_task._start_new_managed_task(self.root, package, package.source_issue, "", None, receipt)
        self.assertLess(events.index("git merge"), events.index("import"))

    def test_publisher_invokes_protected_primitive_once_after_full_checks(self) -> None:
        import _platform_common

        _, one_receipt = self.child("one", "one.txt")
        _, two_receipt = self.child("two", "two.txt")
        receipts = [one_receipt, two_receipt]
        manifest = integration.assemble_candidate(self.root, requirement="acme/backlog#7", base=self.base,
                                                  receipt_paths=receipts)
        slug = integration._candidate_slug("acme/backlog#7")
        candidate = self.root / ".claude/worktrees" / slug
        composed = integration.compose_candidate(self.root, manifest=manifest, receipt_paths=receipts,
                                                 worktree=candidate, branch="agent/" + slug)
        events: list[str] = []

        def checked(_root):
            events.append("full-checks")

        def published(command, **kwargs):
            events.append("protected-pr")
            self.assertEqual(command[:3], ["python3", "scripts/project_publish.py", "--mode"])
            return SimpleNamespace(returncode=0)

        with mock.patch.object(_platform_common, "main_root", return_value=self.root), \
                mock.patch.object(_platform_common, "read_platform_config", return_value={"publish_mode": "pr", "pr_merge_mode": "manual"}), \
                mock.patch.object(integration, "_validate_candidate_checkout", return_value=("agent/" + slug, composed["head"])), \
                mock.patch.object(integration, "_reconcile_exact_merged", side_effect=[None, None]), \
                mock.patch.object(integration, "compose_candidate", return_value={**composed, "resumed": True}), \
                mock.patch.object(integration, "_verify_parent_links"), \
                mock.patch.object(integration, "_run_full_checks", side_effect=checked), \
                mock.patch.object(integration.subprocess, "run", side_effect=published):
            result = integration.publish_candidate(candidate, manifest=manifest, receipt_paths=receipts)
        self.assertEqual(result["status"], "in-review")
        self.assertEqual(events, ["full-checks", "protected-pr"])

    def test_independent_linked_child_requires_committed_exception_reason(self) -> None:
        import managed_task

        self.child("one", "one.txt")
        git(self.root, "switch", "one")
        archive = self.root / "openspec/changes/archive/2026-09-23-one"
        delivery = SimpleNamespace(source_issue="acme/backlog#8", path=archive)
        child_issue = {"body": "Requirement: acme/backlog#7\n", "labels": [{"name": "type:internal-change"}]}
        parent_issue = {"body": "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n<!-- requirement-children:end -->",
                        "labels": [{"name": "type:requirement"}]}
        with mock.patch.object(managed_task, "fetch_issue", side_effect=[child_issue, parent_issue]):
            with self.assertRaisesRegex(integration.RequirementIntegrationError, "requires one"):
                integration.require_independent_publication_exception(self.root, delivery)
        verification = archive / "verification.md"
        verification.write_text(verification.read_text(encoding="utf-8") +
                                "Requirement-Integration-Exception: Bootstrap the shared publication machinery safely\n",
                                encoding="utf-8")
        git(self.root, "add", str(verification.relative_to(self.root)))
        git(self.root, "commit", "-m", "record bootstrap exception")
        with mock.patch.object(managed_task, "fetch_issue", side_effect=[child_issue, parent_issue]):
            reason = integration.require_independent_publication_exception(self.root, delivery)
        self.assertIn("Bootstrap", reason)
