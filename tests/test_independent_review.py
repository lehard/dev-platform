from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location("independent_review", SCRIPTS / "independent_review.py")
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review
SPEC.loader.exec_module(review)

LIFECYCLE_SPEC = importlib.util.spec_from_file_location("openspec_lifecycle", SCRIPTS / "openspec_lifecycle.py")
assert LIFECYCLE_SPEC and LIFECYCLE_SPEC.loader
lifecycle = importlib.util.module_from_spec(LIFECYCLE_SPEC)
sys.modules[LIFECYCLE_SPEC.name] = lifecycle
LIFECYCLE_SPEC.loader.exec_module(lifecycle)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


class IndependentReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "review@example.test")
        git(self.root, "config", "user.name", "Review Test")
        (self.root / "README.md").write_text("base\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "base")
        (self.root / ".dev-platform.toml").write_text("[independent_review]\nenabled = true\n", encoding="utf-8")
        self.change = self.root / "openspec" / "changes" / "review-change"
        self.change.mkdir(parents=True)
        (self.change / ".managed-task.json").write_text('{"change": "review-change"}\n', encoding="utf-8")
        (self.change / "proposal.md").write_text("# Proposal\n", encoding="utf-8")
        (self.change / "design.md").write_text("# Design\n", encoding="utf-8")
        (self.change / "tasks.md").write_text("- [ ] task\n", encoding="utf-8")
        self.request = review.prepare_request(self.root, self.change, "HEAD")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def report(self, perspective: str, findings: list[dict] | None = None, *, availability: str = "available") -> dict:
        data = {
            "schema_version": review.SCHEMA_VERSION,
            "perspective": perspective,
            "request_id": self.request["request_id"],
            "candidate": self.request["candidate"],
            "reviewer": {"runtime": "test-runtime", "context_id": f"fresh-{perspective}", "fresh_context": True, "write_access": False},
            "availability": availability,
            "findings": findings if findings is not None else [],
        }
        if availability == "unavailable":
            data["limitation"] = "test runtime unavailable"
        return data

    def write_report(self, perspective: str, findings: list[dict] | None = None, *, availability: str = "available") -> None:
        path = review.report_path(self.change, perspective)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.report(perspective, findings, availability=availability)), encoding="utf-8")

    def write_clear_reports(self) -> None:
        for perspective in review.PERSPECTIVES:
            self.write_report(perspective)

    def material_finding(self, finding_id: str, status: str = "blocker") -> dict:
        return {
            "id": finding_id,
            "severity": "material",
            "summary": "reviewer found a meaningful mismatch",
            "evidence": "independent review evidence",
            "disposition": {"status": status, "rationale": "controlled review scenario"},
        }

    def test_request_is_provider_neutral_and_requires_fresh_read_only_context(self) -> None:
        self.assertTrue(self.request["fresh_context_required"])
        self.assertEqual(set(self.request["perspectives"]), set(review.PERSPECTIVES))
        self.assertEqual(self.request["reviewer_constraints"]["write_access"], False)
        self.assertNotIn("provider", self.request)
        self.assertNotIn("model", self.request)

    def test_two_clear_reports_are_accepted_for_the_exact_candidate(self) -> None:
        self.write_clear_reports()
        evidence = review.validate_evidence(self.root, self.change)
        self.assertEqual(evidence["request_id"], self.request["request_id"])
        self.assertEqual(evidence["perspectives"], list(review.PERSPECTIVES))

    def test_record_copies_a_schema_valid_runtime_report_to_its_perspective_path(self) -> None:
        source = self.root / "runtime-report.json"
        source.write_text(json.dumps(self.report("spec-fidelity")), encoding="utf-8")
        destination = review.record_report(self.root, self.change, source)
        self.assertEqual(destination, review.report_path(self.change, "spec-fidelity"))
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["request_id"], self.request["request_id"])

    def test_changed_candidate_invalidates_old_review_evidence(self) -> None:
        self.write_clear_reports()
        (self.root / "README.md").write_text("candidate changed\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "candidate change")
        with self.assertRaisesRegex(review.IndependentReviewError, "stale"):
            review.validate_evidence(self.root, self.change)

    def test_spec_fidelity_mismatch_blocks_even_without_a_test_failure(self) -> None:
        self.write_report("spec-fidelity", [self.material_finding("missing-contract-behavior")])
        self.write_report("engineering-quality")
        with self.assertRaisesRegex(review.IndependentReviewError, "spec-fidelity:missing-contract-behavior"):
            review.validate_evidence(self.root, self.change)

    def test_engineering_quality_issue_blocks_without_a_spec_violation(self) -> None:
        self.write_report("spec-fidelity")
        self.write_report("engineering-quality", [self.material_finding("unsafe-maintenance-pattern")])
        with self.assertRaisesRegex(review.IndependentReviewError, "engineering-quality:unsafe-maintenance-pattern"):
            review.validate_evidence(self.root, self.change)

    def test_enabled_lifecycle_blocks_a_pass_receipt_with_unresolved_review_finding(self) -> None:
        self.write_report("spec-fidelity", [self.material_finding("missing-contract-behavior")])
        self.write_report("engineering-quality")
        (self.change / "tasks.md").write_text("- [x] task\n", encoding="utf-8")
        (self.change / "verification.md").write_text(
            "OpenSpec-Verify: PASS\nVerification-Method: equivalent-review\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(SystemExit, "unresolved material independent-review findings"):
            lifecycle.require_ready(self.change)

    def test_fixed_or_explicitly_rejected_material_findings_are_accepted(self) -> None:
        self.write_report("spec-fidelity", [self.material_finding("fixed", "fixed")])
        self.write_report("engineering-quality", [self.material_finding("rejected", "rejected")])
        review.validate_evidence(self.root, self.change)

    def test_unavailable_review_is_a_truthful_archive_blocker(self) -> None:
        self.write_report("spec-fidelity", availability="unavailable")
        self.write_report("engineering-quality")
        with self.assertRaisesRegex(review.IndependentReviewError, "independent review unavailable"):
            review.validate_evidence(self.root, self.change)

    def test_review_is_opt_in_and_does_not_apply_to_quick_or_unmanaged_work(self) -> None:
        self.assertTrue(review.review_is_required(self.root, self.change))
        (self.root / ".dev-platform.toml").write_text("[independent_review]\nenabled = false\n", encoding="utf-8")
        self.assertFalse(review.review_is_required(self.root, self.change))
        (self.root / ".dev-platform.toml").write_text("[independent_review]\nenabled = true\n", encoding="utf-8")
        (self.change / ".managed-task.json").unlink()
        self.assertFalse(review.review_is_required(self.root, self.change))

    def test_platform_review_adapter_has_no_publish_or_completion_operation(self) -> None:
        source = (SCRIPTS / "independent_review.py").read_text(encoding="utf-8")
        for forbidden in ("project_publish", "managed_project_status", "openspec_lifecycle", "subprocess"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
