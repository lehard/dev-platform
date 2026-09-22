"""Deterministic tests for the ADD -> Intents pre-authoring pipeline gates.

These exercise structural/provenance/freshness/coverage/digest-binding
properties, never semantic quality -- consistent with the capability's
documented boundary. Where a requested behavior is genuinely agent-level
semantic judgment (the atomicity split-candidate criteria), the test below is
explicitly a documentation-contract assertion, not a claim that Python
decides atomicity.
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
sys.path.insert(0, str(TEMPLATE_SCRIPTS))

import add_intents  # noqa: E402
import project_evidence  # noqa: E402
from add_intents import AddIntentsError  # noqa: E402


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True)


def init_repo() -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    git("init", "-q", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    git("add", "README.md", cwd=root)
    git("commit", "-q", "-m", "seed", cwd=root)
    return tmp


class NewAddTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scaffolds_add_bound_to_current_head(self) -> None:
        requirement = self.root / "requirement.md"
        requirement.write_text("Add tiered pricing to billing.\n", encoding="utf-8")
        out = self.root / "add.json"
        payload = add_intents.new_add(
            self.root, add_id="add-tiered-pricing", requirement_file=requirement,
            target_repository="acme/billing", out=out,
        )
        self.assertEqual(payload["add_id"], "add-tiered-pricing")
        self.assertEqual(payload["prepared_against"], add_intents.current_revision(self.root))
        self.assertFalse(payload["approved"])
        self.assertIsNone(payload["approval"])
        self.assertEqual(payload["evidence"], [])
        on_disk = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, payload)

    def test_rejects_empty_requirement(self) -> None:
        requirement = self.root / "requirement.md"
        requirement.write_text("   \n", encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.new_add(
                self.root, add_id="add-x", requirement_file=requirement,
                target_repository="acme/billing", out=self.root / "add.json",
            )

    def test_rejects_unsafe_add_id(self) -> None:
        requirement = self.root / "requirement.md"
        requirement.write_text("text\n", encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.new_add(
                self.root, add_id="Not Safe!", requirement_file=requirement,
                target_repository="acme/billing", out=self.root / "add.json",
            )


def _valid_add(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "version": 1,
        "add_id": "add-tiered-pricing",
        "requirement": {"digest": "a" * 64, "summary": ""},
        "target_repository": "acme/billing",
        "prepared_against": "0" * 40,
        "evidence": [{"source": "openspec/specs/billing/spec.md", "kind": "accepted-spec", "digest": "b" * 64}],
        "reused_constraints": [],
        "elements": [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
        ],
        "assumptions": [],
        "contradictions": [],
        "unresolved_choices": [],
        "approved": False,
        "approval": None,
    }
    document.update(overrides)
    return document


def _approved_add(**overrides: object) -> dict[str, object]:
    """A structurally valid ADD with an approval receipt bound to its own final content.

    Overrides are applied to the base document *before* the digest is
    computed, so the receipt is self-consistent for arbitrary field
    overrides. Callers that want a deliberately *stale* approval should call
    this first and then mutate the returned document afterward.
    """
    document = _valid_add(**overrides)
    document["approved"] = True
    document["approval"] = {"digest": add_intents.add_content_digest(document), "approved_at": "2024-01-01T00:00:00Z"}
    return document


class ValidateAddTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.path = self.root / "add.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, document: dict[str, object]) -> None:
        self.path.write_text(json.dumps(document), encoding="utf-8")

    def test_valid_unapproved_add_passes(self) -> None:
        self._write(_valid_add())
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertTrue(report.ok, report.errors)

    def test_freshness_detects_stale_revision(self) -> None:
        self._write(_valid_add())
        report = add_intents.validate_add(self.root, self.path, check_freshness=True)
        self.assertEqual(report.freshness, "stale-needs-semantic-preflight")

    def test_freshness_detects_fresh_revision(self) -> None:
        self._write(_valid_add(prepared_against=add_intents.current_revision(self.root)))
        report = add_intents.validate_add(self.root, self.path, check_freshness=True)
        self.assertEqual(report.freshness, "fresh")

    def test_approval_blocked_by_open_unresolved_choice(self) -> None:
        self._write(_valid_add(
            approved=True,
            unresolved_choices=[{"question": "Do tiers stack with per-seat pricing?", "status": "open"}],
        ))
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("unresolved consequential choice" in error for error in report.errors))

    def test_approval_allowed_once_choice_resolved(self) -> None:
        document = _approved_add(
            unresolved_choices=[{
                "question": "Do tiers stack with per-seat pricing?",
                "status": "resolved",
                "resolution": "No; tiers replace per-seat pricing per the accepted billing spec.",
            }],
        )
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertTrue(report.ok, report.errors)

    def test_approval_blocked_by_unresolved_contradiction(self) -> None:
        self._write(_valid_add(
            approved=True,
            contradictions=[{"statement": "Design doc and code disagree on rounding.", "resolved": False}],
        ))
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("contradiction" in error for error in report.errors))

    def test_evidence_resolved_choice_does_not_ask_a_question(self) -> None:
        # Evidence-resolvable facts are recorded as already-resolved and never block approval.
        document = _approved_add(
            unresolved_choices=[{
                "question": "Which currency does billing use?",
                "status": "resolved",
                "resolution": "USD, per openspec/specs/billing/spec.md.",
            }],
        )
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertTrue(report.ok, report.errors)

    def test_duplicate_element_ids_rejected(self) -> None:
        document = _valid_add()
        document["elements"] = [
            {"id": "dup", "category": "boundary", "status": "new", "statement": "a"},
            {"id": "dup", "category": "boundary", "status": "new", "statement": "b"},
        ]
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("duplicate element id" in error for error in report.errors))

    def test_invalid_element_category_rejected(self) -> None:
        document = _valid_add()
        document["elements"] = [{"id": "e1", "category": "not-a-category", "status": "new", "statement": "a"}]
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)

    def test_unsupported_version_rejected(self) -> None:
        self._write(_valid_add(version=99))
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("unsupported ADD schema version" in error for error in report.errors))

    def test_missing_target_repository_rejected(self) -> None:
        document = _valid_add()
        document["target_repository"] = ""
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("target_repository" in error for error in report.errors))

    def test_assumptions_must_be_non_empty_strings(self) -> None:
        document = _valid_add()
        document["assumptions"] = ["", 5]
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("assumptions" in error for error in report.errors))

    def test_reused_constraint_requires_source_and_statement(self) -> None:
        document = _valid_add()
        document["reused_constraints"] = [{"source": "openspec/specs/billing/spec.md"}]
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("statement" in error for error in report.errors))

    # -- Approval receipt / content-digest binding --------------------------

    def test_approve_add_writes_a_digest_bound_receipt(self) -> None:
        self._write(_valid_add())
        payload = add_intents.approve_add(self.root, self.path, approved_by="alexx")
        self.assertTrue(payload["approved"])
        self.assertEqual(payload["approval"]["digest"], add_intents.add_content_digest(_valid_add()))
        self.assertEqual(payload["approval"]["approved_by"], "alexx")
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertTrue(report.ok, report.errors)

    def test_approve_add_refuses_with_open_choice(self) -> None:
        document = _valid_add(unresolved_choices=[{"question": "Undecided?", "status": "open"}])
        self._write(document)
        with self.assertRaises(AddIntentsError):
            add_intents.approve_add(self.root, self.path)

    def test_approved_true_without_receipt_is_rejected(self) -> None:
        # A hand-edited `approved: true` with no `approval` object is not a valid approval.
        self._write(_valid_add(approved=True))
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("no approval receipt" in error for error in report.errors))

    def test_approval_digest_mismatch_is_rejected(self) -> None:
        document = _approved_add()
        document["approval"]["digest"] = "0" * 64  # tampered/fabricated receipt
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("stale" in error for error in report.errors))

    def test_mutating_add_after_approval_invalidates_it(self) -> None:
        document = _approved_add()
        # Mutate material content (a new element) without re-running approve-add.
        document["elements"].append(
            {"id": "element-extra", "category": "boundary", "status": "new", "statement": "Unreviewed addition."}
        )
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("stale" in error for error in report.errors), report.errors)

    def test_reapproving_after_mutation_restores_validity(self) -> None:
        document = _approved_add()
        document["elements"].append(
            {"id": "element-extra", "category": "boundary", "status": "new", "statement": "Reviewed addition."}
        )
        self._write(document)
        add_intents.approve_add(self.root, self.path)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertTrue(report.ok, report.errors)

    # -- Snapshot evidence schema --------------------------------------------

    def test_snapshot_evidence_requires_additional_fields(self) -> None:
        document = _valid_add()
        document["evidence"].append({"source": "snap.json", "kind": "project-evidence-snapshot", "digest": "c" * 64})
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("snapshot_digest" in error for error in report.errors))

    def test_snapshot_evidence_digest_must_equal_projection_digest(self) -> None:
        document = _valid_add()
        document["evidence"].append({
            "source": "snap.json",
            "kind": "project-evidence-snapshot",
            "digest": "c" * 64,
            "snapshot_digest": "d" * 64,
            "snapshot_revision": "e" * 40,
            "projection": "project-context",
            "projection_digest": "f" * 64,  # mismatched vs. digest
            "projection_status": "fresh",
        })
        self._write(document)
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("digest must equal projection_digest" in error for error in report.errors))


def _build_fresh_snapshot(root: Path, out: Path) -> dict[str, object]:
    """Build a real Project Evidence Snapshot with one fresh projection.

    Reuses project_evidence.py's own build/validate primitives directly; this
    test never reimplements snapshot digesting/freshness.
    """
    worker_result = {
        "version": 1,
        "confidence": "high",
        "facts": [{"statement": "README documents the project.", "evidence_refs": ["README.md"]}],
        "conflicts": [],
        "unknowns": [],
    }
    snapshot, _ = project_evidence.build_snapshot(root, prior=None, results={"project-context": worker_result})
    out.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
    return snapshot


def _snapshot_evidence_entry(root: Path, snapshot_path: Path, snapshot: dict[str, object]) -> dict[str, object]:
    projection = snapshot["projections"]["project-context"]
    return {
        "source": snapshot_path.relative_to(root).as_posix(),
        "kind": "project-evidence-snapshot",
        "digest": projection["digest"],
        "snapshot_digest": snapshot["digest"],
        "snapshot_revision": snapshot["revision"],
        "projection": "project-context",
        "projection_digest": projection["digest"],
        "projection_status": projection["status"],
    }


class SnapshotEvidenceFreshnessTests(unittest.TestCase):
    """Exercise decompose()'s blocking (not merely warning) use of project_evidence.py."""

    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.snapshot_path = self.root / "snapshot.json"
        self.snapshot = _build_fresh_snapshot(self.root, self.snapshot_path)
        self.evidence_entry = _snapshot_evidence_entry(self.root, self.snapshot_path, self.snapshot)
        self.add_path = self.root / "add.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_add(self, **overrides: object) -> dict[str, object]:
        base_overrides: dict[str, object] = {
            "prepared_against": add_intents.current_revision(self.root),
            "evidence": [self.evidence_entry],
        }
        base_overrides.update(overrides)
        document = _approved_add(**base_overrides)
        self.add_path.write_text(json.dumps(document), encoding="utf-8")
        return document

    def test_decompose_succeeds_with_fresh_snapshot_evidence(self) -> None:
        add_document = self._write_add()
        payload = add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")
        self.assertEqual(payload["snapshot_refs"], [self.evidence_entry])
        self.assertEqual(payload["approved_add_digest"], add_document["approval"]["digest"])

    def test_decompose_blocks_on_tampered_snapshot_digest(self) -> None:
        tampered_entry = dict(self.evidence_entry)
        tampered_entry["snapshot_digest"] = "0" * 64
        tampered_entry["digest"] = tampered_entry["projection_digest"]
        self._write_add(evidence=[tampered_entry])
        with self.assertRaises(AddIntentsError) as ctx:
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")
        self.assertIn("snapshot_digest", str(ctx.exception))

    def test_decompose_blocks_when_snapshot_source_changed(self) -> None:
        self._write_add()
        # Change tracked content the snapshot depended on without rebuilding the snapshot.
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(AddIntentsError) as ctx:
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")
        self.assertIn("stale", str(ctx.exception).lower())

    def test_decompose_blocks_when_snapshot_file_missing(self) -> None:
        self._write_add()
        self.snapshot_path.unlink()
        with self.assertRaises(AddIntentsError):
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")

    def test_decompose_blocks_on_stale_add_revision(self) -> None:
        # prepared_against left at a fake SHA rather than the current HEAD.
        document = _approved_add(evidence=[self.evidence_entry])
        self.add_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaises(AddIntentsError) as ctx:
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")
        self.assertIn("stale", str(ctx.exception).lower())


class DecomposeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.add_path = self.root / "add.json"
        self.fresh_revision = add_intents.current_revision(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_decompose_requires_approved_add(self) -> None:
        self.add_path.write_text(
            json.dumps(_valid_add(approved=False, prepared_against=self.fresh_revision)), encoding="utf-8"
        )
        with self.assertRaises(AddIntentsError):
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")

    def test_decompose_requires_structurally_valid_add(self) -> None:
        self.add_path.write_text(json.dumps(_valid_add(approved=True, version=2)), encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")

    def test_decompose_scaffolds_intent_set(self) -> None:
        document = _approved_add(prepared_against=self.fresh_revision)
        self.add_path.write_text(json.dumps(document), encoding="utf-8")
        out = self.root / "intents.json"
        payload = add_intents.decompose(self.root, add_path=self.add_path, out=out, business_context="Tiered pricing")
        self.assertEqual(payload["add_id"], "add-tiered-pricing")
        self.assertEqual(payload["intents"], [])
        self.assertEqual(payload["approved_add_digest"], document["approval"]["digest"])
        self.assertEqual(payload["snapshot_refs"], [])
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), payload)


def _intent(**overrides: object) -> dict[str, object]:
    intent: dict[str, object] = {
        "id": "intent-tier-boundary",
        "goal": "Introduce the new pricing tier boundary.",
        "scope": ["billing service"],
        "non_goals": [],
        "covers": ["element-tier-boundary"],
        "dependencies": [],
        "evidence_refs": [],
        "blocker": None,
        "ready": True,
    }
    intent.update(overrides)
    return intent


class ValidateIntentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.add_path = self.root / "add.json"
        self.fresh_revision = add_intents.current_revision(self.root)
        self.add_document = _approved_add(prepared_against=self.fresh_revision)
        self.add_path.write_text(json.dumps(self.add_document), encoding="utf-8")
        self.intents_path = self.root / "intents.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, document: dict[str, object]) -> None:
        self.intents_path.write_text(json.dumps(document), encoding="utf-8")

    def _base(self, **overrides: object) -> dict[str, object]:
        document: dict[str, object] = {
            "version": 1,
            "add_id": "add-tiered-pricing",
            "approved_add_digest": self.add_document["approval"]["digest"],
            "business_context": "Tiered pricing",
            "intents": [_intent()],
            "non_implementation": [],
            "snapshot_refs": [],
        }
        document.update(overrides)
        return document

    def test_full_coverage_passes(self) -> None:
        self._write(self._base())
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_add_id_mismatch_rejected(self) -> None:
        self._write(self._base(add_id="add-something-else"))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("does not match ADD add_id" in error for error in report.errors))

    def test_preserved_element_needs_no_intent_coverage(self) -> None:
        # An element carried forward from an existing decision (status="preserved") is not a
        # new/changed delta, so decomposition must not be forced to re-cover it with an intent.
        add_document = _approved_add(prepared_against=self.fresh_revision, elements=[
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
            {
                "id": "element-existing-currency", "category": "invariant", "status": "preserved",
                "statement": "Billing already uses USD per the accepted spec; unchanged.",
            },
        ])
        self.add_path.write_text(json.dumps(add_document), encoding="utf-8")
        self._write(self._base(approved_add_digest=add_document["approval"]["digest"]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_missing_design_decision_returns_to_add_refinement_instead_of_guessing(self) -> None:
        # Decomposition cannot bound the intent without a decision the ADD never made: the
        # element gets neither intent coverage nor a non_implementation disposition, which
        # validate-intents must flag rather than let the gap pass silently.
        self._write(self._base(intents=[_intent(covers=[], ready=False, blocker="Rounding rule is undecided in the ADD.")]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("no intent coverage" in error for error in report.errors))

    def test_missing_coverage_rejected(self) -> None:
        self._write(self._base(intents=[]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("no intent coverage" in error for error in report.errors))

    def test_non_implementation_disposition_satisfies_coverage(self) -> None:
        self._write(self._base(intents=[], non_implementation=[
            {"element_id": "element-tier-boundary", "reason": "Deferred to a later phase per proposal.md non-goals."},
        ]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_dangling_dependency_rejected(self) -> None:
        self._write(self._base(intents=[_intent(dependencies=["intent-does-not-exist"])]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("unknown intent" in error for error in report.errors))

    def test_dangling_covers_rejected(self) -> None:
        self._write(self._base(intents=[_intent(covers=["element-does-not-exist"])]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("unknown ADD element" in error for error in report.errors))

    def test_dangling_evidence_ref_rejected(self) -> None:
        self._write(self._base(intents=[_intent(evidence_refs=["does/not/exist.md"])]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("unknown evidence/constraint source" in error for error in report.errors))

    def test_known_evidence_ref_allowed(self) -> None:
        self._write(self._base(intents=[_intent(evidence_refs=["openspec/specs/billing/spec.md"])]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_dependency_cycle_rejected(self) -> None:
        self._write(self._base(intents=[
            _intent(id="intent-a", covers=["element-tier-boundary"], dependencies=["intent-b"]),
            _intent(id="intent-b", covers=[], dependencies=["intent-a"]),
        ]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("cycle" in error for error in report.errors))

    def test_overlap_without_reason_rejected(self) -> None:
        self._write(self._base(intents=[
            _intent(id="intent-a", covers=["element-tier-boundary"]),
            _intent(id="intent-b", covers=["element-tier-boundary"]),
        ]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("covered by multiple intents" in error for error in report.errors))

    def test_overlap_with_explicit_reason_allowed(self) -> None:
        self._write(self._base(intents=[
            _intent(id="intent-a", covers=["element-tier-boundary"], overlap_reason="Shared migration step, tracked jointly."),
            _intent(id="intent-b", covers=["element-tier-boundary"], overlap_reason="Shared migration step, tracked jointly."),
        ]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_ready_intent_with_blocker_rejected(self) -> None:
        self._write(self._base(intents=[_intent(ready=True, blocker="Missing decision on rounding.")]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("cannot be ready while a blocker" in error for error in report.errors))

    def test_not_ready_intent_with_blocker_allowed(self) -> None:
        self._write(self._base(intents=[_intent(ready=False, blocker="Missing decision on rounding.", covers=[])],
                                non_implementation=[{"element_id": "element-tier-boundary", "reason": "returned to ADD refinement"}]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_ready_must_be_boolean(self) -> None:
        self._write(self._base(intents=[_intent(ready="yes")]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("ready must be a boolean" in error for error in report.errors))

    def test_scope_must_be_a_string_list(self) -> None:
        self._write(self._base(intents=[_intent(scope="billing service")]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("scope" in error for error in report.errors))

    # -- Parent digest binding ------------------------------------------------

    def test_missing_approved_add_digest_rejected(self) -> None:
        document = self._base()
        del document["approved_add_digest"]
        self._write(document)
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("approved_add_digest" in error for error in report.errors))

    def test_mismatched_approved_add_digest_rejected(self) -> None:
        self._write(self._base(approved_add_digest="0" * 64))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("does not match the parent ADD" in error for error in report.errors))

    def test_stale_approved_add_digest_rejected_after_add_mutation(self) -> None:
        # A valid binding at authoring time, but the ADD is mutated (and
        # re-approved) afterward without regenerating the intent set.
        self._write(self._base())
        mutated = dict(self.add_document)
        mutated["elements"] = list(mutated["elements"]) + [
            {"id": "element-extra", "category": "boundary", "status": "new", "statement": "New unreviewed element."}
        ]
        mutated["approval"] = {"digest": add_intents.add_content_digest(mutated), "approved_at": "2024-02-01T00:00:00Z"}
        self.add_path.write_text(json.dumps(mutated), encoding="utf-8")
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("does not match the parent ADD" in error for error in report.errors))

    def test_stale_parent_add_revision_rejected(self) -> None:
        stale_document = _approved_add(prepared_against="0" * 40)
        self.add_path.write_text(json.dumps(stale_document), encoding="utf-8")
        self._write(self._base(approved_add_digest=stale_document["approval"]["digest"]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("stale-needs-semantic-preflight" in error for error in report.errors))

    # -- snapshot_refs ----------------------------------------------------------

    def test_snapshot_refs_must_match_add_evidence(self) -> None:
        fabricated = {
            "source": "snap.json", "kind": "project-evidence-snapshot", "digest": "c" * 64,
            "snapshot_digest": "d" * 64, "snapshot_revision": "e" * 40,
            "projection": "project-context", "projection_digest": "c" * 64, "projection_status": "fresh",
        }
        self._write(self._base(snapshot_refs=[fabricated]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("does not match a snapshot evidence entry" in error for error in report.errors))

    def test_snapshot_refs_fresh_and_bound_passes(self) -> None:
        snapshot_path = self.root / "snapshot.json"
        snapshot = _build_fresh_snapshot(self.root, snapshot_path)
        entry = _snapshot_evidence_entry(self.root, snapshot_path, snapshot)
        add_document = _approved_add(prepared_against=self.fresh_revision, evidence=[entry])
        self.add_path.write_text(json.dumps(add_document), encoding="utf-8")
        self._write(self._base(approved_add_digest=add_document["approval"]["digest"], snapshot_refs=[entry]))
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)

    def test_snapshot_refs_stale_rejected(self) -> None:
        snapshot_path = self.root / "snapshot.json"
        snapshot = _build_fresh_snapshot(self.root, snapshot_path)
        entry = _snapshot_evidence_entry(self.root, snapshot_path, snapshot)
        add_document = _approved_add(prepared_against=self.fresh_revision, evidence=[entry])
        self.add_path.write_text(json.dumps(add_document), encoding="utf-8")
        self._write(self._base(approved_add_digest=add_document["approval"]["digest"], snapshot_refs=[entry]))
        (self.root / "README.md").write_text("changed after binding\n", encoding="utf-8")
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertFalse(report.ok)
        self.assertTrue(any("stale" in error.lower() for error in report.errors))


class HandoffTests(unittest.TestCase):
    """End-to-end requirement -> snapshot -> ADD -> approval -> intents -> handoff evidence."""

    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        (self.root / "openspec" / "specs" / "billing").mkdir(parents=True)
        (self.root / "openspec" / "specs" / "billing" / "spec.md").write_text(
            "# billing\ncurrency: USD\n", encoding="utf-8"
        )
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "-m", "seed billing spec", cwd=self.root)

        self.snapshot_path = self.root / "snapshot.json"
        self.snapshot = _build_fresh_snapshot(self.root, self.snapshot_path)
        self.snapshot_entry = _snapshot_evidence_entry(self.root, self.snapshot_path, self.snapshot)

        self.add_path = self.root / "add.json"
        requirement = self.root / "requirement.md"
        requirement.write_text("Add tiered pricing to billing.\n", encoding="utf-8")
        add_intents.new_add(
            self.root, add_id="add-tiered-pricing", requirement_file=requirement,
            target_repository="acme/billing", out=self.add_path,
        )
        document = json.loads(self.add_path.read_text(encoding="utf-8"))
        document["evidence"] = [self.snapshot_entry]
        document["reused_constraints"] = [
            {"source": "openspec/specs/billing/spec.md", "statement": "Billing already uses USD; unchanged by this delta."}
        ]
        document["elements"] = [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
            {"id": "element-currency", "category": "invariant", "status": "preserved", "statement": "Currency remains USD."},
        ]
        self.add_path.write_text(json.dumps(document), encoding="utf-8")

        add_intents.approve_add(self.root, self.add_path, approved_by="alexx")
        self.approved_add = json.loads(self.add_path.read_text(encoding="utf-8"))

        self.intents_path = self.root / "intents.json"
        add_intents.decompose(self.root, add_path=self.add_path, out=self.intents_path, business_context="Tiered pricing")
        intents_document = json.loads(self.intents_path.read_text(encoding="utf-8"))
        intents_document["intents"] = [_intent(
            evidence_refs=["openspec/specs/billing/spec.md"],
        )]
        self.intents_path.write_text(json.dumps(intents_document), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_intents_pass_validation_and_preserve_add_decisions(self) -> None:
        report = add_intents.validate_intents(self.root, self.intents_path, add_path=self.add_path)
        self.assertTrue(report.ok, report.errors)
        # The preserved currency constraint was never re-covered by an intent (status="preserved"),
        # yet validation still passes: OpenSpec authoring does not silently re-decide it.
        intents_document = json.loads(self.intents_path.read_text(encoding="utf-8"))
        self.assertEqual(intents_document["approved_add_digest"], self.approved_add["approval"]["digest"])

    def test_handoff_envelope_carries_preserved_constraint_and_approved_decision(self) -> None:
        envelope_path = self.root / "handoff.json"
        envelope = add_intents.prepare_handoff(
            self.root, add_path=self.add_path, intents_path=self.intents_path,
            intent_ids=["intent-tier-boundary"], out=envelope_path,
        )
        self.assertEqual(envelope["approved_add_digest"], self.approved_add["approval"]["digest"])
        reused_sources = {item["source"] for item in envelope["reused_constraints"]}
        self.assertIn("openspec/specs/billing/spec.md", reused_sources)
        material_ids = {item["id"] for item in envelope["material_elements"]}
        self.assertEqual(material_ids, {"element-tier-boundary"})  # only the covered element, not the preserved one
        report = add_intents.check_handoff_staleness(
            self.root, envelope_path=envelope_path, add_path=self.add_path, intents_path=self.intents_path,
        )
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.freshness, "fresh")

    def test_handoff_envelope_preserves_complete_requirement_context(self) -> None:
        envelope = add_intents.prepare_handoff(
            self.root, add_path=self.add_path, intents_path=self.intents_path,
            intent_ids=["intent-tier-boundary"], out=self.root / "handoff.json",
            requirement_context={
                "version": 1,
                "outcome": "Introduce tiered pricing.",
                "context": "Customers need a lower-cost plan.",
                "acceptance_evidence": "A customer can subscribe to a tier.",
                "exclusions": "No change to invoicing.",
                "target_repository": "acme/billing",
            },
        )
        self.assertEqual(envelope["requirement_context"], {
            "version": 1,
            "outcome": "Introduce tiered pricing.",
            "context": "Customers need a lower-cost plan.",
            "acceptance_evidence": "A customer can subscribe to a tier.",
            "exclusions": "No change to invoicing.",
            "target_repository": "acme/billing",
        })

    def test_handoff_requires_group_reason_for_multiple_intents(self) -> None:
        intents_document = json.loads(self.intents_path.read_text(encoding="utf-8"))
        intents_document["intents"].append(_intent(id="intent-second", covers=[]))
        self.intents_path.write_text(json.dumps(intents_document), encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.prepare_handoff(
                self.root, add_path=self.add_path, intents_path=self.intents_path,
                intent_ids=["intent-tier-boundary", "intent-second"], out=self.root / "handoff.json",
            )

    def test_handoff_marked_stale_after_add_mutation(self) -> None:
        envelope_path = self.root / "handoff.json"
        add_intents.prepare_handoff(
            self.root, add_path=self.add_path, intents_path=self.intents_path,
            intent_ids=["intent-tier-boundary"], out=envelope_path,
        )
        mutated = dict(self.approved_add)
        mutated["elements"] = list(mutated["elements"]) + [
            {"id": "element-new", "category": "boundary", "status": "new", "statement": "New decision after handoff."}
        ]
        add_intents._write_json(self.add_path, mutated)  # bypass approve_add: simulate an unreviewed hand-edit
        report = add_intents.check_handoff_staleness(
            self.root, envelope_path=envelope_path, add_path=self.add_path, intents_path=self.intents_path,
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.freshness, "stale-needs-regeneration")

    def test_handoff_marked_stale_after_snapshot_mutation(self) -> None:
        envelope_path = self.root / "handoff.json"
        add_intents.prepare_handoff(
            self.root, add_path=self.add_path, intents_path=self.intents_path,
            intent_ids=["intent-tier-boundary"], out=envelope_path,
        )
        intents_document = json.loads(self.intents_path.read_text(encoding="utf-8"))
        intents_document["snapshot_refs"] = [self.snapshot_entry]
        self.intents_path.write_text(json.dumps(intents_document), encoding="utf-8")
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        envelope["snapshot_refs"] = [self.snapshot_entry]
        envelope["digest"] = add_intents._content_digest({k: v for k, v in envelope.items() if k != "digest"})
        envelope_path.write_text(json.dumps(envelope), encoding="utf-8")

        (self.root / "README.md").write_text("changed after handoff\n", encoding="utf-8")
        report = add_intents.check_handoff_staleness(
            self.root, envelope_path=envelope_path, add_path=self.add_path, intents_path=self.intents_path,
        )
        self.assertFalse(report.ok)

    def test_handoff_marked_stale_after_intents_mutation(self) -> None:
        envelope_path = self.root / "handoff.json"
        add_intents.prepare_handoff(
            self.root, add_path=self.add_path, intents_path=self.intents_path,
            intent_ids=["intent-tier-boundary"], out=envelope_path,
        )
        intents_document = json.loads(self.intents_path.read_text(encoding="utf-8"))
        intents_document["intents"][0]["scope"] = ["billing service", "entitlement service"]
        self.intents_path.write_text(json.dumps(intents_document), encoding="utf-8")
        report = add_intents.check_handoff_staleness(
            self.root, envelope_path=envelope_path, add_path=self.add_path, intents_path=self.intents_path,
        )
        self.assertFalse(report.ok)


class MultiOutcomeSplitCandidateTests(unittest.TestCase):
    """The split/refinement judgment itself is agent-level semantic review, not a Python
    unit-testable property (see design.md and dev-platform/capabilities/add-intents.md,
    "Semantic atomicity review"). What *is* mechanically testable and asserted here is that
    the guidance an agent must apply is actually documented, and that the structural layer
    still lets a materially-independent-outcomes intent set validate structurally (because
    Python deliberately does not decide atomicity) while `overlap_reason`/coverage gates
    remain the only enforced structural signal.
    """

    def test_atomicity_guidance_documents_split_candidate_criteria(self) -> None:
        doc = (ROOT / "dev-platform" / "capabilities" / "add-intents.md").read_text(encoding="utf-8")
        self.assertIn("Semantic atomicity review", doc)
        for phrase in (
            "Independent triggers, policies, or outcomes",
            "Independently verifiable, deliverable, or rollbackable",
            "business outcome mixed with independent infra",
            "container for several independent changes",
        ):
            self.assertIn(phrase, doc)

    def test_structural_gates_do_not_themselves_flag_multi_outcome_intents(self) -> None:
        # A single intent bundling two materially independent outcomes (billing tier pricing
        # and an unrelated notification channel) still passes *structural* validation: Python
        # never encodes the semantic split judgment. This documents the boundary rather than
        # asserting Python should catch it -- catching it is the agent's job per the guidance
        # asserted above.
        tmp = init_repo()
        try:
            root = Path(tmp.name)
            add_path = root / "add.json"
            document = _approved_add(
                prepared_against=add_intents.current_revision(root),
                elements=[
                    {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier."},
                    {"id": "element-notify", "category": "integration", "status": "new", "statement": "New notification channel."},
                ],
            )
            add_path.write_text(json.dumps(document), encoding="utf-8")
            intents_path = root / "intents.json"
            bundled = {
                "version": 1,
                "add_id": "add-tiered-pricing",
                "approved_add_digest": document["approval"]["digest"],
                "business_context": "Tiered pricing",
                "intents": [_intent(
                    id="intent-bundled",
                    goal="Introduce tiered pricing and a new notification channel.",
                    covers=["element-tier-boundary", "element-notify"],
                )],
                "non_implementation": [],
                "snapshot_refs": [],
            }
            intents_path.write_text(json.dumps(bundled), encoding="utf-8")
            report = add_intents.validate_intents(root, intents_path, add_path=add_path)
            self.assertTrue(report.ok, report.errors)  # structurally valid; a split call is agent judgment, not this gate
        finally:
            tmp.cleanup()


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TEMPLATE_SCRIPTS / "add_intents.py"), *args],
            cwd=self.root, text=True, capture_output=True,
        )

    def test_end_to_end_cli_flow(self) -> None:
        requirement = self.root / "requirement.md"
        requirement.write_text("Add tiered pricing to billing.\n", encoding="utf-8")
        add_path = self.root / "add.json"
        result = self._run(
            "new-add", "--add-id", "add-tiered-pricing", "--requirement-file", str(requirement),
            "--target-repository", "acme/billing", "--out", str(add_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        document = json.loads(add_path.read_text(encoding="utf-8"))
        document["elements"] = [
            {"id": "element-tier-boundary", "category": "boundary", "status": "new", "statement": "New pricing tier boundary."},
        ]
        add_path.write_text(json.dumps(document), encoding="utf-8")

        approve_result = self._run("approve-add", str(add_path))
        self.assertEqual(approve_result.returncode, 0, approve_result.stdout + approve_result.stderr)

        validate_result = self._run("validate-add", str(add_path))
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)
        validate_payload = json.loads(validate_result.stdout)
        self.assertEqual(validate_payload["freshness"], "fresh")
        self.assertTrue(validate_payload["content_digest"])

        intents_path = self.root / "intents.json"
        decompose_result = self._run("decompose", "--add", str(add_path), "--out", str(intents_path))
        self.assertEqual(decompose_result.returncode, 0, decompose_result.stderr)

        intents_document = json.loads(intents_path.read_text(encoding="utf-8"))
        intents_document["intents"] = [_intent()]
        intents_path.write_text(json.dumps(intents_document), encoding="utf-8")

        validate_intents_result = self._run("validate-intents", str(intents_path), "--add", str(add_path))
        self.assertEqual(validate_intents_result.returncode, 0, validate_intents_result.stdout + validate_intents_result.stderr)

        handoff_path = self.root / "handoff.json"
        handoff_result = self._run(
            "prepare-handoff", "--add", str(add_path), "--intents", str(intents_path),
            "--intent-id", "intent-tier-boundary", "--out", str(handoff_path),
        )
        self.assertEqual(handoff_result.returncode, 0, handoff_result.stdout + handoff_result.stderr)
        self.assertTrue(handoff_path.is_file())

        validate_handoff_result = self._run(
            "validate-handoff", str(handoff_path), "--add", str(add_path), "--intents", str(intents_path),
        )
        self.assertEqual(
            validate_handoff_result.returncode, 0, validate_handoff_result.stdout + validate_handoff_result.stderr
        )
        self.assertTrue(json.loads(validate_handoff_result.stdout)["ok"])

    def test_approve_add_cli_rejects_unresolved_choice(self) -> None:
        requirement = self.root / "requirement.md"
        requirement.write_text("Add tiered pricing to billing.\n", encoding="utf-8")
        add_path = self.root / "add.json"
        self._run(
            "new-add", "--add-id", "add-tiered-pricing", "--requirement-file", str(requirement),
            "--target-repository", "acme/billing", "--out", str(add_path),
        )
        document = json.loads(add_path.read_text(encoding="utf-8"))
        document["unresolved_choices"] = [{"question": "Undecided?", "status": "open"}]
        add_path.write_text(json.dumps(document), encoding="utf-8")
        result = self._run("approve-add", str(add_path))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
