"""E2E coverage for the resumable pre-authoring orchestrator.

Exercises the full snapshot -> ADD -> intents -> handoff flow purely through
orchestrate_pre_authoring.py's own status()/init()/record_decision(), calling
project_evidence.py/add_intents.py directly only the way a main agent would
between orchestrator calls -- never duplicating their gate logic here.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPTS = ROOT / "template" / "scripts"
# Always insert at position 0, even if already present elsewhere on
# sys.path: several test modules prepend the bare scripts/ directory (whose
# shims execute unconditionally on import), and a merely-conditional insert
# here can leave template/scripts shadowed behind it depending on discovery
# order.
sys.path.insert(0, str(TEMPLATE_SCRIPTS))

import add_intents  # noqa: E402
import orchestrate_pre_authoring as orch  # noqa: E402
import project_evidence  # noqa: E402


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=True)


def init_repo() -> tempfile.TemporaryDirectory[str]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    for relative, content in {
        "README.md": "# Example\n",
        "AGENTS.md": "# Rules\n",
        "docs/engineering/project-rules.md": "# Engineering rules\n",
        "docs/context/domain.md": "# Domain\n",
        "openspec/specs/payments/spec.md": "# Payments\n",
        "src/payments.py": "def pay(): pass\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "seed")
    return temporary


def worker_results_for(root: Path, *, confidence: str = "high", conflicts: list[str] | None = None) -> dict[str, dict]:
    current = project_evidence.inventory(root)
    results: dict[str, dict] = {}
    for concern, dependencies in current["dependencies"].items():
        facts = [] if not dependencies else [{"statement": f"{concern} fact", "evidence_refs": [dependencies[0]]}]
        results[concern] = {
            "version": 1,
            "confidence": confidence,
            "facts": facts,
            "conflicts": conflicts or [],
            "unknowns": [],
            "provenance_ref": f"routing:{concern}",
            "usage": {"model_calls": 1},
        }
    return results


def build_fresh_snapshot(root: Path, out: Path) -> dict:
    snapshot, _ = project_evidence.build_snapshot(root, prior=None, results=worker_results_for(root))
    out.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
    return snapshot


def snapshot_evidence_entry(root: Path, snapshot_path: Path, snapshot: dict, concern: str = "project-context") -> dict:
    projection = snapshot["projections"][concern]
    return {
        "source": snapshot_path.relative_to(root).as_posix(),
        "kind": add_intents.EVIDENCE_KIND_SNAPSHOT,
        "digest": projection["digest"],
        "snapshot_digest": snapshot["digest"],
        "snapshot_revision": snapshot["revision"],
        "projection": concern,
        "projection_digest": projection["digest"],
        "projection_status": projection["status"],
    }


class OrchestratorFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.requirement = self.root / "requirement.md"
        self.requirement.write_text("Add tiered pricing to billing.\n", encoding="utf-8")
        self.base_dir = self.root / ".claude" / "pre-authoring"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _init(self) -> dict:
        state = orch.init(
            self.root,
            requirement_id="add-tiered-pricing",
            requirement_file=self.requirement,
            target_repository="acme/billing",
            base_dir=self.base_dir,
        )
        orch.select_depth(self.root, requirement_id="add-tiered-pricing", depth=orch.DEPTH_MATERIAL_DESIGN,
                          reason="Pricing tiers change behavior and boundaries", base_dir=self.base_dir)
        return state

    def _status(self) -> dict:
        return orch.status(self.root, requirement_id="add-tiered-pricing", base_dir=self.base_dir)

    def test_init_scaffolds_state_and_add(self) -> None:
        state = self._init()
        self.assertEqual(state["target_repository"], "acme/billing")
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        self.assertTrue(orch.add_path(directory).is_file())

    def test_unselected_requirement_has_no_add_and_deterministic_skip_is_reusable(self) -> None:
        orch.init(self.root, requirement_id="add-tiered-pricing", requirement_file=self.requirement,
                  target_repository="acme/billing", base_dir=self.base_dir)
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        self.assertFalse(orch.add_path(directory).exists())
        self.assertEqual(self._status()["current_stage"], "selection")
        decision = orch.select_depth(self.root, requirement_id="add-tiered-pricing", depth=orch.DEPTH_DETERMINISTIC,
                                     reason="Mechanical correction", base_dir=self.base_dir)
        self.assertEqual(decision["routing"], "none")
        first = self._status()
        self.assertEqual(first["current_stage"], "complete")
        self.assertFalse(orch.add_path(directory).exists())
        receipt = orch.skip_path(directory).read_text(encoding="utf-8")
        self._status()
        self.assertEqual(orch.skip_path(directory).read_text(encoding="utf-8"), receipt)

    def test_bounded_evidence_only_requests_selected_projection(self) -> None:
        orch.init(self.root, requirement_id="add-tiered-pricing", requirement_file=self.requirement,
                  target_repository="acme/billing", base_dir=self.base_dir)
        orch.select_depth(self.root, requirement_id="add-tiered-pricing", depth=orch.DEPTH_BOUNDED_EVIDENCE,
                          reason="Need rules lookup", concerns=["rules"], base_dir=self.base_dir)
        result = self._status()
        self.assertIn("--concern rules", result["blocker"]["action"])
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results={}, concerns=["rules"])
        orch._write_json(orch.snapshot_path(directory), snapshot)
        result = self._status()
        self.assertEqual(set(result["blocker"]["worker_requests"]), {"rules"})
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=snapshot,
            results={"rules": worker_results_for(self.root)["rules"]}, concerns=["rules"])
        orch._write_json(orch.snapshot_path(directory), snapshot)
        self.assertEqual(self._status()["current_stage"], "complete")
        self.assertFalse(orch.add_path(directory).exists())

    def test_changed_requirement_invalidates_selection_and_skip_but_not_snapshot(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        snapshot = build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        self.assertEqual(self._status()["current_stage"], "add")
        self.requirement.write_text("Change tier boundaries.\n", encoding="utf-8")
        orch.init(self.root, requirement_id="add-tiered-pricing", requirement_file=self.requirement,
                  target_repository="acme/billing", base_dir=self.base_dir, refresh_requirement=True)
        self.assertFalse(orch.selection_path(directory).exists())
        self.assertFalse(orch.add_path(directory).exists())
        self.assertEqual(orch._load_json(orch.snapshot_path(directory), "snapshot"), snapshot)
        self.assertEqual(self._status()["current_stage"], "selection")

    def test_material_selection_recovers_missing_add_without_resetting_decision(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        orch.add_path(directory).unlink()
        orch.select_depth(self.root, requirement_id="add-tiered-pricing", depth=orch.DEPTH_MATERIAL_DESIGN,
                          reason="Pricing tiers change behavior and boundaries", base_dir=self.base_dir)
        self.assertTrue(orch.add_path(directory).is_file())

    def test_init_is_idempotent_for_the_same_requirement(self) -> None:
        first = self._init()
        second = self._init()
        self.assertEqual(first, second)

    def test_init_refuses_to_rebind_a_different_requirement_to_the_same_id(self) -> None:
        self._init()
        other = self.root / "other.md"
        other.write_text("A completely different requirement.\n", encoding="utf-8")
        with self.assertRaises(orch.OrchestratorError):
            orch.init(
                self.root, requirement_id="add-tiered-pricing", requirement_file=other,
                target_repository="acme/billing", base_dir=self.base_dir,
            )

    def test_init_recovers_from_a_partial_failure_that_left_state_without_add(self) -> None:
        """Regression: a prior init() that wrote state.json but raised before
        new_add() completed must not permanently wedge the requirement -- a
        later init() call with the same arguments must retry the ADD
        scaffold, not silently return state for a missing artifact."""
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        directory.mkdir(parents=True)
        requirement_digest = orch._digest(self.requirement.read_text(encoding="utf-8"))
        orch._write_json(orch.state_path(directory), {
            "version": orch.STATE_VERSION,
            "id": "add-tiered-pricing",
            "requirement_file": str(self.requirement),
            "requirement_digest": requirement_digest,
            "target_repository": "acme/billing",
            "created_at": "2024-01-01T00:00:00Z",
        })
        self.assertFalse(orch.add_path(directory).is_file())
        self._init()
        self.assertTrue(orch.add_path(directory).is_file())
        result = self._status()
        self.assertNotEqual(result["stages"].get("snapshot", {}).get("state"), None)

    def test_record_decision_rollback_is_atomic(self) -> None:
        """Regression: the rollback write on a failed record-decision must use
        the same atomic-write path as every other mutation in this module."""
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        # approved=True with no elements and a mismatched approval digest
        # forces _validate_add_document to reject the in-memory candidate
        # after record_decision resolves the only open choice, exercising
        # the rollback path.
        add_document["unresolved_choices"] = [{"question": "Pick a default currency?", "status": "open"}]
        add_document["approved"] = True
        add_document["approval"] = {"digest": "0" * 64, "approved_at": "2024-01-01T00:00:00Z"}
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        before = add_file.read_text(encoding="utf-8")
        with self.assertRaises(orch.OrchestratorError):
            orch.record_decision(
                self.root, requirement_id="add-tiered-pricing", index=0,
                resolution="USD", base_dir=self.base_dir,
            )
        self.assertEqual(add_file.read_text(encoding="utf-8"), before)
        # No stray temp file left behind by the rollback write.
        self.assertEqual(list(directory.glob(".add.json.*")), [])

    def test_status_before_snapshot_reports_missing_snapshot(self) -> None:
        self._init()
        result = self._status()
        self.assertEqual(result["current_stage"], "snapshot")
        self.assertEqual(result["stages"]["snapshot"]["state"], "missing")

    def test_snapshot_needing_extraction_surfaces_worker_requests(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        snapshot, _ = project_evidence.build_snapshot(self.root, prior=None, results={})
        orch._write_json(orch.snapshot_path(directory), snapshot)
        result = self._status()
        self.assertEqual(result["stages"]["snapshot"]["state"], "needs-worker")
        self.assertEqual(set(result["stages"]["snapshot"]["worker_requests"]), set(project_evidence.CONCERNS))

    def test_clean_run_reaches_complete_handoff(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")

        # Snapshot stage: build with full worker results (simulates the main
        # agent having run the routine read-only workers requested above).
        snapshot = build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        result = self._status()
        self.assertEqual(result["current_stage"], "add")
        self.assertEqual(result["stages"]["add"]["state"], "needs-drafting")

        # ADD stage: a design worker fills elements/evidence with no open choice.
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        evidence_entry = snapshot_evidence_entry(self.root, orch.snapshot_path(directory), snapshot)
        add_document["evidence"] = [evidence_entry]
        add_document["elements"] = [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
        ]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        result = self._status()
        self.assertEqual(result["stages"]["add"]["state"], "needs-approval")

        add_intents.approve_add(self.root, add_file)
        result = self._status()
        self.assertEqual(result["current_stage"], "intents")
        self.assertEqual(result["stages"]["intents"]["state"], "missing")

        # Intents stage: decompose scaffolds an empty set; a decomposition
        # worker fills one ready intent covering the ADD's only element.
        intents_file = orch.intents_path(directory)
        add_intents.decompose(self.root, add_path=add_file, out=intents_file)
        intents_document = json.loads(intents_file.read_text(encoding="utf-8"))
        intents_document["intents"] = [{
            "id": "intent-tier-boundary", "goal": "Introduce the new pricing tier boundary.",
            "covers": ["element-tier-boundary"], "dependencies": [], "scope": ["src/payments.py"],
            "non_goals": [], "evidence_refs": [], "blocker": None, "ready": True,
        }]
        intents_file.write_text(json.dumps(intents_document), encoding="utf-8")
        result = self._status()
        self.assertEqual(result["current_stage"], "handoff")
        self.assertEqual(result["stages"]["handoff"]["missing_intent_ids"], ["intent-tier-boundary"])

        # Handoff stage: prepare the envelope for the one ready intent.
        envelope_path = orch.handoff_dir(directory) / "intent-tier-boundary.json"
        add_intents.prepare_handoff(
            self.root, add_path=add_file, intents_path=intents_file,
            intent_ids=["intent-tier-boundary"], out=envelope_path,
        )
        result = self._status()
        self.assertEqual(result["current_stage"], "complete")
        self.assertIsNone(result["blocker"])
        self.assertIn("intent-tier-boundary", result["handoffs"])

        # Receipt is written for external inspection and carries no raw content.
        receipt = json.loads(orch.receipt_path(directory).read_text(encoding="utf-8"))
        self.assertEqual(receipt["current_stage"], "complete")
        self.assertNotIn("prompt", json.dumps(receipt))
        self.assertNotIn("transcript", json.dumps(receipt))

    def test_handoff_action_includes_requirement_context_when_bound(self) -> None:
        context = self.root / "requirement-context.json"
        context.write_text('{"outcome": "Tiered pricing"}\n', encoding="utf-8")
        orch.init(
            self.root,
            requirement_id="add-tiered-pricing",
            requirement_file=self.requirement,
            target_repository="acme/billing",
            base_dir=self.base_dir,
            business_context_file=context,
        )
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        action = orch._handoff_status(self.root, directory, ["intent-tier-boundary"])["action"]
        self.assertIn(f"--requirement-context-file {context}", action)

    def test_human_pause_surfaces_open_decision_and_resume_applies_the_answer(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        add_document["elements"] = [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
        ]
        add_document["unresolved_choices"] = [{
            "question": "Do tiers stack with per-seat pricing?",
            "status": "open",
            "alternatives": ["stack", "replace"],
            "evidence": ["openspec/specs/payments/spec.md"],
            "consequences": "Stacking changes billing totals for existing per-seat customers.",
            "affected_elements": ["element-tier-boundary"],
        }]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")

        # Pause: the orchestrator must not approve or guess -- it surfaces the
        # bounded decision request for main-agent/human mediation.
        result = self._status()
        self.assertEqual(result["current_stage"], "add")
        self.assertEqual(result["stages"]["add"]["state"], "needs-decision")
        decision = result["stages"]["add"]["decisions"][0]
        self.assertEqual(decision["question"], "Do tiers stack with per-seat pricing?")
        self.assertEqual(decision["alternatives"], ["stack", "replace"])
        self.assertEqual(decision["affected_elements"], ["element-tier-boundary"])

        # A subagent cannot self-approve: attempting approve-add while the
        # choice is still open fails closed.
        with self.assertRaises(add_intents.AddIntentsError):
            add_intents.approve_add(self.root, add_file)

        # Resume: apply the accepted human answer through the canonical path.
        orch.record_decision(
            self.root, requirement_id="add-tiered-pricing", index=0,
            resolution="No; tiers replace per-seat pricing per the accepted billing spec.",
            base_dir=self.base_dir,
        )
        result = self._status()
        self.assertEqual(result["stages"]["add"]["state"], "needs-approval")

    def test_record_decision_rejects_blank_resolution(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        add_document["unresolved_choices"] = [{"question": "Pick a default currency?", "status": "open"}]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        with self.assertRaises(orch.OrchestratorError):
            orch.record_decision(
                self.root, requirement_id="add-tiered-pricing", index=0, resolution="   ", base_dir=self.base_dir,
            )
        # Fails closed: the choice remains open, not silently resolved.
        reloaded = json.loads(add_file.read_text(encoding="utf-8"))
        self.assertEqual(reloaded["unresolved_choices"][0]["status"], "open")

    def test_resume_after_restart_does_not_repeat_fresh_worker_extraction(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        first = self._status()
        self.assertEqual(first["stages"]["snapshot"]["state"], "ready")

        # A brand-new call (simulating a restarted process/session) with no
        # new worker results still finds the same snapshot fresh, because
        # status() only re-validates identities -- it never redoes worker
        # extraction for a projection that is still bound to unchanged
        # sources.
        second = self._status()
        self.assertEqual(second["stages"]["snapshot"], first["stages"]["snapshot"])

    def test_upstream_mutation_invalidates_only_dependent_downstream_stage(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        snapshot = build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        add_document["evidence"] = [snapshot_evidence_entry(self.root, orch.snapshot_path(directory), snapshot)]
        add_document["elements"] = [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
        ]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        add_intents.approve_add(self.root, add_file)
        result = self._status()
        self.assertEqual(result["stages"]["add"]["state"], "ready")

        # Mutate a tracked source the snapshot depended on, without rebuilding
        # the snapshot. The snapshot stage itself is unaffected (still valid
        # against its own recorded source identities) but is now stale
        # relative to the live tree, so the orchestrator must stop there
        # rather than trusting the now-unproven downstream ADD/evidence link.
        (self.root / "docs" / "context" / "domain.md").write_text("# Domain (changed)\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "change domain context")
        result = self._status()
        self.assertEqual(result["current_stage"], "snapshot")
        self.assertEqual(result["stages"]["snapshot"]["state"], "stale")
        self.assertIn("docs/context/domain.md", result["stages"]["snapshot"]["changed_sources"])

    def test_stage_failure_is_reported_and_recoverable_without_touching_upstream(self) -> None:
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        snapshot = build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        add_file = orch.add_path(directory)
        add_document = json.loads(add_file.read_text(encoding="utf-8"))
        add_document["evidence"] = [snapshot_evidence_entry(self.root, orch.snapshot_path(directory), snapshot)]
        add_document["elements"] = [
            {"id": "element-a", "category": "boundary", "status": "new", "statement": "A"},
        ]
        add_file.write_text(json.dumps(add_document), encoding="utf-8")
        add_intents.approve_add(self.root, add_file)
        intents_file = orch.intents_path(directory)
        add_intents.decompose(self.root, add_path=add_file, out=intents_file)

        # A broken decomposition: a self-dependency cycle.
        intents_document = json.loads(intents_file.read_text(encoding="utf-8"))
        intents_document["intents"] = [{
            "id": "intent-a", "goal": "A", "covers": ["element-a"], "dependencies": ["intent-a"],
            "scope": [], "non_goals": [], "evidence_refs": [], "blocker": None, "ready": False,
        }]
        intents_file.write_text(json.dumps(intents_document), encoding="utf-8")
        result = self._status()
        self.assertEqual(result["stages"]["intents"]["state"], "invalid")
        self.assertTrue(any("cycle" in error for error in result["stages"]["intents"]["errors"]))
        # The already-approved, still-fresh ADD stage is untouched by the
        # downstream failure -- retry/repair is bounded to the culprit stage.
        self.assertEqual(result["stages"]["add"]["state"], "ready")

        # Repair only the broken stage and resume.
        intents_document["intents"][0]["dependencies"] = []
        intents_document["intents"][0]["ready"] = True
        intents_file.write_text(json.dumps(intents_document), encoding="utf-8")
        result = self._status()
        self.assertEqual(result["current_stage"], "handoff")

    def test_orchestrator_creates_no_competing_status_or_priority_fields(self) -> None:
        """Documentation-contract check: the receipt is navigation state only.

        No backlog-shaped field (status/priority/assignee) may appear, since
        the spec requires this receipt to never become a second lifecycle.
        """
        self._init()
        directory = orch.requirement_dir(self.base_dir, "add-tiered-pricing")
        build_fresh_snapshot(self.root, orch.snapshot_path(directory))
        self._status()
        receipt = json.loads(orch.receipt_path(directory).read_text(encoding="utf-8"))
        for forbidden in ("priority", "assignee", "status", "project_number"):
            self.assertNotIn(forbidden, receipt)


if __name__ == "__main__":
    unittest.main()
