from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import requirement_child_context as context


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


class RequirementChildContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Test")
        change = self.root / "openspec/changes/child"
        change.mkdir(parents=True)
        (change / ".managed-task.json").write_text(
            json.dumps({"source_issue": "acme/backlog#8", "change": "child"}), encoding="utf-8"
        )
        (self.root / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "acme/backlog#8", "change": "child"}), encoding="utf-8"
        )
        (self.root / "sibling-transcript.txt").write_text("must never enter context", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "child base")
        self.head = git(self.root, "rev-parse", "HEAD")
        self.package = SimpleNamespace(source_issue="acme/backlog#8", change="child", parent_requirement="acme/backlog#7")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_derived_context_excludes_sibling_and_transcript(self) -> None:
        body = "Managed package\nRequirement: acme/backlog#7\nSibling body: secret"
        value = context.derive_context(self.root, self.package, issue_body=body)
        self.assertEqual(value["requirement"], "acme/backlog#7")
        self.assertEqual(value["repository_head"], self.head)
        encoded = json.dumps(value)
        self.assertNotIn("Sibling body", encoded)
        self.assertNotIn("must never enter context", encoded)
        self.assertEqual(value["dependencies"], [])

    def test_stale_dependency_requires_refresh(self) -> None:
        body = "Requirement: acme/backlog#7\n"
        predecessor = SimpleNamespace(
            requirement="acme/backlog#7", source_issue="acme/backlog#6", change="first",
            head=self.head, digest="a" * 64,
        )
        path = context.refresh_context(self.root, self.package, predecessor=predecessor)
        self.assertIsNotNone(path)
        context.validate_context(self.root, self.package, issue_body=body, predecessor=predecessor)
        changed = SimpleNamespace(**{**vars(predecessor), "digest": "b" * 64})
        with self.assertRaisesRegex(context.ManagedTaskError, "stale"):
            context.validate_context(self.root, self.package, issue_body=body, predecessor=changed)
        context.refresh_context(self.root, self.package, predecessor=changed)
        context.validate_context(self.root, self.package, issue_body=body, predecessor=changed)

    def test_ambiguous_parent_fails_closed(self) -> None:
        with self.assertRaisesRegex(context.ManagedTaskError, "ambiguous"):
            context.derive_context(
                self.root, self.package,
                issue_body="Requirement: acme/backlog#7\nRequirement: acme/backlog#9\n",
            )


if __name__ == "__main__":
    unittest.main()
