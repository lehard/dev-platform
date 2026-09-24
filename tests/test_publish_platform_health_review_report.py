from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_platform_health_review_report as report  # noqa: E402


class FakeGh:
    """Records calls instead of shelling out to a real `gh` binary."""

    def __init__(self, *, open_reports: list[dict] | None = None, created_number: int = 42) -> None:
        self.open_reports = open_reports or []
        self.created_number = created_number
        self.label_ensured = False
        self.created: dict | None = None
        self.closed: list[int] = []

    def ensure_label(self) -> None:
        self.label_ensured = True

    def list_open_reports(self) -> list[dict]:
        return self.open_reports

    def create_report_issue(self, title: str, body: str) -> dict:
        self.created = {"title": title, "body": body}
        return {
            "number": self.created_number,
            "html_url": f"https://github.com/lehard/dev-platform/issues/{self.created_number}",
        }

    def close_issue(self, number: int) -> None:
        self.closed.append(number)


def _outcome(name: str, result: str = "success", number: str = "7", url: str = "https://x/7") -> report.ReviewOutcome:
    return report._outcome(name, result, number, url)


class RenderSectionTests(unittest.TestCase):
    def test_success_with_issue_links_to_it(self) -> None:
        text = report.render_section(_outcome("Process Health Review"))
        self.assertIn("ran.", text)
        self.assertIn("#7", text)
        self.assertIn("https://x/7", text)

    def test_success_without_issue_notes_no_report(self) -> None:
        outcome = report._outcome("Process Health Review", "success", "", "")
        text = report.render_section(outcome)
        self.assertIn("ran but did not produce a report issue", text)

    def test_skipped_states_did_not_run(self) -> None:
        outcome = report._outcome("Architecture Health Review", "skipped", "", "")
        text = report.render_section(outcome)
        self.assertIn("did not run", text)

    def test_failure_states_did_not_complete(self) -> None:
        outcome = report._outcome("Architecture Health Review", "failure", "", "")
        text = report.render_section(outcome)
        self.assertIn("did not complete", text)
        self.assertIn("failure", text)

    def test_cancelled_states_did_not_complete(self) -> None:
        outcome = report._outcome("Architecture Health Review", "cancelled", "", "")
        text = report.render_section(outcome)
        self.assertIn("did not complete", text)

    def test_unrecognized_result_is_stated_explicitly(self) -> None:
        outcome = report._outcome("Architecture Health Review", "neutral", "", "")
        text = report.render_section(outcome)
        self.assertIn("unrecognized job result", text)
        self.assertIn("neutral", text)


class ExtractReviewedAtTests(unittest.TestCase):
    def test_extracts_value_from_report_body(self) -> None:
        body = "# Platform Health Review\n\n- reviewed_at: 2026-09-15T06:00:00Z\n- main_sha: abc123\n"
        self.assertEqual(report.extract_reviewed_at(body), "2026-09-15T06:00:00Z")

    def test_missing_field_returns_none(self) -> None:
        self.assertIsNone(report.extract_reviewed_at("no such field here"))

    def test_empty_body_returns_none(self) -> None:
        self.assertIsNone(report.extract_reviewed_at(""))


class PreviousBoundaryTests(unittest.TestCase):
    def test_no_prior_reports_is_none(self) -> None:
        self.assertEqual(report.previous_boundary([]), "none")

    def test_picks_most_recently_created_reports_reviewed_at(self) -> None:
        prior = [
            {
                "created_at": "2026-09-08T06:05:00Z",
                "body": "- reviewed_at: 2026-09-08T06:00:00Z\n",
            },
            {
                "created_at": "2026-09-15T06:05:00Z",
                "body": "- reviewed_at: 2026-09-15T06:00:00Z\n",
            },
        ]
        self.assertEqual(report.previous_boundary(prior), "2026-09-15T06:00:00Z")

    def test_ignores_reports_without_a_parsable_reviewed_at(self) -> None:
        prior = [{"created_at": "2026-09-15T06:05:00Z", "body": "no field here"}]
        self.assertEqual(report.previous_boundary(prior), "none")


class ReportTitleTests(unittest.TestCase):
    def test_uses_fixed_prefix_and_date_only(self) -> None:
        self.assertEqual(
            report.report_title("2026-09-22T06:00:00Z"),
            "[platform-health-review] 2026-09-22",
        )

    def test_falls_back_to_raw_value_when_unparsable(self) -> None:
        self.assertEqual(report.report_title("not-a-date"), "[platform-health-review] not-a-date")


