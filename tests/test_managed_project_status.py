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
            "repository": {"nameWithOwner": "example-org/development-backlog"},
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


class FakeProject:
    """Stateful fake of the Project GraphQL surface used by ensure_item."""

    def __init__(self, *, items=0, status: str | None = "Ready", fail_on: str | None = None, lag: bool = False) -> None:
        self.items = [{"id": f"item-{n}", "status": status} for n in range(items)]
        self.fail_on = fail_on
        self.lag = lag
        self.adds = 0
        self.updates: list[str] = []

    def __call__(self, root, env, query, variables):
        if self.fail_on and self.fail_on in query:
            raise managed_project_status.ManagedProjectStatusError("GitHub Project API request failed: unavailable")
        if "addProjectV2ItemById" in query:
            self.adds += 1
            if not self.items:  # GitHub returns the existing item on repeat adds
                self.items.append({"id": "item-new", "status": None})
            return {"data": {"addProjectV2ItemById": {"item": {"id": self.items[0]["id"]}}}}
        if "updateProjectV2ItemFieldValue" in query:
            self.updates.append(variables["option"])
            names = {f"option-{i}": n for i, n in enumerate(managed_project_status.EXPECTED_STATUSES)}
            self.items[0]["status"] = names[variables["option"]]
            return {"data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "x"}}}}
        if "issue(number" in query and "id }" in query and "projectItems" not in query:
            return {"data": {"repository": {"issue": {"id": "issue-node"}}}}
        payload = project_payload()
        nodes = []
        for item in self.items:
            node = {"id": item["id"], "content": {"__typename": "Issue", "number": 8,
                    "repository": {"nameWithOwner": "example-org/development-backlog"}},
                    "fieldValueByName": {"name": item["status"], "optionId": "o"} if item["status"] else None}
            nodes.append(node)
        payload["data"]["user"]["projectV2"]["items"]["nodes"] = [] if self.lag else nodes
        if "projectItems" in query:
            issue_nodes = [{**n, "isArchived": False, "project": {"id": "project-id"}} for n in nodes]
            return {"data": {"repository": {"issue": {"projectItems": {
                "nodes": issue_nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}
        return payload


class EnsureItemTests(unittest.TestCase):
    ISSUE = "example-org/development-backlog#8"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / ".dev-platform.toml").write_text(
            'main_branch = "main"\n[development_backlog]\n'
            'repository = "example-org/development-backlog"\nproject_label = "project:dev-platform"\n'
            'default_priority = "P2"\nproject_owner = "lehard"\nproject_number = 1\n', encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def ensure(self, fake: FakeProject):
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=fake),
        ):
            return managed_project_status.ensure_item(self.root, source_issue=self.ISSUE)

    def test_auto_add_already_happened_unset_status_gets_backlog(self) -> None:
        fake = FakeProject(items=1, status=None)
        receipt = self.ensure(fake)
        self.assertFalse(receipt.added)
        self.assertTrue(receipt.status_initialized)
        self.assertEqual(receipt.status, "Backlog")
        self.assertEqual(fake.adds, 0)

    def test_auto_add_absent_adds_one_item_with_backlog_and_reads_back(self) -> None:
        fake = FakeProject(items=0)
        receipt = self.ensure(fake)
        self.assertTrue(receipt.added)
        self.assertEqual((receipt.status, len(fake.items), fake.adds), ("Backlog", 1, 1))
        self.assertEqual(fake.updates, ["option-0"])

    def test_added_item_missing_from_project_list_is_found_through_issue(self) -> None:
        fake = FakeProject(items=0, lag=True)
        self.assertEqual(self.ensure(fake).status, "Backlog")

    def test_existing_item_and_status_are_never_changed(self) -> None:
        fake = FakeProject(items=1, status="In progress")
        receipt = self.ensure(fake)
        self.assertEqual((receipt.added, receipt.status_initialized, receipt.status), (False, False, "In progress"))
        self.assertEqual((fake.adds, fake.updates), (0, []))

    def test_repeated_reconciliation_is_idempotent_with_no_duplicate(self) -> None:
        fake = FakeProject(items=0)
        first = self.ensure(fake)
        second = self.ensure(fake)
        self.assertEqual(len(fake.items), 1)
        self.assertEqual(first.item_id, second.item_id)
        self.assertEqual((fake.adds, len(fake.updates)), (1, 1))
        self.assertFalse(second.added)

    def test_duplicate_items_fail_without_mutation(self) -> None:
        fake = FakeProject(items=2)
        with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "maps to 2 items"):
            self.ensure(fake)
        self.assertEqual((fake.adds, fake.updates), (0, []))

    def test_unavailable_project_api_fails_explicitly(self) -> None:
        for stage in ("addProjectV2ItemById", "user(login"):
            with self.subTest(stage=stage):
                with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "unavailable"):
                    self.ensure(FakeProject(items=0, fail_on=stage))

    def test_initialized_card_costs_one_project_scan(self) -> None:
        fake = FakeProject(items=1, status="Backlog")
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=fake) as graphql,
        ):
            managed_project_status.ensure_item(self.root, source_issue=self.ISSUE)
        self.assertEqual(graphql.call_count, 1)

    def test_readback_status_contradicting_initialization_fails(self) -> None:
        class Claimed(FakeProject):
            def __call__(self, root, env, query, variables):
                result = super().__call__(root, env, query, variables)
                if "updateProjectV2ItemFieldValue" in query:
                    self.items[0]["status"] = "In progress"  # another agent claimed it
                return result

        with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "expected 'Backlog'"):
            self.ensure(Claimed(items=1, status=None))

    def test_missing_authentication_fails_explicitly(self) -> None:
        with patch.object(managed_project_status, "github_cli_env", return_value=None):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "authentication"):
                managed_project_status.ensure_item(self.root, source_issue=self.ISSUE)


class ManagedProjectStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "openspec" / "changes" / "managed").mkdir(parents=True)
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").write_text(
            json.dumps({"source_issue": "example-org/development-backlog#8"}), encoding="utf-8"
        )
        (self.root / ".dev-platform.toml").write_text(
            'main_branch = "main"\n'
            '[development_backlog]\n'
            'repository = "example-org/development-backlog"\n'
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
        self.assertEqual(source.reference, "example-org/development-backlog#8")

    def test_opaque_active_source_requires_private_mapping(self) -> None:
        import managed_task

        path = self.root / "openspec/changes/managed/.managed-task.json"
        path.write_text(json.dumps({"private_lineage_handle": "pln_" + "a" * 32, "change": "managed"}), encoding="utf-8")
        with patch.object(managed_task, "source_issue_for_provenance", return_value="example-org/development-backlog#8"):
            source = managed_project_status.discover_source_issue(self.root)
            assert source is not None
            self.assertEqual(source.reference, "example-org/development-backlog#8")
        with patch.object(managed_task, "source_issue_for_provenance", side_effect=managed_task.ManagedTaskError("missing mapping")):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "cannot be authorized"):
                managed_project_status.discover_source_issue(self.root)

    def test_task_level_state_survives_after_active_change_is_archived(self) -> None:
        (self.root / "openspec" / "changes" / "managed" / ".managed-task.json").unlink()
        (self.root / ".managed-task-state.json").write_text(
            json.dumps({"source_issue": "example-org/development-backlog#8", "change": "managed"}), encoding="utf-8"
        )
        source = managed_project_status.discover_source_issue(self.root)
        assert source is not None
        self.assertEqual(source.reference, "example-org/development-backlog#8")

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

    def test_issue_side_lookup_recovers_item_missing_from_project_list(self) -> None:
        project = project_payload()
        project["data"]["user"]["projectV2"]["items"]["nodes"] = []
        issue_item = {
            "id": "item-1",
            "isArchived": False,
            "project": {"id": "project-id"},
            "content": {
                "__typename": "Issue",
                "number": 8,
                "repository": {"nameWithOwner": "example-org/development-backlog"},
            },
            "fieldValueByName": {"name": "Ready", "optionId": "current-option"},
        }
        issue = {"data": {"repository": {"issue": {"projectItems": {
            "nodes": [issue_item], "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}}}
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=[project, issue]) as graphql,
        ):
            observation = managed_project_status.observe(self.root)
        assert observation is not None
        self.assertEqual(observation.current_status, "Ready")
        self.assertEqual(graphql.call_count, 2)

    def test_issue_side_lookup_rejects_other_project(self) -> None:
        project = project_payload()
        project["data"]["user"]["projectV2"]["items"]["nodes"] = []
        issue = {"data": {"repository": {"issue": {"projectItems": {
            "nodes": [{
                "id": "item-1", "isArchived": False, "project": {"id": "other-project"},
                "content": {"__typename": "Issue", "number": 8,
                            "repository": {"nameWithOwner": "example-org/development-backlog"}},
                "fieldValueByName": {"name": "Ready"},
            }], "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}}}
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=[project, issue]),
        ):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "maps to 0 items"):
                managed_project_status.observe(self.root)

    def test_issue_side_lookup_rejects_ambiguous_project_items(self) -> None:
        project = project_payload()
        project["data"]["user"]["projectV2"]["items"]["nodes"] = []
        item = {
            "id": "item-1", "isArchived": False, "project": {"id": "project-id"},
            "content": {"__typename": "Issue", "number": 8,
                        "repository": {"nameWithOwner": "example-org/development-backlog"}},
            "fieldValueByName": {"name": "Ready"},
        }
        issue = {"data": {"repository": {"issue": {"projectItems": {
            "nodes": [item, {**item, "id": "item-2"}],
            "pageInfo": {"hasNextPage": False, "endCursor": None},
        }}}}}
        with (
            patch.object(managed_project_status, "github_cli_env", return_value={}),
            patch.object(managed_project_status, "_graphql", side_effect=[project, issue]),
        ):
            with self.assertRaisesRegex(managed_project_status.ManagedProjectStatusError, "maps to 2 items"):
                managed_project_status.observe(self.root)

    def test_missing_locator_and_auth_are_actionable(self) -> None:
        config = managed_project_status.read_platform_config(self.root)
        del config["development_backlog"]["project_number"]
        source = managed_project_status.parse_source_issue("example-org/development-backlog#8")
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
