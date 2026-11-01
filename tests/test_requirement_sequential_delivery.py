"""BR-941: sequential Requirement children and the rebind of an unchanged approved chain."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

import add_intents  # noqa: E402
import orchestrate_pre_authoring as orch  # noqa: E402
import project_evidence  # noqa: E402
from _platform_modules import load_platform_module  # noqa: E402

execution = load_platform_module("execute_requirement", ROOT / "template/scripts/execute_requirement.py")
contour = load_platform_module("integration_contour", ROOT / "template/scripts/integration_contour.py")

REQUIREMENT_ID = "requirement-7"
REQUIREMENT = "acme/backlog#7"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True).stdout.strip()


def commit(root: Path, message: str, files: dict[str, str]) -> str:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", *files)
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


def worker_results(root: Path) -> dict[str, dict]:
    results = {}
    for concern, dependencies in project_evidence.inventory(root)["dependencies"].items():
        results[concern] = {"version": 1, "confidence": "high", "conflicts": [], "unknowns": [],
                            "facts": [{"statement": f"{concern} fact", "evidence_refs": [dependencies[0]]}] if dependencies else []}
    return results


def intents_for(order: list[str] | None, *, ready: bool = True, dependencies: dict[str, list[str]] | None = None) -> dict:
    document = {"intents": [{"id": identity, "ready": ready, "dependencies": (dependencies or {}).get(identity, [])}
                            for identity in ("first", "second")]}
    if order is not None:
        document["delivery"] = {"mode": "sequential", "order": order}
    return document


class DeliveryDeclarationTests(unittest.TestCase):
    def _errors(self, document: dict) -> list[str]:
        by_id = {item["id"]: item for item in document["intents"]}
        return add_intents._delivery_errors(document.get("delivery"), by_id)

    def test_absent_declaration_keeps_default_delivery(self) -> None:
        self.assertEqual(self._errors(intents_for(None)), [])
        self.assertIsNone(add_intents.delivery_order(intents_for(None)))

    def test_valid_order_is_returned(self) -> None:
        document = intents_for(["first", "second"], dependencies={"second": ["first"]})
        self.assertEqual(self._errors(document), [])
        self.assertEqual(add_intents.delivery_order(document), ["first", "second"])

    def test_invalid_declarations_name_the_problem(self) -> None:
        cases = {
            "every intent exactly once": intents_for(["first"]),
            "exactly once:": intents_for(["first", "first", "second"]),
            "must be ready": intents_for(["first", "second"], ready=False),
            "before its dependency": intents_for(["second", "first"], dependencies={"second": ["first"]}),
            '"mode": "sequential"': {**intents_for(None), "delivery": {"mode": "parallel", "order": ["first", "second"]}},
        }
        for expected, document in cases.items():
            with self.subTest(expected=expected):
                self.assertTrue(any(expected in error for error in self._errors(document)), self._errors(document))


class RebindTests(unittest.TestCase):
    """A real snapshot -> ADD -> intents -> handoff chain in a disposable repository."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "Test")
        commit(self.root, "seed", {
            "README.md": "# Example\n", "AGENTS.md": "# Rules\n", ".gitignore": ".claude/\n",
            "docs/context/domain.md": "# Domain\n",
            "openspec/specs/payments/spec.md": "# Payments\n", "openspec/specs/billing/spec.md": "# Billing\n",
        })
        requirement = self.root / "requirement.md"
        requirement.write_text("Ship two children one at a time.\n", encoding="utf-8")
        self.base_dir = self.root / ".claude" / "pre-authoring"
        orch.init(self.root, requirement_id=REQUIREMENT_ID, requirement_file=requirement,
                  target_repository="acme/project", base_dir=self.base_dir)
        orch.select_depth(self.root, requirement_id=REQUIREMENT_ID, depth=orch.DEPTH_MATERIAL_DESIGN,
                          reason="Two sequential children", base_dir=self.base_dir)
        self.directory = orch.requirement_dir(self.base_dir, REQUIREMENT_ID)
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results=worker_results(self.root))
        orch._write_json(orch.snapshot_path(self.directory), snapshot)
        add_file = orch.add_path(self.directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        source = orch.snapshot_path(self.directory).relative_to(self.root).as_posix()
        add_document["evidence"] = [{
            "source": source, "kind": add_intents.EVIDENCE_KIND_SNAPSHOT, "digest": projection["digest"],
            "snapshot_digest": snapshot["digest"], "snapshot_revision": snapshot["revision"], "projection": concern,
            "projection_digest": projection["digest"], "projection_status": projection["status"],
        } for concern, projection in sorted(snapshot["projections"].items())]
        add_document["elements"] = [{"id": "payments-rule", "category": "capability", "status": "new", "statement": "Payments."},
                                    {"id": "billing-rule", "category": "capability", "status": "new", "statement": "Billing."}]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        add_intents.approve_add(self.root, add_file, approved_by="owner")
        intents_file = orch.intents_path(self.directory)
        add_intents.decompose(self.root, add_path=add_file, out=intents_file)
        intents_document = json.loads(intents_file.read_text(encoding="utf-8"))
        intents_document["intents"] = [
            {"id": intent, "goal": f"Deliver {intent}.", "covers": [element], "dependencies": dependencies,
             "scope": [intent], "non_goals": [], "evidence_refs": [], "blocker": None, "ready": True}
            for intent, element, dependencies in (("first", "payments-rule", []), ("second", "billing-rule", ["first"]))]
        intents_document["delivery"] = {"mode": "sequential", "order": ["first", "second"]}
        intents_file.write_text(json.dumps(intents_document), encoding="utf-8")
        for intent in ("first", "second"):
            add_intents.prepare_handoff(self.root, add_path=add_file, intents_path=intents_file,
                                        intent_ids=[intent], out=orch.handoff_dir(self.directory) / f"{intent}.json")
        for intent, change, capability in (("first", "first-change", "payments"), ("second", "second-change", "billing")):
            bundle = self.directory / "bundles" / intent
            (bundle / "specs" / capability).mkdir(parents=True)
            (bundle / "manifest.json").write_text(json.dumps({"change": change, "handoff": intent}), encoding="utf-8")
            (bundle / "specs" / capability / "spec.md").write_text("## ADDED Requirements\n", encoding="utf-8")
        self.assertEqual(self._status()["current_stage"], "complete")

    def _status(self) -> dict:
        return orch.status(self.root, requirement_id=REQUIREMENT_ID, base_dir=self.base_dir)

    def _rebind(self) -> dict | None:
        return orch.rebind(self.root, requirement_id=REQUIREMENT_ID, base_dir=self.base_dir,
                           own_changes=["first-change"], remaining_changes=["second-change"])

    def _artifacts(self) -> dict[str, str]:
        return {path.relative_to(self.directory).as_posix(): path.read_text(encoding="utf-8")
                for path in sorted(self.directory.rglob("*.json")) if path.name != "receipt.json"}

    def _approved(self) -> dict:
        return json.loads(orch.add_path(self.directory).read_text(encoding="utf-8"))

    def test_complete_chain_needs_no_rebind(self) -> None:
        self.assertIsNone(self._rebind())

    def test_own_child_change_is_rebound_without_reapproval(self) -> None:
        before = self._approved()
        own = commit(self.root, "first child (#1)", {
            "openspec/specs/payments/spec.md": "# Payments\nNew rule.\n",
            "openspec/changes/archive/2026-01-01-first-change/specs/payments/spec.md": "## ADDED Requirements\n",
        })
        self.assertNotEqual(self._status()["current_stage"], "complete")
        receipt = self._rebind()
        self.assertEqual(self._status()["current_stage"], "complete")
        after = self._approved()
        for key in ("elements", "assumptions", "unresolved_choices", "requirement", "reused_constraints"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["prepared_against"], own)
        self.assertIn(f"carried from {before['approval']['digest']}", after["approval"]["approved_by"])
        self.assertIn("approved by owner", after["approval"]["approved_by"])
        self.assertEqual(receipt["add_digest"], {"from": before["approval"]["digest"], "to": after["approval"]["digest"]})
        self.assertEqual(receipt["to_revision"], own)
        [source] = [item for item in receipt["sources"] if item["path"] == "openspec/specs/payments/spec.md"]
        self.assertEqual(source["commits"], [{"commit": own, "own": True}])
        self.assertTrue(Path(receipt["receipt"]).is_file())

    def test_mixed_commit_cannot_attribute_another_capability_to_the_child(self) -> None:
        mixed = commit(self.root, "first child plus another spec", {
            "openspec/specs/payments/spec.md": "# Payments\nNew rule.\n",
            "openspec/specs/billing/spec.md": "# Billing\nSmuggled.\n",
            "openspec/changes/archive/2026-01-01-first-change/specs/payments/spec.md": "## ADDED Requirements\n",
        })
        before = self._artifacts()
        with self.assertRaisesRegex(orch.RebindStop, f"openspec/specs/billing/spec.md \\({mixed[:12]}\\)"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)

    def test_commit_archiving_another_change_is_not_own(self) -> None:
        commit(self.root, "two archives", {
            "openspec/specs/payments/spec.md": "# Payments\nNew rule.\n",
            "openspec/changes/archive/2026-01-01-first-change/specs/payments/spec.md": "## ADDED Requirements\n",
            "openspec/changes/archive/2026-01-01-unrelated/specs/payments/spec.md": "## ADDED Requirements\n",
        })
        receipt = self._rebind()
        [source] = [item for item in receipt["sources"] if item["path"] == "openspec/specs/payments/spec.md"]
        self.assertFalse(source["commits"][0]["own"])

    def test_receipt_write_failure_rolls_back_without_a_receipt(self) -> None:
        commit(self.root, "first child", {
            "openspec/specs/payments/spec.md": "# Payments\nNew.\n",
            "openspec/changes/archive/2026-01-01-first-change/specs/payments/spec.md": "## ADDED Requirements\n",
        })
        before = self._artifacts()
        real = orch._write_json

        def failing(path, payload):
            if path.name.startswith("rebind-"):
                real(path, payload)
                raise OSError("receipt disk full")
            real(path, payload)

        with mock.patch.object(orch, "_write_json", side_effect=failing), \
             self.assertRaisesRegex(orch.RebindStop, "rolled back: receipt disk full"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)
        self.assertEqual(list(self.directory.glob("rebind-*.json")), [])

    def test_foreign_change_outside_the_remaining_children_is_rebound(self) -> None:
        foreign = commit(self.root, "other stream", {"openspec/specs/payments/spec.md": "# Payments\nOther.\n"})
        receipt = self._rebind()
        [source] = [item for item in receipt["sources"] if item["path"] == "openspec/specs/payments/spec.md"]
        self.assertEqual(source, {"path": "openspec/specs/payments/spec.md", "affected": False,
                                  "commits": [{"commit": foreign, "own": False}]})
        self.assertEqual(self._status()["current_stage"], "complete")

    def test_foreign_change_to_a_remaining_childs_spec_stops_without_writing(self) -> None:
        foreign = commit(self.root, "other stream", {"openspec/specs/billing/spec.md": "# Billing\nOther.\n"})
        before = self._artifacts()
        with self.assertRaisesRegex(orch.RebindStop, f"openspec/specs/billing/spec.md \\({foreign[:12]}\\).*re-approve"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)

    def test_add_edited_after_approval_stops_without_writing(self) -> None:
        commit(self.root, "first child", {"openspec/specs/payments/spec.md": "# Payments\nNew.\n"})
        add_file = orch.add_path(self.directory)
        document = json.loads(add_file.read_text(encoding="utf-8"))
        document["elements"][0]["statement"] = "Payments, changed."
        add_file.write_text(json.dumps(document), encoding="utf-8")
        before = self._artifacts()
        with self.assertRaisesRegex(orch.RebindStop, "changed since its approval"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)

    def test_edited_intent_set_stops_without_writing(self) -> None:
        commit(self.root, "first child", {"openspec/specs/payments/spec.md": "# Payments\nNew.\n"})
        intents_file = orch.intents_path(self.directory)
        document = json.loads(intents_file.read_text(encoding="utf-8"))
        document["intents"][1]["goal"] = "Something else."
        intents_file.write_text(json.dumps(document), encoding="utf-8")
        before = self._artifacts()
        with self.assertRaisesRegex(orch.RebindStop, "first.json no longer matches"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)

    def test_failure_while_writing_rolls_every_artifact_back(self) -> None:
        commit(self.root, "first child", {
            "openspec/specs/payments/spec.md": "# Payments\nNew.\n",
            "openspec/changes/archive/2026-01-01-first-change/proposal.md": "done\n",
        })
        before = self._artifacts()
        with mock.patch.object(orch.add_intents, "prepare_handoff", side_effect=add_intents.AddIntentsError("disk full")), \
             self.assertRaisesRegex(orch.RebindStop, "rolled back: disk full"):
            self._rebind()
        self.assertEqual(self._artifacts(), before)
        self.assertEqual(list(self.directory.glob("rebind-*.json")), [])


class SequentialRoundTests(unittest.TestCase):
    def _handoffs(self, root: Path) -> list[tuple[str, Path]]:
        entries = []
        for intent in ("second", "first"):
            path = root / f"{intent}.json"
            path.write_text(json.dumps({"intents": [{"id": intent}]}), encoding="utf-8")
            entries.append((intent, path))
        return entries

    def _round(self, root: Path, linked: dict[str, str], statuses: dict[str, str]):
        with mock.patch.object(execution.requirement_intake, "materialize_handoff",
                               side_effect=lambda *a, handoff_file, **k: {"child": f"acme/backlog#{handoff_file.stem}"}) as materialize, \
             mock.patch.object(execution, "_bundle", return_value=root / "bundle"), \
             mock.patch.object(execution.managed_project_status, "observe",
                               side_effect=lambda _root, source_issue: SimpleNamespace(current_status=statuses[source_issue])), \
             mock.patch.object(execution, "_done_child_is_delivered") as delivered:
            result = execution._sequential_round(root, REQUIREMENT, root, self._handoffs(root), linked,
                                                 ["first", "second"], False)
        return result, materialize, delivered

    def test_every_child_is_materialized_but_only_the_first_open_one_is_returned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linked: dict[str, str] = {}
            (ordered, completed), materialize, _ = self._round(
                root, linked, {"acme/backlog#first": "Ready", "acme/backlog#second": "Ready"})
            self.assertEqual([change for change, _ in ordered], ["first"])
            self.assertEqual(completed, [])
            self.assertEqual(materialize.call_count, 2)
            self.assertEqual(set(linked), {"first", "second"})

    def test_a_delivered_first_child_hands_over_to_the_second(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linked = {"first": "acme/backlog#first", "second": "acme/backlog#second"}
            (ordered, completed), materialize, delivered = self._round(
                root, linked, {"acme/backlog#first": "Done", "acme/backlog#second": "Ready"})
            self.assertEqual([change for change, _ in ordered], ["second"])
            self.assertEqual(completed, ["acme/backlog#first"])
            materialize.assert_not_called()
            delivered.assert_called_once_with(root, "acme/backlog#first", "first")

    def test_all_delivered_returns_no_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linked = {"first": "acme/backlog#first", "second": "acme/backlog#second"}
            (ordered, completed), _, _ = self._round(
                root, linked, {"acme/backlog#first": "Done", "acme/backlog#second": "Done"})
            self.assertEqual((ordered, completed), ([], ["acme/backlog#first", "acme/backlog#second"]))


class SequentialAdvanceTests(unittest.TestCase):
    def test_second_child_is_not_started_while_the_first_is_in_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / REQUIREMENT_ID
            directory.mkdir()
            (directory / "intents.json").write_text(json.dumps(intents_for(["first", "second"])), encoding="utf-8")
            handoffs = []
            for intent in ("first", "second"):
                path = root / f"{intent}.json"
                path.write_text(json.dumps({"intents": [{"id": intent, "dependencies": []}]}), encoding="utf-8")
                handoffs.append((intent, path))
            parent = {"body": "## Outcome\n\nShip it\n\n## Target repository\n\n`acme/project`\n",
                      "labels": [{"name": "type:requirement"}], "state": "OPEN"}
            linked = {"first": "acme/backlog#8", "second": "acme/backlog#9"}
            import _platform_common
            with mock.patch.object(_platform_common, "read_platform_config", return_value={"platform_version": "1.0"}), \
                 mock.patch.object(execution, "current_worktree_root", return_value=root), \
                 mock.patch.object(execution, "_git", return_value="main"), \
                 mock.patch.object(execution.requirement_target_lifecycle, "require_local_target_support"), \
                 mock.patch.object(execution.requirement_intake, "fetch_issue", return_value=parent), \
                 mock.patch.object(execution.orchestrate_pre_authoring, "status", return_value={"current_stage": "complete"}), \
                 mock.patch.object(execution.requirement_board, "claim_started"), \
                 mock.patch.object(execution, "_ordered_handoffs", return_value=handoffs), \
                 mock.patch.object(execution, "_linked_children_by_change", return_value=linked), \
                 mock.patch.object(execution.managed_project_status, "observe",
                                   return_value=SimpleNamespace(current_status="In review")), \
                 mock.patch.object(execution, "_advance_contributions") as contributions, \
                 mock.patch.object(execution, "_publish_active_child", return_value=True) as publish, \
                 mock.patch.object(execution.start_managed_task, "start_managed_task") as start:
                result = execution.advance(root, requirement=REQUIREMENT, base_dir=root)
            self.assertEqual((result["status"], result["child"]), ("await-child-review", "acme/backlog#8"))
            publish.assert_called_once_with(root.resolve(), "acme/backlog#8", "first")
            contributions.assert_not_called()
            start.assert_not_called()

    def test_unreadable_handoff_in_the_sequential_round_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = root / "first.json"
            broken.write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(execution.RequirementExecutionError, "cannot read handoff .*first.json"):
                execution._sequential_round(root, REQUIREMENT, root, [("first", broken)], {}, ["first"], False)

    def test_unreadable_intent_set_fails_naming_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / REQUIREMENT_ID).mkdir()
            (root / REQUIREMENT_ID / "intents.json").write_text("{broken", encoding="utf-8")
            with self.assertRaisesRegex(execution.RequirementExecutionError, "cannot read intent set .*intents.json"):
                execution._sequential_order(root, REQUIREMENT)
            (root / REQUIREMENT_ID / "intents.json").unlink()
            self.assertIsNone(execution._sequential_order(root, REQUIREMENT))


class TerminalAfterFirstChildTests(unittest.TestCase):
    def test_merging_the_first_sequential_child_does_not_close_the_requirement(self) -> None:
        ops = mock.Mock()
        ops.lineage.return_value = {"child": "acme/backlog#8", "requirement": REQUIREMENT}
        ops.children.return_value = ["acme/backlog#8", "acme/backlog#9"]
        ops.child_closed.side_effect = lambda _root, child: child == "acme/backlog#8"
        outcome = contour.run_terminal(ops, Path("/r"), 11, "agent/br-7-t1-first", "a" * 40,
                                       task_identity={"change": "first-change"})
        self.assertEqual(outcome, "child-reconciled; requirement awaits remaining children")
        ops.reconcile_parent.assert_not_called()
        ops.reconcile_child.assert_called_once_with(Path("/r"), "acme/backlog#8")


if __name__ == "__main__":
    unittest.main()
