#!/usr/bin/env python3
"""Publish one combined Platform Health Review report Issue per run.

This is a plain, non-agentic aggregation step for the `platform-health-review`
capability (openspec/specs/platform-health-review/spec.md). It runs as a
deterministic Actions step, `needs:` both of the review jobs declared in
`.github/workflows/platform-health-review.yml` with `if: always()`, so it
still runs -- and still records the gap -- when one review job failed or was
skipped.

It does not re-run, re-evaluate, or change either review's own findings. It
only reads each review's already-published `create-issue` safe-output result
(job `result` plus `created_issue_number`/`created_issue_url` outputs exposed
by each review's compiled `workflow_call` lock file) and composes exactly one
dated, human-readable combined report Issue, reusing the same
title-prefix + close-older-issues replace-not-accumulate shape already
accepted for each individual review's own report. Because this step is plain
GitHub Actions rather than a gh-aw safe output, the search-and-close-prior
logic below is this script's own implementation of that same semantic.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass


TITLE_PREFIX = "[platform-health-review] "
REPORT_LABEL = "platform-health-review"
REPORT_LABEL_COLOR = "5319e7"
REPORT_LABEL_DESCRIPTION = "Combined Platform Health Review report (process + architecture)"

_REVIEWED_AT_RE = re.compile(r"^- reviewed_at:\s*(\S+)\s*$", re.MULTILINE)
_DATE_ONLY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class PlatformHealthReportError(RuntimeError):
    """Raised when the combined report cannot be published."""


@dataclass(frozen=True)
class ReviewOutcome:
    name: str
    result: str
    issue_number: str | None
    issue_url: str | None


class GhClient:
    """Thin wrapper around the `gh` CLI used for the combined report.

    Kept small and injectable so tests can supply a fake instead of shelling
    out to a real `gh` binary / live GitHub API.
    """

    def __init__(self, repo: str) -> None:
        self.repo = repo

    def _run(self, args: list[str]) -> str:
        result = subprocess.run(["gh", *args], text=True, capture_output=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise PlatformHealthReportError(f"`gh {' '.join(args)}` failed: {detail}")
        return result.stdout

    def ensure_label(self) -> None:
        self._run(
            [
                "label",
                "create",
                REPORT_LABEL,
                "--repo",
                self.repo,
                "--color",
                REPORT_LABEL_COLOR,
                "--description",
                REPORT_LABEL_DESCRIPTION,
                "--force",
            ]
        )

    def list_open_reports(self) -> list[dict]:
        stdout = self._run(
            [
                "api",
                f"repos/{self.repo}/issues",
                "--method",
                "GET",
                "--paginate",
                "-f",
                "state=open",
                "-f",
                f"labels={REPORT_LABEL}",
                "-f",
                "per_page=100",
            ]
        )
        # `--paginate` concatenates one JSON array per page; join truthy pages.
        pages = [json.loads(chunk) for chunk in _split_json_arrays(stdout)]
        issues: list[dict] = []
        for page in pages:
            issues.extend(page)
        return [issue for issue in issues if str(issue.get("title", "")).startswith(TITLE_PREFIX)]

    def create_report_issue(self, title: str, body: str) -> dict:
        stdout = self._run(
            [
                "api",
                f"repos/{self.repo}/issues",
                "-f",
                f"title={title}",
                "-f",
                f"body={body}",
                "-f",
                f"labels[]={REPORT_LABEL}",
            ]
        )
        return json.loads(stdout)

    def close_issue(self, number: int) -> None:
        self._run(
            [
                "api",
                f"repos/{self.repo}/issues/{number}",
                "-X",
                "PATCH",
                "-f",
                "state=closed",
                "-f",
                "state_reason=not_planned",
            ]
        )


def _split_json_arrays(stdout: str) -> list[str]:
    """Split `gh api --paginate` stdout into one string per JSON array page."""
    text = stdout.strip()
    if not text:
        return []
    chunks: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == "[":
            if depth == 0:
                start = index
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                chunks.append(text[start : index + 1])
    return chunks


def render_section(outcome: ReviewOutcome) -> str:
    if outcome.result == "success":
        if outcome.issue_number:
            url_suffix = f" ({outcome.issue_url})" if outcome.issue_url else ""
            return f"**{outcome.name}: ran.** See #{outcome.issue_number}{url_suffix} for the full report."
        return (
            f"**{outcome.name}: ran but did not produce a report issue** for this run "
            "(no findings issue was created by its safe output)."
        )
    if outcome.result == "skipped":
        return f"**{outcome.name}: did not run** for this trigger (job skipped)."
    if outcome.result in ("failure", "cancelled"):
        return f"**{outcome.name}: did not complete** for this run (result: {outcome.result}); no report was produced."
    return f"**{outcome.name}: reported an unrecognized job result** ({outcome.result!r}); no report was produced."


def extract_reviewed_at(body: str) -> str | None:
    match = _REVIEWED_AT_RE.search(body or "")
    return match.group(1) if match else None


def previous_boundary(prior_reports: list[dict]) -> str:
    """Return the `reviewed_at` of the most recently created prior report, or "none"."""
    dated = [
        (report.get("created_at", ""), extract_reviewed_at(str(report.get("body", ""))))
        for report in prior_reports
    ]
    dated = [(created_at, reviewed_at) for created_at, reviewed_at in dated if reviewed_at]
    if not dated:
        return "none"
    dated.sort(key=lambda pair: pair[0])
    return dated[-1][1]


def report_title(reviewed_at: str) -> str:
    match = _DATE_ONLY_RE.match(reviewed_at)
    date_part = match.group(1) if match else reviewed_at
    return f"{TITLE_PREFIX}{date_part}"


def render_body(
    *,
    reviewed_at: str,
    main_sha: str,
    boundary: str,
    process_section: str,
    architecture_section: str,
) -> str:
    return (
        "# Platform Health Review\n\n"
        f"- reviewed_at: {reviewed_at}\n"
        f"- main_sha: {main_sha}\n"
        f"- previous_review_boundary: {boundary}\n\n"
        "## Process Health Review\n\n"
        f"{process_section}\n\n"
        "## Architecture Health Review\n\n"
        f"{architecture_section}\n\n"
        "---\n"
        "This is an aggregated, advisory report generated by "
        "`scripts/publish_platform_health_review_report.py`. It performs no "
        "source-issue mutation beyond linking to each review's own report and "
        "closing the prior combined report under this same title prefix. It "
        "does not change what either review evaluates.\n"
    )


def render_summary(*, title: str, process: ReviewOutcome, architecture: ReviewOutcome) -> str:
    """Render the short (few-line) summary used for external notification.

    This is deliberately not the full report body: it names the report and
    each review's high-level result only, never findings detail. See
    `openspec/specs/platform-health-review/spec.md`.
    """
    return (
        f"{title}\n"
        f"Process Health Review: {process.result}. "
        f"Architecture Health Review: {architecture.result}."
    )


def publish(
    *,
    reviewed_at: str,
    main_sha: str,
    process: ReviewOutcome,
    architecture: ReviewOutcome,
    gh: GhClient,
) -> dict:
    gh.ensure_label()
    prior_reports = gh.list_open_reports()
    boundary = previous_boundary(prior_reports)
    body = render_body(
        reviewed_at=reviewed_at,
        main_sha=main_sha,
        boundary=boundary,
        process_section=render_section(process),
        architecture_section=render_section(architecture),
    )
    title = report_title(reviewed_at)
    created = gh.create_report_issue(title, body)
    new_number = created.get("number")
    for report in prior_reports:
        number = report.get("number")
        if number is not None and number != new_number:
            gh.close_issue(int(number))
    return {
        "title": title,
        "number": new_number,
        "url": created.get("html_url"),
        "previous_review_boundary": boundary,
        "closed_prior_reports": [r.get("number") for r in prior_reports if r.get("number") != new_number],
        "summary": render_summary(title=title, process=process, architecture=architecture),
    }


def write_github_output(path: str, *, number: object, url: object, summary: str) -> None:
    """Append this run's report identity as GitHub Actions step outputs.

    Consumed by the notification job (`openspec/specs/platform-health-review/spec.md`)
    so that a later, separate, non-agentic step can send a short summary + link without
    re-reading or re-deriving the report. Uses the standard multiline-value
    delimiter form for `summary`, since it may contain newlines.
    """
    delimiter = f"ghadelim_{uuid.uuid4().hex}"
    lines = [
        f"report_issue_number={number if number is not None else ''}",
        f"report_issue_url={url if url is not None else ''}",
        f"report_summary<<{delimiter}",
        summary,
        delimiter,
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _outcome(name: str, result: str, issue_number: str, issue_url: str) -> ReviewOutcome:
    number = issue_number.strip() if issue_number else ""
    url = issue_url.strip() if issue_url else ""
    return ReviewOutcome(name=name, result=result.strip(), issue_number=number or None, issue_url=url or None)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/repo, e.g. lehard/dev-platform")
    parser.add_argument("--reviewed-at", required=True, help="ISO-8601 UTC timestamp for this combined run")
    parser.add_argument("--main-sha", required=True, help="exact default-branch commit SHA for this run")
    parser.add_argument("--process-result", required=True, help="needs.<process job>.result")
    parser.add_argument("--process-issue-number", default="")
    parser.add_argument("--process-issue-url", default="")
    parser.add_argument("--architecture-result", required=True, help="needs.<architecture job>.result")
    parser.add_argument("--architecture-issue-number", default="")
    parser.add_argument("--architecture-issue-url", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    process = _outcome(
        "Process Health Review", args.process_result, args.process_issue_number, args.process_issue_url
    )
    architecture = _outcome(
        "Architecture Health Review",
        args.architecture_result,
        args.architecture_issue_number,
        args.architecture_issue_url,
    )
    gh = GhClient(args.repo)
    try:
        result = publish(
            reviewed_at=args.reviewed_at,
            main_sha=args.main_sha,
            process=process,
            architecture=architecture,
            gh=gh,
        )
    except PlatformHealthReportError as exc:
        print(f"error: {exc}", flush=True)
        return 1
    print(f"Published combined Platform Health Review report: {result['title']} (#{result['number']})")
    print(f"  url: {result['url']}")
    print(f"  previous_review_boundary: {result['previous_review_boundary']}")
    if result["closed_prior_reports"]:
        print(f"  closed prior report(s): {result['closed_prior_reports']}")
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if github_output_path:
        write_github_output(
            github_output_path,
            number=result["number"],
            url=result["url"],
            summary=result["summary"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
