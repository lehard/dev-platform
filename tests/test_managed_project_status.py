from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import managed_project_status  # noqa: E402


def project_payload(*, current: str = "Ready", duplicate: bool = False) -> dict:
    options = [
        {"id": f"option-{index}", "name": name}
        for index, name in enumerate(managed_project_status.EXPECTED_STATUSES)
    ]
    item = {
        "id": "item-1",
        "content": {
            "__typename": "Issue",
            "number": 8,
            "repository": {"nameWithOwner": "lehard/development-backlog"},
        },
        "fieldValueByName": {"name": current, "optionId": "current-option"},
    }
    return {
        "data": {
            "user": {
                "projectV2": {
                    "id": "project-id",
                    "title": "Development Backlog",
                    "fields": {
                        "nodes": [
                            {
                                "__typename": "ProjectV2SingleSelectField",
                                "id": "status-field",
                                "name": "Status",
                                "options": options,
                            }
                        ]
                    },
                    "items": {
                        "nodes": [item, dict(item)] if duplicate else [item],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                }
            }
        }
    }


class ManagedProjectStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "openspec" / "changes" / "managed").mkdir(parents=True)
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").write_text(
            json.dumps({"source_issue": "lehard/development-backlog#8"}), encoding="utf-8"
        )
        (self.root / ".dev-platform.toml").write_text(
            'main_branch = "main"\n'
            '[development_backlog]\n'
            'repository = "lehard/development-backlog"\n'
            'project_label = "project:dev-platform"\n'
            'default_priority = "P2"\n'
            'project_owner = "lehard"\n'
            'project_number = 1\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_discovers_unambiguous_active_managed_source(self) -> None:
        source = managed_project_status.discover_source_issue(self.root)
        assert source is not None
        self.assertEqual(source.reference, "lehard/development-backlog#8")

    def test_task_level_state_survives_after_active_change_is_archived(self) -> None:
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").unlink()
        (self.root / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "lehard/development-backlog#8", "change": "managed"}), encoding="utf-8"
        )
        source = managed_project_status.discover_source_issue(self.root)
        assert source is not None
        self.assertEqual(source.reference, "lehard/development-backlog#8")

    def test_reconcile_is_idempotent_when_status_is_already_current(self) -> None:
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", return_value=project_payload(current="In review")) as graphql,
        ):
            observation = managed_project_status.reconcile(self.root, "In review")
        assert observation is not None
        self.assertFalse(observation.changed)
        self.assertEqual(graphql.call_count, 1)

    def test_reconcile_updates_exact_issue_item_with_resolved_option(self) -> None:
        calls: list[dict[str, object]] = []

        def graphql(root, env, query, variables):
            calls.append(variables)
            return project_payload() if len(calls) == 1 else {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}}

        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=graphql),
        ):
            observation = managed_project_status.reconcile(self.root, "In progress")
        assert observation is not None
        self.assertTrue(observation.changed)
        self.assertEqual(observation.current_status, "In progress")
        self.assertEqual(calls[1]["item"], "item-1")
        self.assertEqual(calls[1]["field"], "status-field")
        self.assertEqual(calls[1]["option"], "option-2")

    def test_ambiguous_issue_mapping_fails_without_mutation(self) -> None:
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", return_value=project_payload(duplicate=True)) as graphql,
        ):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "maps to 2 items"):
                managed_project_status.reconcile(self.root, "In progress")
        self.assertEqual(graphql.call_count, 1)

    def test_missing_locator_and_auth_are_actionable(self) -> None:
        config = managed_project_status.read_platform_config(self.root)
        del config["development_backlog"]["project_number"]
        source = managed_project_status.parse_source_issue("lehard/development-backlog#8")
        with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "project_number"):
            managed_project_status.project_locator(config, source)
        with patch.object(managed_project_status, "github_cli_env", return_value=None):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "gh auth refresh -s project"):
                managed_project_status.reconcile(self.root, "In progress")

    def test_quick_task_without_provenance_is_noop(self) -> None:
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").unlink()
        with patch.object(managed_project_status, "run_git") as git:
            git.return_value.returncode = 1
            git.return_value.stdout = ""
            self.assertIsNone(managed_project_status.reconcile(self.root, "In progress"))

    def test_block_for_scope_conflict_sets_blocked_status(self) -> None:
        calls: list[dict[str, object]] = []

        def graphql(root, env, query, variables):
            calls.append(variables)
            return project_payload(current="In progress") if len(calls) == 1 else {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}}

        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=graphql),
        ):
            observation = managed_project_status.block_for_scope_conflict(self.root, "hard overlap with sibling-id: shared.py")
        assert observation is not None
        self.assertTrue(observation.changed)
        self.assertEqual(observation.current_status, "Blocked")

    def test_block_for_scope_conflict_is_noop_for_a_quick_task_without_provenance(self) -> None:
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").unlink()
        with patch.object(managed_project_status, "run_git") as git:
            git.return_value.returncode = 1
            git.return_value.stdout = ""
            self.assertIsNone(managed_project_status.block_for_scope_conflict(self.root, "reason"))

    def test_resume_from_scope_conflict_is_noop_when_not_blocked(self) -> None:
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", return_value=project_payload(current="In progress")) as graphql,
        ):
            self.assertIsNone(managed_project_status.resume_from_scope_conflict(self.root))
        self.assertEqual(graphql.call_count, 1)  # Only observe() ran; no mutation was attempted.

    def test_resume_from_scope_conflict_returns_blocked_to_derived_status(self) -> None:
        calls: list[dict[str, object]] = []

        def graphql(root, env, query, variables):
            calls.append(variables)
            # observe() and reconcile() each re-query project state before the
            # mutation call, so the query payload must be returned twice.
            return project_payload(current="Blocked") if len(calls) <= 2 else {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "item-1"}}}}

        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=graphql),
            patch.object(managed_project_status, "derive_resume_status", return_value="In progress"),
        ):
            observation = managed_project_status.resume_from_scope_conflict(self.root)
        assert observation is not None
        self.assertTrue(observation.changed)
        self.assertEqual(observation.current_status, "In progress")

    def test_graphql_keeps_numeric_looking_option_id_as_string(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout='{"data": {}}', stderr="")
        with patch.object(managed_project_status.subprocess, "run", return_value=completed) as run:
            managed_project_status._graphql(
                self.root,
                {},
                "mutation($number: Int!, $option: String!) { __typename }",
                {"number": 1, "option": "98236657"},
            )
        command = run.call_args.args[0]
        self.assertIn("-F", command)
        self.assertEqual(command[command.index("number=1") - 1], "-F")
        self.assertEqual(command[command.index("option=98236657") - 1], "-f")


if __name__ == "__main__":
    unittest.main()
