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
from _platform_modules import load_platform_module

execution = load_platform_module("execute_requirement", ROOT / "template/scripts/execute_requirement.py")


def _write_handoffs(root: Path, intents: dict[str, list[str]]) -> dict[str, str]:
    """Recorded handoffs with real content digests plus the approved intent set."""
    requirement_dir = root / "requirement-7"
    (requirement_dir / "handoff").mkdir(parents=True, exist_ok=True)
    intents_document = {"intents": [
        {"id": change, "ready": True, "dependencies": dependencies} for change, dependencies in intents.items()
    ]}
    (requirement_dir / "intents.json").write_text(json.dumps(intents_document), encoding="utf-8")
    intents_digest = execution.add_intents._content_digest(intents_document)
    digests = {}
    for change, dependencies in intents.items():
        envelope = {"add_id": "requirement-7", "intents": [{"id": change, "dependencies": dependencies}],
                    "source_bindings": {"intents_digest": intents_digest}}
        envelope["digest"] = execution.add_intents._content_digest(envelope)
        (requirement_dir / "handoff" / f"{change}.json").write_text(json.dumps(envelope), encoding="utf-8")
        digests[change] = envelope["digest"]
    return digests


REQUIREMENT = "acme/backlog#7"
PARENT_BODY = "## Outcome\n\nShip it\n\n## Target repository\n\n`acme/project`\n"


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

    def test_stale_pre_authoring_uses_materialized_handoff_for_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = _write_handoffs(root, {"first": []})["first"]
            parent = {"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}
            child = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digest} -->"}
            terminal = load_platform_module("requirement_terminal", ROOT / "template/scripts/requirement_terminal.py")
            for materialized in (True, False):
                with self.subTest(materialized=materialized), mock.patch.object(
                    execution, "current_worktree_root", return_value=root
                ), mock.patch.object(execution, "_git", return_value="main"), mock.patch.object(
                    execution.requirement_target_lifecycle, "require_local_target_support"
                ), mock.patch.object(
                    execution.requirement_intake, "fetch_issue", side_effect=[parent, child if materialized else {"body": ""}]
                ), mock.patch.object(
                    execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "snapshot", "blocker": "stale sources"}
                ), mock.patch.object(execution.requirement_board, "claim_started"), mock.patch.object(
                    execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8"}
                ), mock.patch.object(
                    execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Done")
                ), mock.patch.object(execution, "_done_child_is_delivered"), mock.patch.object(
                    terminal, "reconcile_parent", return_value={"status": "done"}
                ) as reconcile, mock.patch.object(execution.requirement_intake, "materialize_handoff") as create:
                    if materialized:
                        self.assertEqual(execution.advance(root, requirement=REQUIREMENT, base_dir=root), {"status": "done"})
                        reconcile.assert_called_once_with(root.resolve(), requirement=REQUIREMENT)
                    else:
                        with self.assertRaisesRegex(execution.RequirementExecutionError, "not fresh and complete"):
                            execution.advance(root, requirement=REQUIREMENT, base_dir=root)
                        reconcile.assert_not_called()
                    create.assert_not_called()

    def test_materialized_handoffs_preserve_dependency_order_and_require_every_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            children = {"last": "acme/backlog#9", "first": "acme/backlog#8"}
            digests = _write_handoffs(root, {"last": ["first"], "first": []})
            bodies = [{"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests[change]} -->"} for change in ("last", "first")]
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=bodies):
                report = execution._materialized_handoff_report(root, REQUIREMENT, root, children)
            self.assertEqual([change for change, _ in execution._ordered_handoffs(report, REQUIREMENT)], ["first", "last"])
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[bodies[0], {"body": ""}]):
                self.assertIsNone(execution._materialized_handoff_report(root, REQUIREMENT, root, children))

    def test_recovered_multi_child_requirement_reconciles_when_all_children_are_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = _write_handoffs(root, {"last": ["first"], "first": []})
            children = {"last": "acme/backlog#9", "first": "acme/backlog#8"}
            parent = {"body": PARENT_BODY, "labels": [{"name": "type:requirement"}], "state": "OPEN"}
            bodies = [{"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests[change]} -->"} for change in ("last", "first")]
            terminal = load_platform_module("requirement_terminal", ROOT / "template/scripts/requirement_terminal.py")
            with mock.patch.object(execution, "current_worktree_root", return_value=root), \
                 mock.patch.object(execution, "_git", return_value="main"), \
                 mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), \
                 mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[parent, *bodies]), \
                 mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "snapshot", "blocker": "stale"}), \
                 mock.patch.object(execution.requirement_board, "claim_started"), \
                 mock.patch.object(execution, "_linked_children_by_change", return_value=children), \
                 mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Done")), \
                 mock.patch.object(execution, "_done_child_is_delivered"), \
                 mock.patch.object(terminal, "reconcile_parent", return_value={"status": "done"}) as reconcile:
                self.assertEqual(execution.advance(root, requirement=REQUIREMENT, base_dir=root), {"status": "done"})
            reconcile.assert_called_once_with(root.resolve(), requirement=REQUIREMENT)

    def test_recovery_maps_intent_named_handoffs_to_differently_named_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = _write_handoffs(root, {"intent-retry": []})
            body = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests['intent-retry']} -->"}
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[body]):
                report = execution._materialized_handoff_report(
                    root, REQUIREMENT, root, {"retry-implementation": "acme/backlog#8"})
            self.assertEqual(list(report["handoffs"]), ["retry-implementation"])

    def test_recovery_accepts_a_cohesive_group_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "requirement-7"
            (directory / "handoff").mkdir(parents=True)
            intents_document = {"intents": [{"id": "part-a", "ready": True, "dependencies": []},
                                            {"id": "part-b", "ready": True, "dependencies": ["part-a"]}]}
            (directory / "intents.json").write_text(json.dumps(intents_document), encoding="utf-8")
            envelope = {"add_id": "requirement-7", "intents": intents_document["intents"],
                        "source_bindings": {"intents_digest": execution.add_intents._content_digest(intents_document)}}
            envelope["digest"] = execution.add_intents._content_digest(envelope)
            for name in ("part-a", "part-b"):  # the grouped envelope recorded under each intent's name
                (directory / "handoff" / f"{name}.json").write_text(json.dumps(envelope), encoding="utf-8")
            body = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{envelope['digest']} -->"}
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[body]):
                report = execution._materialized_handoff_report(root, REQUIREMENT, root, {"grouped-change": "acme/backlog#8"})
            self.assertEqual(list(report["handoffs"]), ["grouped-change"])
            # An internal dependency of the group is not a cycle.
            self.assertEqual([change for change, _ in execution._ordered_handoffs(report, REQUIREMENT)], ["grouped-change"])

    def test_fresh_report_maps_intent_keys_to_differently_named_active_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = _write_handoffs(root, {"intent-retry": []})["intent-retry"]
            handoff = root / "requirement-7" / "handoff" / "intent-retry.json"
            parent = {"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}
            child = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digest} -->"}
            with mock.patch.object(execution, "current_worktree_root", return_value=root), \
                 mock.patch.object(execution, "_git", return_value="main"), \
                 mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), \
                 mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[parent, child]), \
                 mock.patch.object(execution.orchestrate_pre_authoring, "status",
                                   return_value={"current_stage": "complete", "handoffs": {"intent-retry": str(handoff)}}), \
                 mock.patch.object(execution.requirement_board, "claim_started"), \
                 mock.patch.object(execution, "_linked_children_by_change", return_value={"retry-implementation": "acme/backlog#8"}), \
                 mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")), \
                 mock.patch.object(execution, "_ready_receipt", return_value=None), \
                 mock.patch.object(execution.start_managed_task, "start_managed_task",
                                   return_value=(SimpleNamespace(task_root=root / "child"), "head", False)), \
                 mock.patch.object(execution.requirement_board, "reconcile_nonterminal"):
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual((result["status"], result["change"]), ("implement-child", "retry-implementation"))

    def test_partially_materialized_fresh_report_rekeys_the_linked_child_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = _write_handoffs(root, {"intent-first": [], "intent-second": ["intent-first"]})
            directory = root / "requirement-7" / "handoff"
            handoffs = {name: str(directory / f"{name}.json") for name in ("intent-first", "intent-second")}
            child = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests['intent-first']} -->"}
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[child]):
                rekeyed = execution._rekey_by_linked_child(root, REQUIREMENT, handoffs, {"change-first": "acme/backlog#8"})
            self.assertEqual(set(rekeyed), {"change-first", "intent-second"})
            ordered = execution._ordered_handoffs({"current_stage": "complete", "handoffs": rekeyed}, REQUIREMENT)
            self.assertEqual([change for change, _ in ordered], ["change-first", "intent-second"])

    def test_rekey_follows_markers_even_when_names_collide_and_dedupes_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = _write_handoffs(root, {"intent-a": [], "intent-b": []})
            directory = root / "requirement-7" / "handoff"
            handoffs = {name: str(directory / f"{name}.json") for name in ("intent-a", "intent-b")}
            # Children deliberately named after the *other* intent.
            bodies = [{"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests['intent-a']} -->"},
                      {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests['intent-b']} -->"}]
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=bodies):
                rekeyed = execution._rekey_by_linked_child(
                    root, REQUIREMENT, handoffs, {"intent-b": "acme/backlog#8", "intent-a": "acme/backlog#9"})
            self.assertEqual(rekeyed, {"intent-b": handoffs["intent-a"], "intent-a": handoffs["intent-b"]})
            # The same grouped envelope under two intent names maps once.
            (directory / "intent-b.json").write_text((directory / "intent-a.json").read_text(encoding="utf-8"), encoding="utf-8")
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[bodies[0]]):
                grouped = execution._rekey_by_linked_child(root, REQUIREMENT, handoffs, {"grouped": "acme/backlog#8"})
            self.assertEqual(list(grouped), ["grouped"])

    def test_refreshed_handoff_reuses_its_child_through_the_authored_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_handoffs(root, {"intent-retry": []})
            handoffs = {"intent-retry": str(root / "requirement-7" / "handoff" / "intent-retry.json")}
            stale_marker = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{'0' * 64} -->"}
            bundle = SimpleNamespace(change="retry-implementation", artifacts=("a",), contents=("c",))
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[stale_marker]), \
                 mock.patch.object(execution, "_bundle", return_value=root / "bundle"), \
                 mock.patch.object(execution.managed_task, "load_authoring_bundle", return_value=bundle), \
                 mock.patch.object(execution.managed_task, "discover_task",
                                   return_value=SimpleNamespace(artifacts=("a",), contents=("c",))):
                rekeyed = execution._rekey_by_linked_child(
                    root, REQUIREMENT, handoffs, {"retry-implementation": "acme/backlog#8"}, root)
            self.assertEqual(list(rekeyed), ["retry-implementation"])
            # A refreshed bundle that changes the child's contract stops explicitly.
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[stale_marker]), \
                 mock.patch.object(execution, "_bundle", return_value=root / "bundle"), \
                 mock.patch.object(execution.managed_task, "load_authoring_bundle", return_value=bundle), \
                 mock.patch.object(execution.managed_task, "discover_task",
                                   return_value=SimpleNamespace(artifacts=("a",), contents=("changed",))):
                with self.assertRaisesRegex(execution.RequirementExecutionError, "changes the contract"):
                    execution._rekey_by_linked_child(root, REQUIREMENT, handoffs, {"retry-implementation": "acme/backlog#8"}, root)

    def test_recovery_accepts_a_refreshed_handoff_reused_through_its_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_handoffs(root, {"intent-retry": []})
            stale_marker = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{'0' * 64} -->"}
            bundle = SimpleNamespace(change="retry-implementation", artifacts=("a",), contents=("c",))
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[stale_marker]), \
                 mock.patch.object(execution, "_bundle", return_value=root / "bundle"), \
                 mock.patch.object(execution.managed_task, "load_authoring_bundle", return_value=bundle), \
                 mock.patch.object(execution.managed_task, "discover_task",
                                   return_value=SimpleNamespace(artifacts=("a",), contents=("c",))):
                report = execution._materialized_handoff_report(root, REQUIREMENT, root, {"retry-implementation": "acme/backlog#8"})
            self.assertEqual(list(report["handoffs"]), ["retry-implementation"])

    def test_recovery_rejects_an_intent_set_edited_after_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digests = _write_handoffs(root, {"first": [], "second": []})
            (root / "requirement-7" / "handoff" / "second.json").unlink()
            intents_path = root / "requirement-7" / "intents.json"
            document = json.loads(intents_path.read_text(encoding="utf-8"))
            document["intents"][1]["ready"] = False  # hides the never-materialized second intent
            intents_path.write_text(json.dumps(document), encoding="utf-8")
            body = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests['first']} -->"}
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[body]):
                self.assertIsNone(execution._materialized_handoff_report(root, REQUIREMENT, root, {"first": "acme/backlog#8"}))

    def test_unreadable_pre_authoring_state_still_reaches_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            digest = _write_handoffs(root, {"first": []})["first"]
            parent = {"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}
            child = {"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digest} -->"}
            terminal = load_platform_module("requirement_terminal", ROOT / "template/scripts/requirement_terminal.py")
            with mock.patch.object(execution, "current_worktree_root", return_value=root), \
                 mock.patch.object(execution, "_git", return_value="main"), \
                 mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), \
                 mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=[parent, child]), \
                 mock.patch.object(execution.orchestrate_pre_authoring, "status",
                                   side_effect=execution.orchestrate_pre_authoring.OrchestratorError("state.json is unreadable")), \
                 mock.patch.object(execution.requirement_board, "claim_started"), \
                 mock.patch.object(execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8"}), \
                 mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Done")), \
                 mock.patch.object(execution, "_done_child_is_delivered"), \
                 mock.patch.object(terminal, "reconcile_parent", return_value={"status": "done"}):
                self.assertEqual(execution.advance(root, requirement=REQUIREMENT, base_dir=root), {"status": "done"})

    def test_materialized_recovery_rejects_edited_or_incomplete_handoffs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            children = {"last": "acme/backlog#9", "first": "acme/backlog#8"}
            digests = _write_handoffs(root, {"last": ["first"], "first": []})
            bodies = [{"body": f"<!-- requirement-handoff:v1:{REQUIREMENT}:{digests[change]} -->"} for change in ("last", "first")]
            path = root / "requirement-7" / "handoff" / "last.json"
            original = path.read_text(encoding="utf-8")
            # A dependency removed after materialization keeps the old digest.
            edited = json.loads(original)
            edited["intents"][0]["dependencies"] = []
            path.write_text(json.dumps(edited), encoding="utf-8")
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=bodies):
                self.assertIsNone(execution._materialized_handoff_report(root, REQUIREMENT, root, children))
            path.write_text(original, encoding="utf-8")
            # A lost handoff file must not shrink the mandatory set.
            path.unlink()
            with mock.patch.object(execution.requirement_intake, "fetch_issue", side_effect=bodies[1:]):
                self.assertIsNone(execution._materialized_handoff_report(root, REQUIREMENT, root, {"first": "acme/backlog#8"}))

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
                mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"),
                mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}),
                mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}),
                mock.patch.object(execution, "_ordered_handoffs", return_value=[("first", handoff)]),
                mock.patch.object(execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8"}),
                mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")),
                mock.patch.object(execution, "_ready_receipt", return_value=None),
                mock.patch.object(execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root / "child"), "head", True)),
                mock.patch.object(execution.requirement_intake, "materialize_handoff"),
                mock.patch.object(execution.requirement_board, "reconcile_nonterminal"),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9] as start, patches[10] as materialize, patches[11] as board:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["status"], "implement-child")
            self.assertEqual(result["child"], "acme/backlog#8")
            self.assertIsNone(start.call_args.kwargs["base_child_receipt"])
            materialize.assert_not_called()
            # Once at entry (claim before slow steps) and once after the child start.
            self.assertEqual(board.call_args_list, [mock.call(root.resolve(), requirement=REQUIREMENT)] * 2)

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
            ), mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), mock.patch.object(
                execution.requirement_intake, "fetch_issue", return_value={"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}), mock.patch.object(
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

    def test_multi_child_advance_dispatches_to_contribution_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoffs = [("first", root / "first.json"), ("second", root / "second.json")]
            with mock.patch.object(execution, "current_worktree_root", return_value=root), mock.patch.object(
                execution, "_git", return_value="main"
            ), mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), mock.patch.object(
                execution.requirement_intake, "fetch_issue", return_value={"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}
            ), mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}), mock.patch.object(
                execution, "_ordered_handoffs", return_value=handoffs
            ), mock.patch.object(execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8", "second": "acme/backlog#9"}), mock.patch.object(
                execution, "_advance_contributions", return_value={"status": "implement-children"}
            ) as contributions, mock.patch.object(execution, "_contribution_publication_supported", return_value=True), mock.patch.object(execution.requirement_board, "claim_started"), mock.patch.object(execution.requirement_integration, "assemble_candidate") as legacy:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["status"], "implement-children")
            contributions.assert_called_once()
            legacy.assert_not_called()

    def test_downstream_multi_child_uses_existing_supervisor_path(self):
        import _platform_common
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / "first.json"
            handoff.write_text(json.dumps({"intents": [{"id": "first", "dependencies": []}]}))
            with mock.patch.object(execution, "current_worktree_root", return_value=root), mock.patch.object(
                execution, "_git", return_value="main"
            ), mock.patch.object(_platform_common, "read_platform_config", return_value={"platform_version": "1.0"}), mock.patch.object(
                execution.requirement_target_lifecycle, "require_local_target_support"
            ), mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}), mock.patch.object(
                execution.orchestrate_pre_authoring, "status", return_value={}
            ), mock.patch.object(execution, "_ordered_handoffs", return_value=[("first", handoff), ("second", handoff)]), mock.patch.object(
                execution, "_linked_children_by_change", return_value={"first": "acme/backlog#8", "second": "acme/backlog#9"}
            ), mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="Ready")), mock.patch.object(
                execution, "_ready_receipt", return_value=None
            ), mock.patch.object(execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=root), "head", False)) as start, mock.patch.object(
                execution.requirement_board, "claim_started"
            ), mock.patch.object(execution.requirement_board, "reconcile_nonterminal"), mock.patch.object(execution, "_advance_contributions") as contributions:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["status"], "implement-child")
            contributions.assert_not_called()
            self.assertNotIn("contribution", start.call_args.kwargs)

    def test_single_child_active_coordinator_candidate_publishes_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "first"; worktree.mkdir()
            change = worktree / "openspec/changes/first"; change.mkdir(parents=True)
            (change / "tasks.md").write_text("- [x] Implement\n")
            with mock.patch.object(execution, "_contribution_publication_supported", return_value=True), mock.patch.object(
                execution, "machine_path", return_value=root
            ), mock.patch.object(execution, "_single_child_in_flight", return_value=False), mock.patch.object(execution.managed_task, "resolve_canonical_provenance", return_value=SimpleNamespace(lifecycle="active", path=change)), mock.patch.object(
                execution.subprocess, "run", return_value=SimpleNamespace(returncode=0)
            ) as finish:
                self.assertTrue(execution._publish_active_child(root, "acme/backlog#8", "first"))
            self.assertEqual(finish.call_args.kwargs["cwd"], worktree)
            self.assertEqual(finish.call_args.kwargs["stdin"], execution.subprocess.DEVNULL)
            self.assertTrue(change.is_dir())

    def test_single_child_resume_observes_handoff_and_newer_remote_head_without_republishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "first").mkdir()
            for state, remote_head in (("review-pending", "a" * 40), ("repairing", "b" * 40),
                                       ("finalize-pending", "b" * 40), (None, "b" * 40)):
                with self.subTest(state=state):
                    adapter = SimpleNamespace(
                        _repo=lambda *a: "acme/project", _gh=lambda *a: [{"number": 8}],
                        _pr=lambda *a: {"head": {"ref": "agent/first", "sha": remote_head},
                                       "base": {"ref": "main"}},
                        _comments=lambda *a: [], _derive=lambda *a: {}, _malformed=lambda *a: False,
                        _latest=lambda *a: {"state": state} if state else None,
                        _events=lambda *a: [], _admission=lambda *a: None)
                    observe = execution._single_child_in_flight
                    with mock.patch.object(execution, "_git", side_effect=["agent/first", "a" * 40]), \
                            mock.patch.object(execution, "_contribution_publication_supported", return_value=True), \
                            mock.patch.object(execution, "machine_path", return_value=root), \
                            mock.patch.object(execution, "_single_child_in_flight", side_effect=lambda w: observe(w, adapter=adapter)), \
                            mock.patch.object(execution.subprocess, "run") as finish, \
                            mock.patch.object(execution.managed_task, "resolve_canonical_provenance") as provenance:
                        self.assertTrue(execution._publish_active_child(root, "acme/backlog#8", "first"))
                        finish.assert_not_called()
                        provenance.assert_not_called()

    def test_dependent_child_gets_predecessor_receipt_when_change_names_differ_from_intents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = root / "intent-first.json", root / "intent-second.json"
            first.write_text(json.dumps({"intents": [{"id": "intent-first", "dependencies": []}]}), encoding="utf-8")
            second.write_text(json.dumps({"intents": [{"id": "intent-second", "dependencies": ["intent-first"]}]}), encoding="utf-8")
            handoffs = [("change-first", first), ("change-second", second)]
            receipt = root / "first-receipt.json"

            def git_result(_root: Path, *args: str) -> str:
                return "main" if args[:2] == ("branch", "--show-current") else "a" * 40

            with mock.patch.object(execution, "current_worktree_root", return_value=root), mock.patch.object(
                execution, "_git", side_effect=git_result
            ), mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), mock.patch.object(
                execution.requirement_intake, "fetch_issue", return_value={"body": PARENT_BODY, "labels": [{"name": "type:requirement"}]}
            ), mock.patch.object(
                execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}
            ), mock.patch.object(execution, "_ordered_handoffs", return_value=handoffs), mock.patch.object(
                execution, "_linked_children_by_change", return_value={"change-first": "acme/backlog#8", "change-second": "acme/backlog#9"}
            ), mock.patch.object(
                execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")
            ), mock.patch.object(
                execution, "_ready_receipt", side_effect=[(receipt, object()), None]
            ), mock.patch.object(execution, "_publish_early_draft", return_value=None), mock.patch.object(
                execution.start_managed_task, "start_managed_task",
                return_value=(SimpleNamespace(task_root=root / "child"), "head", False),
            ) as start, mock.patch.object(execution.requirement_board, "reconcile_nonterminal"):
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual(result["change"], "change-second")
            self.assertEqual(start.call_args.kwargs["base_child_receipt"], receipt)

    def test_single_mandatory_change_never_opens_a_shared_draft(self) -> None:
        self.assertIsNone(execution._publish_early_draft(
            Path("/unused"), REQUIREMENT, [("only", Path("only.json"))], {"only": "acme/backlog#8"}, [Path("r.json")], [],
        ))

    def test_existing_early_candidate_keeps_its_recorded_base(self) -> None:
        existing = {"base": "b" * 40}
        with mock.patch.object(execution, "_existing_candidate", return_value=existing), mock.patch.object(
            execution.requirement_integration, "assemble_candidate", return_value={"digest": "x"}
        ) as assemble, mock.patch.object(execution.requirement_integration, "_public_requirement", return_value=REQUIREMENT), mock.patch.object(
            execution, "_git", return_value="c" * 40
        ):
            execution._candidate_for(Path("/unused"), REQUIREMENT, [Path("r.json")], ["a", "b"])
        self.assertEqual(assemble.call_args.kwargs["base"], "b" * 40)

    def test_ready_receipt_supersedes_own_stale_receipt_in_child_worktree_and_reports_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worktree = root / "worktrees" / "first"
            worktree.mkdir(parents=True)
            archive = worktree / "openspec/changes/archive/2026-09-30-first"
            payload = {"head": "b" * 40}
            superseded: list[dict[str, str]] = []
            with mock.patch.object(execution.requirement_integration, "_registered_worktrees", return_value={worktree.resolve(): "agent/first"}), mock.patch.object(execution, "machine_path", return_value=root / "worktrees"), mock.patch.object(
                execution, "_git", return_value="agent/first"
            ), mock.patch.object(
                execution.managed_task, "resolve_canonical_provenance",
                return_value=SimpleNamespace(lifecycle="archived", path=archive),
            ), mock.patch.object(execution.requirement_integration, "create_receipt", return_value=payload), mock.patch.object(
                execution.requirement_integration, "superseded_receipt_head", return_value="a" * 40
            ) as prove, mock.patch.object(
                execution.requirement_integration, "write_receipt", return_value=SimpleNamespace(head="b" * 40)
            ) as write:
                path, _ = execution._ready_receipt(
                    root, root / "receipts", REQUIREMENT, "acme/backlog#8", "first",
                    release_claim=False, superseded=superseded,
                )
            self.assertEqual(prove.call_args.kwargs["root"], worktree)
            self.assertEqual(write.call_args.kwargs["root"], worktree)
            self.assertEqual(superseded, [{
                "source_issue": "acme/backlog#8", "change": "first", "receipt": str(path),
                "superseded_head": "a" * 40, "head": "b" * 40,
            }])

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
