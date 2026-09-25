"""Real pre-authoring handoffs consumed by the Requirement executor."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import add_intents
import execute_requirement as execution
import orchestrate_pre_authoring as orch
import project_evidence
import requirement_terminal
from test_orchestrate_pre_authoring import init_repo, worker_results_for, snapshot_evidence_entry

REQ = "acme/backlog#7"
ORIGINAL_RUN = subprocess.run


class RequirementFlowEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = init_repo()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "branch", "-M", "main"], cwd=self.root, check=True, capture_output=True)
        self.base = self.root / ".claude/pre-authoring"
        self.requirement = self.root / "requirement.json"
        self.requirement.write_text('{"outcome":"Change billing"}\n', encoding="utf-8")
        orch.init(self.root, requirement_id="requirement-7", requirement_file=self.requirement,
                  target_repository="acme/billing", base_dir=self.base)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run_with_linked(self, linked: dict[str, str], ready: list[tuple[Path, object] | None], *, publish: bool = False):
        with mock.patch.object(execution, "current_worktree_root", return_value=self.root), \
                mock.patch.object(execution.requirement_intake, "fetch_issue", return_value={"labels": [{"name": "type:requirement"}]}), \
                mock.patch.object(execution, "_linked_children_by_change", return_value=linked), \
                mock.patch.object(execution.managed_project_status, "observe", return_value=SimpleNamespace(current_status="In progress")), \
                mock.patch.object(execution, "_ready_receipt", side_effect=ready), \
                mock.patch.object(execution.requirement_board, "reconcile_nonterminal"), \
                mock.patch.object(execution.start_managed_task, "start_managed_task", return_value=(SimpleNamespace(task_root=self.root / "child"), "head", False)), \
                mock.patch.object(execution.requirement_integration, "assemble_candidate", return_value={"digest": "exact"}) as assemble, \
                mock.patch.object(execution.requirement_integration, "compose_candidate"), \
                mock.patch.object(execution.requirement_integration, "publish_candidate", return_value={"status": "merged-and-reconciled"}), \
                mock.patch.object(requirement_terminal, "reconcile_parent", return_value={"status": "done"}) as terminal, \
                mock.patch.object(execution.subprocess, "run") as run:
            def git_only(command, *args, **kwargs):
                if command[0] == "git":
                    return ORIGINAL_RUN(command, *args, **kwargs)
                return SimpleNamespace(returncode=0)
            run.side_effect = git_only
            result = execution.advance(self.root, requirement=REQ, base_dir=self.base)
            return result, assemble.call_count, terminal.call_count

    def test_deterministic_direct_handoff_enters_single_child_execution(self) -> None:
        orch.select_depth(self.root, requirement_id="requirement-7", depth=orch.DEPTH_DETERMINISTIC,
                          reason="Mechanical correction", base_dir=self.base)
        result, assembled, terminal = self._run_with_linked({"single": "acme/backlog#8"}, [None])
        self.assertEqual(result["status"], "implement-child")
        self.assertEqual(result["change"], "single")
        self.assertEqual((assembled, terminal), (0, 0))
        result, assembled, terminal = self._run_with_linked(
            {"single": "acme/backlog#8"}, [(self.root / "ready.json", object())]
        )
        self.assertEqual(result["status"], "done")
        self.assertEqual((assembled, terminal), (0, 1))

    def test_bounded_evidence_direct_handoff_enters_single_child_execution(self) -> None:
        orch.select_depth(self.root, requirement_id="requirement-7", depth=orch.DEPTH_BOUNDED_EVIDENCE,
                          reason="Inspect rules", concerns=["rules"], base_dir=self.base)
        directory = orch.requirement_dir(self.base, "requirement-7")
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results={}, concerns=["rules"])
        snapshot, _ = project_evidence.build_snapshot(
            self.root, prior=snapshot, results={"rules": worker_results_for(self.root)["rules"]}, concerns=["rules"]
        )
        orch._write_json(orch.snapshot_path(directory), snapshot)
        result, assembled, _ = self._run_with_linked({"single": "acme/backlog#8"}, [None])
        self.assertEqual(result["status"], "implement-child")
        self.assertEqual(assembled, 0)

    def test_material_two_child_handoffs_reach_shared_candidate(self) -> None:
        orch.select_depth(self.root, requirement_id="requirement-7", depth=orch.DEPTH_MATERIAL_DESIGN,
                          reason="Two independent billing boundaries", base_dir=self.base)
        directory = orch.requirement_dir(self.base, "requirement-7")
        results = worker_results_for(self.root)
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results=results)
        orch._write_json(orch.snapshot_path(directory), snapshot)
        add_file = orch.add_path(directory)
        add = json.loads(add_file.read_text(encoding="utf-8"))
        add["evidence"] = [snapshot_evidence_entry(self.root, orch.snapshot_path(directory), snapshot)]
        add["elements"] = [
            {"id": "element-one", "category": "boundary", "status": "new", "statement": "First boundary"},
            {"id": "element-two", "category": "boundary", "status": "new", "statement": "Second boundary"},
        ]
        add_file.write_text(json.dumps(add), encoding="utf-8")
        add_intents.approve_add(self.root, add_file)
        intents_file = orch.intents_path(directory)
        add_intents.decompose(self.root, add_path=add_file, out=intents_file)
        intents = json.loads(intents_file.read_text(encoding="utf-8"))
        intents["intents"] = [
            {"id": name, "goal": f"Implement {name}", "covers": [element], "dependencies": [],
             "scope": [scope], "non_goals": [], "evidence_refs": [], "blocker": None, "ready": True}
            for name, element, scope in (("first", "element-one", "src/one.py"), ("second", "element-two", "src/two.py"))
        ]
        intents_file.write_text(json.dumps(intents), encoding="utf-8")
        for name in ("first", "second"):
            add_intents.prepare_handoff(self.root, add_path=add_file, intents_path=intents_file,
                                        intent_ids=[name], out=orch.handoff_dir(directory) / f"{name}.json")
        result, assembled, terminal = self._run_with_linked(
            {"first": "acme/backlog#8", "second": "acme/backlog#9"},
            [(self.root / "first.json", object()), (self.root / "second.json", object())],
        )
        self.assertEqual(result["status"], "merged-and-reconciled")
        self.assertEqual((assembled, terminal), (1, 0))


if __name__ == "__main__":
    unittest.main()