class RenderBodyTests(unittest.TestCase):
    def test_body_records_required_fields_and_both_sections(self) -> None:
        body = report.render_body(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="deadbeef",
            boundary="2026-09-15T06:00:00Z",
            evidence_status="available",
            unavailable_evidence=None,
            process_result="success",
            architecture_result="success",
            process_section="process section text",
            architecture_section="architecture section text",
        )
        self.assertIn("reviewed_at: 2026-09-22T06:00:00Z", body)
        self.assertIn("main_sha: deadbeef", body)
        self.assertIn("previous_review_boundary: 2026-09-15T06:00:00Z", body)
        self.assertIn("audit_status: complete", body)
        self.assertIn("private_evidence: available", body)
        self.assertIn("## Process Health Review", body)
        self.assertIn("process section text", body)
        self.assertIn("## Architecture Health Review", body)
        self.assertIn("architecture section text", body)


class PublishTests(unittest.TestCase):
    def test_normal_run_creates_one_issue_and_closes_nothing_when_no_prior_report(self) -> None:
        gh = FakeGh(open_reports=[], created_number=101)
        result = report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review"),
            architecture=_outcome("Architecture Health Review"),
            gh=gh,
        )
        self.assertTrue(gh.label_ensured)
        self.assertEqual(result["number"], 101)
        self.assertEqual(result["previous_review_boundary"], "none")
        self.assertEqual(gh.closed, [])
        self.assertIn("[platform-health-review] 2026-09-22", gh.created["title"])

    def test_repeat_run_closes_prior_report_and_carries_its_boundary(self) -> None:
        prior = {
            "number": 55,
            "created_at": "2026-09-15T06:05:00Z",
            "body": "- reviewed_at: 2026-09-15T06:00:00Z\n",
        }
        gh = FakeGh(open_reports=[prior], created_number=101)
        result = report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review"),
            architecture=_outcome("Architecture Health Review"),
            gh=gh,
        )
        self.assertEqual(result["previous_review_boundary"], "2026-09-15T06:00:00Z")
        self.assertEqual(gh.closed, [55])
        self.assertEqual(result["closed_prior_reports"], [55])

    def test_never_closes_the_newly_created_issue_even_if_it_reappears_in_the_prior_list(self) -> None:
        # Defensive: the new issue's number must never be closed, even if a
        # caller-side race made it appear in the "prior" snapshot.
        prior = {"number": 101, "created_at": "2026-09-15T06:05:00Z", "body": ""}
        gh = FakeGh(open_reports=[prior], created_number=101)
        report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review"),
            architecture=_outcome("Architecture Health Review"),
            gh=gh,
        )
        self.assertEqual(gh.closed, [])

    def test_partial_run_records_missing_section_without_failing(self) -> None:
        gh = FakeGh(open_reports=[])
        architecture_missing = report._outcome("Architecture Health Review", "failure", "", "")
        result = report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review"),
            architecture=architecture_missing,
            gh=gh,
        )
        self.assertIn("did not complete", gh.created["body"])
        self.assertIn("Architecture Health Review", gh.created["body"])
        self.assertIn("audit_status: degraded", gh.created["body"])
        self.assertIsNotNone(result["number"])

    def test_degraded_run_names_unavailable_evidence_and_never_claims_complete(self) -> None:
        gh = FakeGh(open_reports=[])
        report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review", "skipped", "", ""),
            architecture=_outcome("Architecture Health Review", "skipped", "", ""),
            evidence_status="degraded",
            unavailable_evidence="GitHub App read token or required private repository access",
            gh=gh,
        )
        self.assertIn("audit_status: degraded", gh.created["body"])
        self.assertIn("unavailable_evidence:", gh.created["body"])
        self.assertNotIn("audit_status: complete", gh.created["body"])

    def test_degraded_run_requires_an_evidence_category(self) -> None:
        with self.assertRaisesRegex(report.PlatformHealthReportError, "must name"):
            report.publish(
                reviewed_at="2026-09-22T06:00:00Z",
                main_sha="abc123",
                process=_outcome("Process Health Review"),
                architecture=_outcome("Architecture Health Review"),
                evidence_status="degraded",
                gh=FakeGh(),
            )


