from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
import execute_requirement as execution


REQUIREMENT = "acme/backlog#7"


@contextmanager
def fixture_locked_json(path: Path) -> Iterator[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    yield data
    path.write_text(json.dumps(data), encoding="utf-8")


class RequirementExecutionTests(unittest.TestCase):
    def test_handoffs_follow_declared_dependencies_not_filename_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw: dict[str, str] = {}
            for change, dependencies in (("last", ["first"]), ("first", [])):
                path = base / f"{change}.json"
                path.write_text(json.dumps({
                    "add_id": "requirement-7", "intents": [{"id": change, "dependencies": dependencies}],
                }), encoding="utf-8")
                raw[change] = str(path)
            ordered = execution._ordered_handoffs({"current_stage": "complete", "handoffs": raw}, REQUIREMENT)
            self.assertEqual([change for change, _ in ordered], ["first", "last"])

    def test_handoff_cycle_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            raw: dict[str, str] = {}
            for change, dependency in (("a", "b"), ("b", "a")):
                path = base / f"{change}.json"
                path.write_text(json.dumps({
                    "add_id": "requirement-7", "intents": [{"id": change, "dependencies": [dependency]}],
                }), encoding="utf-8")
                raw[change] = str(path)
            with self.assertRaisesRegex(execution.RequirementExecutionError, "cyclic"):
                execution._ordered_handoffs({"current_stage": "complete", "handoffs": raw}, REQUIREMENT)

    def test_unique_historical_child_is_reused_and_done_link_is_repaired(self) -> None:
        parent = {"body": "<!-- requirement-children:start -->\n- [x] acme/backlog#8\n<!-- requirement-children:end -->"}
        issue = {"body": "Parent Requirement: acme/backlog#7\n", "labels": [{"name": "type:internal-change"}]}
        with mock.patch.object(execution.managed_task, "discover_task", return_value=SimpleNamespace(change="first")), mock.patch.object(
            execution.requirement_intake, "fetch_issue", return_value=issue
        ), mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Done")), mock.patch.object(
            execution.requirement_intake, "link_child"
        ) as link:
            children = execution._linked_children_by_change(Path("/tmp/repo"), REQUIREMENT, parent)
        self.assertEqual(children, {"first": "acme/backlog#8"})
        link.assert_called_once()

    def test_duplicate_linked_managed_change_blocks_execution(self) -> None:
        parent = {"body": "<!-- requirement-children:start -->\n- [ ] acme/backlog#8\n- [ ] acme/backlog#9\n<!-- requirement-children:end -->"}
        issue = {"body": "Requirement: acme/backlog#7\n", "labels": [{"name": "type:internal-change"}]}
        with mock.patch.object(execution.managed_task, "discover_task", return_value=SimpleNamespace(change="same")), mock.patch.object(
            execution.requirement_intake, "fetch_issue", return_value=issue
        ):
            with self.assertRaisesRegex(execution.RequirementExecutionError, "both claim"):
                execution._linked_children_by_change(Path("/tmp/repo"), REQUIREMENT, parent)

    def test_advance_resumes_exact_active_child_without_materializing_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "first.json"
            handoff.write_text(json.dumps({"intents": [{"id": "first", "dependencies": []}]}), encoding="utf-8")
            patches = (
                mock.patch.object(execution, "current_worktree_root", return_value=root),
                mock.patch.object(execution, "_git", return_value="main"),
                mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"labels": [{"name": "type:requirement"}]}),
                mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}),
                mock.patch.object(execution, "_ordered_handoffs", return_value=[("first", handoff)]),
                mock.patch.object(execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8"}),
                mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")),
                mock.patch.object(execution, "_ready_receipt", return_value=None),
                mock.patch.object(execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root / "child"), "head", True)),
                mock.patch.object(execution.requirement_intake, "materialize_handoff"),
                mock.patch.object(execution.requirement_board, "reconcile_nonterminal"),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8] as start, patches[9] as materialize, patches[10] as board:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["status"], "implement-child")
            self.assertEqual(result["child"], "acme/backlog#8")
            self.assertIsNone(start.call_args.kwargs["base_child_receipt"])
            materialize.assert_not_called()
            board.assert_called_once_with(root.resolve(), requirement=REQUIREMENT)

    def test_advance_materializes_missing_child_then_starts_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "requirement-7/bundles/first"
            bundle.mkdir(parents=True)
            (bundle / "manifest.json").write_text("{}", encoding="utf-8")
            handoff = root / "first.json"
            handoff.write_text(json.dumps({"intents": [{"id": "first", "dependencies": []}]}), encoding="utf-8")
            with mock.patch.object(execution, "current_worktree_root", return_value=root), mock.patch.object(
                execution, "_git", return_value="main"
            ), mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"labels": [{"name": "type:requirement"}]}), mock.patch.object(
                execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}
            ), mock.patch.object(execution, "_ordered_handoffs", return_value=[("first", handoff)]), mock.patch.object(
                execution, "_linked_children_by_change", return_value={}
            ), mock.patch.object(execution.requirement_intake, "materialize_handoff", return_value={"child": "acme/backlog#8"}) as materialize, mock.patch.object(
                execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Ready")
            ), mock.patch.object(execution, "_ready_receipt", return_value=None), mock.patch.object(
                execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root / "child"), "head", False)
            ), mock.patch.object(
                execution.requirement_board, "reconcile_nonterminal"
            ):
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root, confirm_distinct=True)
            self.assertEqual(result["status"], "implement-child")
            self.assertTrue(materialize.call_args.kwargs["confirm_distinct"])

    def test_advance_publishes_only_after_two_exact_ready_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoffs = []
            for change in ("first", "second"):
                path = root / f"{change}.json"
                path.write_text(json.dumps({"intents": [{"id": change, "dependencies": []}]}), encoding="utf-8")
                handoffs.append((change, path))
            def git_result(_root: Path, *args: str) -> str:
                return "main" if args[:2] == ("branch", "--show-current") else "a" * 40
            with mock.patch.object(execution, "current_worktree_root", return_value=root), mock.patch.object(
                execution, "_git", side_effect=git_result
            ), mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"labels": [{"name": "type:requirement"}]}), mock.patch.object(
                execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}
            ), mock.patch.object(execution, "_ordered_handoffs", return_value=handoffs), mock.patch.object(
                execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8", "second": "acme/backlog#9"}
            ), mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")), mock.patch.object(
                execution, "_ready_receipt", side_effect=[(root / "first-receipt.json", object()), (root / "second-receipt.json", object())]
            ), mock.patch.object(execution.requirement_integration, "assemble_candidate", return_value={"digest": "exact"}) as assemble, mock.patch.object(
                execution.requirement_integration, "compose_candidate"
            ) as compose, mock.patch.object(execution.requirement_integration, "publish_candidate", return_value={"status": "merged-and-reconciled"}) as publish:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["status"], "merged-and-reconciled")
            self.assertEqual(len(assemble.call_args.kwargs["receipt_paths"]), 2)
            compose.assert_called_once()
            publish.assert_called_once()

    def test_ready_child_releases_only_its_exact_board_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "predecessor"
            worktree.mkdir()
            board = root / "board.json"
            board.write_text(json.dumps({"items": [
                {"id": "other", "branch": "agent/other", "worktree": str(worktree), "task": "Managed task acme/backlog#9"},
                {"id": "previous", "branch": "agent/predecessor", "worktree": str(worktree), "task": "Managed task acme/backlog#8"},
            ]}), encoding="utf-8")
            receipt = SimpleNamespace(head="a" * 40, source_branch="agent/predecessor", source_issue="acme/backlog#8")
            def git_result(_root: Path, *args: str) -> str:
                return receipt.head if args == ("rev-parse", "HEAD") else ""
            with mock.patch.object(execution.agent_board, "board_path", return_value=board), mock.patch.object(
                execution, "_git", side_effect=git_result
            ), mock.patch.object(
                execution, "locked_json", fixture_locked_json
            ):
                execution._release_ready_claim(root, worktree, receipt)
                execution._release_ready_claim(root, worktree, receipt)
            self.assertEqual([item["id"] for item in json.loads(board.read_text())["items"]], ["other"])

    def test_changed_or_dirty_ready_child_keeps_writer_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "predecessor"
            worktree.mkdir()
            board = root / "board.json"
            board.write_text(json.dumps({"items": [
                {"id": "previous", "branch": "agent/predecessor", "worktree": str(worktree), "task": "Managed task acme/backlog#8"},
            ]}), encoding="utf-8")
            receipt = SimpleNamespace(head="a" * 40, source_branch="agent/predecessor", source_issue="acme/backlog#8")
            for head, status in (("b" * 40, ""), (receipt.head, " M changed.py")):
                with mock.patch.object(execution.agent_board, "board_path", return_value=board), mock.patch.object(
                    execution, "_git", side_effect=lambda _root, *args: head if args == ("rev-parse", "HEAD") else status
                ), mock.patch.object(
                    execution, "locked_json", fixture_locked_json
                ):
                    with self.assertRaisesRegex(execution.RequirementExecutionError, "writer claim remains active"):
                        execution._release_ready_claim(root, worktree, receipt)
                self.assertEqual(len(json.loads(board.read_text())["items"]), 1)


if __name__ == "__main__":
    unittest.main()
