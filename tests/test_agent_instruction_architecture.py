"""Regression evidence for bounded, cross-surface agent instructions."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "template" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import managed_task  # noqa: E402


FIXTURES = ROOT / "tests" / "fixtures"
CONCERN_ROW = "Maintaining agent-facing instructions, pointers and surface ownership"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def package_from_fixture(value: dict[str, object]) -> managed_task.Package:
    package = value["package"]
    assert isinstance(package, dict)
    contents = package["artifacts"]
    assert isinstance(contents, dict)
    return managed_task.Package(
        source_issue=str(package["source_issue"]),
        target_repository=str(package["target_repository"]),
        change=str(package["change"]),
        prepared_against=str(package["prepared_against"]),
        artifacts=tuple(contents),
        contents={str(path): str(content) for path, content in contents.items()},
        revision="fixture",
        routing_receipt=package["routing_receipt"],
        source_issue_evidence=package["source_issue_evidence"],
    )


def pointer_destination(text: str, concern: str) -> str:
    for row in text.splitlines():
        if not row.startswith("|") or concern not in row:
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) != 2 or cells[0] != concern:
            continue
        marker = "]("
        start = cells[1].find(marker)
        end = cells[1].find(")", start)
        if start >= 0 and end > start:
            return cells[1][start + len(marker):end]
    raise AssertionError(f"No instruction pointer for {concern!r}")


class InstructionArchitectureTests(unittest.TestCase):
    def test_reached_instruction_concern_discovers_its_canonical_document(self) -> None:
        for relative, base in (("AGENTS.md", ROOT), ("template/AGENTS.md.jinja", ROOT / "template")):
            text = (ROOT / relative).read_text(encoding="utf-8")
            destination = pointer_destination(text, CONCERN_ROW)
            with self.subTest(relative=relative):
                self.assertEqual(destination, "docs/engineering/agent-instructions.md")
                self.assertTrue((base / destination).is_file())

    def test_unrelated_task_intake_concern_does_not_route_to_instruction_architecture(self) -> None:
        for relative in ("AGENTS.md", "template/AGENTS.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertEqual(
                    pointer_destination(text, "Task intake and intent transitions"),
                    "docs/engineering/task-intake.md",
                )
                self.assertNotEqual(
                    pointer_destination(text, "Task intake and intent transitions"),
                    pointer_destination(text, CONCERN_ROW),
                )

    def test_tool_specific_adapters_remain_pointers_not_shared_policy_copies(self) -> None:
        for relative in ("CLAUDE.md", "template/CLAUDE.md.jinja"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("AGENTS.md", text)
                self.assertIn("do not create parallel shared policy", text)
                self.assertNotIn("Fix/add to Backlog", text)
                self.assertNotIn("managed_task.py", text)

    def test_task_intake_and_chatgpt_adapter_share_one_authoring_contract(self) -> None:
        paths = (
            "docs/engineering/task-intake.md",
            "template/docs/engineering/task-intake.md",
            "docs/engineering/chatgpt-project-protocol.md",
            "template/docs/engineering/chatgpt-project-protocol.md",
        )
        for relative in paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("managed-openspec:v1", text)
                self.assertIn("Backlog", text)
                self.assertIn("start_managed_task.py", text)
        for relative in ("docs/engineering/chatgpt-project-protocol.md", "template/docs/engineering/chatgpt-project-protocol.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn("Connected-GitHub authoring", text)
                self.assertIn("no local shell is required", text)
                self.assertIn("ChatGPT-specific manifest", text)

    def test_chatgpt_fixture_is_backlog_only_and_consumable_by_normal_package_discovery(self) -> None:
        value = fixture("chatgpt_project_fixation.json")
        package = package_from_fixture(value)
        serialized = managed_task.serialize_package(package)
        parsed = managed_task.parse_package([serialized], package.source_issue)
        self.assertFalse(value["local_shell_used"])
        self.assertTrue(value["authoring_stops"])
        self.assertEqual(value["project_status"], "Backlog")
        self.assertEqual(parsed.change, package.change)
        self.assertEqual(parsed.target_repository, package.target_repository)
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(managed_task, "issue_bodies", return_value=[serialized]),
                patch.object(managed_task, "origin_repository", return_value=package.target_repository),
            ):
                discovered = managed_task.discover_task(Path(tmp), package.source_issue)
        self.assertEqual(discovered.revision, parsed.revision)

    def test_repo_local_fixture_uses_deterministic_authoring_and_matches_chatgpt_representation(self) -> None:
        chatgpt = fixture("chatgpt_project_fixation.json")
        local = fixture("repo_local_fixation.json")
        self.assertEqual(local["authoring_command"], "python3 scripts/managed_task.py create --bundle <directory>")
        for key in ("intent", "authoring_stops", "project_status", "issue"):
            self.assertEqual(local[key], chatgpt[key])

        expected = package_from_fixture(local)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            (bundle / "specs" / "authoring").mkdir(parents=True)
            (bundle / "manifest.json").write_text(
                json.dumps({"title": "Fixture managed authoring", "change": expected.change, "artifacts": list(expected.artifacts)}),
                encoding="utf-8",
            )
            (bundle / "issue.md").write_text("Fixture authoring evidence.\n", encoding="utf-8")
            for relative, content in expected.contents.items():
                (bundle / relative).write_text(content, encoding="utf-8")
            issue = {"updated_at": "2026-09-01T00:00:00Z", "title": "[R2] Fixture managed authoring", "body": "Fixture authoring evidence."}
            with (
                patch.object(managed_task, "authoring_config", return_value=managed_task.AuthoringConfig("lehard/development-backlog", "project:dev-platform", "P2")),
                patch.object(managed_task, "origin_repository", return_value=expected.target_repository),
                patch.object(managed_task, "target_main", return_value=expected.prepared_against),
                patch.object(managed_task, "validate_backlog_labels"),
                patch.object(managed_task, "validate_authoring_bundle"),
                patch.object(managed_task, "open_backlog_issues", return_value=[]),
                patch.object(managed_task, "create_issue", return_value=80),
                patch.object(managed_task, "fetch_issue", return_value=issue),
                patch.object(managed_task, "publish_package", return_value=False),
            ):
                created, resumed, already_published = managed_task.create_task(root, str(bundle), None, False)
        self.assertFalse(resumed)
        self.assertFalse(already_published)
        self.assertEqual(created.source_issue, expected.source_issue)
        self.assertEqual(created.target_repository, expected.target_repository)
        self.assertEqual(created.change, expected.change)
        self.assertEqual(created.artifacts, expected.artifacts)
        self.assertEqual(created.contents, expected.contents)
        self.assertEqual(created.routing_receipt, expected.routing_receipt)

    def test_ordinary_lifecycle_has_no_external_instruction_or_chatgpt_service_dependency(self) -> None:
        architecture = (ROOT / "docs/engineering/agent-instructions.md").read_text(encoding="utf-8")
        self.assertIn("neither a runtime dependency nor a", architecture)
        lifecycle_sources = (
            "template/scripts/managed_task.py",
            "template/scripts/start_managed_task.py",
            "template/scripts/execute_managed_task.py",
            "template/scripts/finish_task.py",
        )
        for relative in lifecycle_sources:
            text = (ROOT / relative).read_text(encoding="utf-8").lower()
            with self.subTest(relative=relative):
                self.assertNotIn("writing-for-agents", text)
                self.assertNotIn("chatgpt", text)


if __name__ == "__main__":
    unittest.main()