class RenderSummaryTests(unittest.TestCase):
    def test_summary_is_short_and_excludes_findings_detail(self) -> None:
        summary = report.render_summary(
            title="[platform-health-review] 2026-09-22",
            process=_outcome("Process Health Review", "success"),
            architecture=_outcome("Architecture Health Review", "success"),
        )
        self.assertIn("[platform-health-review] 2026-09-22", summary)
        self.assertIn("Process Health Review: success", summary)
        self.assertIn("Architecture Health Review: success", summary)
        # Short: a handful of lines, never the full report body shape.
        self.assertLessEqual(len(summary.splitlines()), 3)

    def test_publish_result_includes_a_summary_key(self) -> None:
        gh = FakeGh(open_reports=[], created_number=101)
        result = report.publish(
            reviewed_at="2026-09-22T06:00:00Z",
            main_sha="abc123",
            process=_outcome("Process Health Review"),
            architecture=_outcome("Architecture Health Review"),
            gh=gh,
        )
        self.assertIn("summary", result)
        self.assertIn("[platform-health-review] 2026-09-22", result["summary"])


class WriteGithubOutputTests(unittest.TestCase):
    def test_writes_parseable_key_value_and_multiline_summary(self) -> None:
        with tempfile.NamedTemporaryFile(mode="r+", delete=False) as handle:
            path = handle.name
        try:
            report.write_github_output(path, number=101, url="https://x/101", summary="line one\nline two")
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("report_issue_number=101", content)
            self.assertIn("report_issue_url=https://x/101", content)
            self.assertIn("report_summary<<ghadelim_", content)
            self.assertIn("line one\nline two", content)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_appends_without_clobbering_existing_content(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
            handle.write("existing=value\n")
            path = handle.name
        try:
            report.write_github_output(path, number=1, url="https://x/1", summary="s")
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("existing=value", content)
            self.assertIn("report_issue_number=1", content)
        finally:
            Path(path).unlink(missing_ok=True)


class SplitJsonArraysTests(unittest.TestCase):
    def test_splits_multiple_paginated_arrays(self) -> None:
        stdout = '[{"a": 1}]\n[{"b": 2}, {"c": 3}]\n'
        chunks = report._split_json_arrays(stdout)
        self.assertEqual(len(chunks), 2)

    def test_empty_stdout_yields_no_chunks(self) -> None:
        self.assertEqual(report._split_json_arrays(""), [])

    def test_single_empty_array(self) -> None:
        self.assertEqual(report._split_json_arrays("[]"), ["[]"])


class OutcomeParsingTests(unittest.TestCase):
    def test_blank_issue_number_and_url_become_none(self) -> None:
        outcome = report._outcome("Process Health Review", "success", "  ", "")
        self.assertIsNone(outcome.issue_number)
        self.assertIsNone(outcome.issue_url)

    def test_result_is_stripped(self) -> None:
        outcome = report._outcome("Process Health Review", " success ", "", "")
        self.assertEqual(outcome.result, "success")


class GhClientCommandTests(unittest.TestCase):
    """Assert the exact `gh` argv built for each call, without shelling out.

    `gh api` defaults to POST the moment any `-f`/`-F` parameter is present
    (see `gh api --help`), so a read-only list call must pass `--method GET`
    explicitly or GitHub validates the request against the wrong (mutating)
    endpoint schema. This regression-guards the real failure hit in a live
    post-merge dispatch: https://github.com/lehard/dev-platform/actions/runs/35800636908
    ('For properties/labels, "platform-health-review" is not an array.
    "title" wasn't supplied. (HTTP 422)').
    """

    def _run_with_mocked_gh(self, method_name: str, *args, stdout: str = "[]") -> list[str]:
        client = report.GhClient("lehard/dev-platform")
        with patch("publish_platform_health_review_report.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = stdout
            mock_run.return_value.stderr = ""
            getattr(client, method_name)(*args)
        (called_args,), _ = mock_run.call_args
        return called_args

    def test_list_open_reports_uses_explicit_get_method(self) -> None:
        argv = self._run_with_mocked_gh("list_open_reports")
        self.assertIn("gh", argv)
        self.assertIn("--method", argv)
        self.assertEqual(argv[argv.index("--method") + 1], "GET")
        self.assertIn("--paginate", argv)

    def test_create_report_issue_defaults_to_post(self) -> None:
        argv = self._run_with_mocked_gh(
            "create_report_issue", "title", "body", stdout='{"number": 1, "html_url": "https://x/1"}'
        )
        # No explicit --method: gh api's documented default becomes POST as
        # soon as -f parameters are present, which is correct for creating
        # an issue -- this test pins that assumption so it fails loudly if
        # gh's default behavior or this call's flags ever change.
        self.assertNotIn("--method", argv)
        self.assertIn("-f", argv)

    def test_close_issue_uses_explicit_patch_method(self) -> None:
        argv = self._run_with_mocked_gh("close_issue", 7, stdout="{}")
        self.assertIn("-X", argv)
        self.assertEqual(argv[argv.index("-X") + 1], "PATCH")


if __name__ == "__main__":
    unittest.main()
