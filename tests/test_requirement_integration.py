from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "template" / "scripts" / "requirement_integration.py"
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

    def child(self, name: str, path: str) -> tuple[str, Path]:
        git(self.root, "switch", "-c", name, self.base)
        (self.root / path).write_text(name + "\n", encoding="utf-8")
        archive = self.root / "openspec" / "changes" / "archive" / f"2026-09-23-{name}"
        archive.mkdir(parents=True)
        verification = archive / "verification.md"
        verification.write_text("OpenSpec-Verify: PASS\nVerification-Method: test\n", encoding="utf-8")
        git(self.root, "add", path, str(verification.relative_to(self.root)))
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
