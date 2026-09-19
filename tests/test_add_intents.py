"""Deterministic tests for the ADD -> Intents pre-authoring pipeline gates.

These exercise only structural/provenance/freshness/coverage properties, never
semantic quality -- consistent with the capability's documented boundary.
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
    }
    document.update(overrides)
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
        self._write(_valid_add(
            approved=True,
            unresolved_choices=[{
                "question": "Do tiers stack with per-seat pricing?",
                "status": "resolved",
                "resolution": "No; tiers replace per-seat pricing per the accepted billing spec.",
            }],
        ))
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
        self._write(_valid_add(
            approved=True,
            unresolved_choices=[{
                "question": "Which currency does billing use?",
                "status": "resolved",
                "resolution": "USD, per openspec/specs/billing/spec.md.",
            }],
        ))
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
        self._write(_valid_add(version=2))
        report = add_intents.validate_add(self.root, self.path, check_freshness=False)
        self.assertFalse(report.ok)
        self.assertTrue(any("unsupported ADD schema version" in error for error in report.errors))


def _approved_add(**overrides: object) -> dict[str, object]:
    return _valid_add(approved=True, **overrides)


class DecomposeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = init_repo()
        self.root = Path(self.tmp.name)
        self.add_path = self.root / "add.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_decompose_requires_approved_add(self) -> None:
        self.add_path.write_text(json.dumps(_valid_add(approved=False)), encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")

    def test_decompose_requires_structurally_valid_add(self) -> None:
        self.add_path.write_text(json.dumps(_valid_add(approved=True, version=2)), encoding="utf-8")
        with self.assertRaises(AddIntentsError):
            add_intents.decompose(self.root, add_path=self.add_path, out=self.root / "intents.json")

    def test_decompose_scaffolds_intent_set(self) -> None:
        self.add_path.write_text(json.dumps(_approved_add()), encoding="utf-8")
        out = self.root / "intents.json"
        payload = add_intents.decompose(self.root, add_path=self.add_path, out=out, business_context="Tiered pricing")
        self.assertEqual(payload["add_id"], "add-tiered-pricing")
        self.assertEqual(payload["intents"], [])
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
        self.add_path.write_text(json.dumps(_approved_add()), encoding="utf-8")
        self.intents_path = self.root / "intents.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, document: dict[str, object]) -> None:
        self.intents_path.write_text(json.dumps(document), encoding="utf-8")

    def _base(self, **overrides: object) -> dict[str, object]:
        document: dict[str, object] = {
            "version": 1,
            "add_id": "add-tiered-pricing",
            "business_context": "Tiered pricing",
            "intents": [_intent()],
            "non_implementation": [],
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
        add_document = _valid_add()
        add_document["elements"].append({
            "id": "element-existing-currency", "category": "invariant", "status": "preserved",
            "statement": "Billing already uses USD per the accepted spec; unchanged.",
        })
        add_document["approved"] = True
        self.add_path.write_text(json.dumps(add_document), encoding="utf-8")
        self._write(self._base())
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
        document["approved"] = True
        add_path.write_text(json.dumps(document), encoding="utf-8")

        validate_result = self._run("validate-add", str(add_path))
        self.assertEqual(validate_result.returncode, 0, validate_result.stdout + validate_result.stderr)
        self.assertEqual(json.loads(validate_result.stdout)["freshness"], "fresh")

        intents_path = self.root / "intents.json"
        decompose_result = self._run("decompose", "--add", str(add_path), "--out", str(intents_path))
        self.assertEqual(decompose_result.returncode, 0, decompose_result.stderr)

        intents_document = json.loads(intents_path.read_text(encoding="utf-8"))
        intents_document["intents"] = [_intent()]
        intents_path.write_text(json.dumps(intents_document), encoding="utf-8")

        validate_intents_result = self._run("validate-intents", str(intents_path), "--add", str(add_path))
        self.assertEqual(validate_intents_result.returncode, 0, validate_intents_result.stdout + validate_intents_result.stderr)


if __name__ == "__main__":
    unittest.main()
