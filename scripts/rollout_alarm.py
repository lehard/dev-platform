from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from rollout_failure_streak import ALERT_LABEL, TrackerError, ensure_label

PLAN_JOB = "plan"
TARGET_SEPARATOR = " -> "
FAILURE_ANNOTATION_LEVEL = "failure"
MAX_ERROR_CHARS = 1000


class AlarmError(Exception):
    """Raised when the run cannot be read or the alarm cannot be delivered."""


def run_gh(args: list[str]) -> str:
    result = subprocess.run(["gh", *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AlarmError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip() or result.returncode}")
    return result.stdout


def json_lines(text: str, what: str) -> list[dict[str, Any]]:
    items = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AlarmError(f"could not parse {what}: {exc}") from exc
        if not isinstance(item, dict):
            raise AlarmError(f"could not parse {what}: expected an object, got {type(item).__name__}")
        items.append(item)
    return items


def alarm_title(tag: str) -> str:
    return f"Managed rollout failed: {tag}"


def release_tag(planned: str, requested: str, version_file: Path) -> str:
    """Name the release exactly as the plan job resolves it."""
    if planned:
        return planned
    if requested:
        return requested
    version = version_file.read_text(encoding="utf-8").strip()
    if not version:
        raise AlarmError(f"{version_file} is empty; cannot name the requested release")
    return f"v{version}"


def run_jobs(repository: str, run_id: str, attempt: str) -> list[dict[str, Any]]:
    text = run_gh([
        "api", "--paginate",
        f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs",
        "--jq", ".jobs[]",
    ])
    jobs = json_lines(text, "run jobs")
    if not jobs:
        raise AlarmError(f"run {run_id} attempt {attempt} reports no jobs")
    return jobs


def failure_messages(repository: str, job_id: int) -> list[str]:
    text = run_gh(["api", "--paginate", f"repos/{repository}/check-runs/{job_id}/annotations", "--jq", ".[]"])
    messages: list[str] = []
    for annotation in json_lines(text, f"annotations of job {job_id}"):
        if annotation.get("annotation_level") != FAILURE_ANNOTATION_LEVEL:
            continue
        message = " ".join(str(annotation.get("message") or "").split())
        if message and message not in messages:
            messages.append(message[:MAX_ERROR_CHARS])
    return messages


def failed_jobs(jobs: list[dict[str, Any]], alarm_job: str) -> list[dict[str, Any]]:
    """Every job of this attempt that did not succeed, except the alarm job itself.

    A skipped job is a failure unless the plan job failed: then the matrix never
    expanded and the plan failure is what is reported.
    """
    own = [job for job in jobs if job.get("name") != alarm_job]
    plan = [job for job in own if job.get("name") == PLAN_JOB]
    if len(plan) != 1:
        raise AlarmError(f"expected exactly one '{PLAN_JOB}' job in the run, found {len(plan)}")
    plan_succeeded = plan[0].get("conclusion") == "success"
    failed = []
    for job in own:
        conclusion = job.get("conclusion")
        if conclusion == "success":
            continue
        if conclusion == "skipped" and not plan_succeeded:
            continue
        failed.append(job)
    return failed


def describe_failure(repository: str, job: dict[str, Any]) -> dict[str, str]:
    name = str(job.get("name"))
    stage = name.split(TARGET_SEPARATOR, 1)[0] if TARGET_SEPARATOR in name else name
    steps = [step for step in job.get("steps") or [] if step.get("conclusion") == "failure"]
    conclusion = job.get("conclusion") or "not finished"
    step = steps[0]["name"] if steps else f"no failed step recorded (job {conclusion})"
    messages = failure_messages(repository, int(job["id"]))
    if messages:
        error = "; ".join(messages)
    else:
        error = f"no error annotation was recorded; see the job log {job.get('html_url')}"
    return {"stage": stage, "step": step, "error": error, "conclusion": str(conclusion)}


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_report(tag: str, failures: list[dict[str, str]], context: dict[str, str]) -> str:
    lines = [
        f"Managed rollout of **{tag}** failed in run [{context['run_id']}]({context['run_url']}) "
        f"(attempt {context['attempt']}).",
        "",
        f"- event: `{context['event']}`, triggered by `{context['actor']}`",
        f"- requested scope: {context['scope']}",
        "",
        "| Stage or target | Failed step | Error |",
        "| --- | --- | --- |",
    ]
    for failure in failures:
        lines.append(f"| `{cell(failure['stage'])}` | {cell(failure['step'])} | {cell(failure['error'])} |")
    lines += [
        "",
        "No rollout PR exists for the failed targets until the failure is fixed and rollout is dispatched again. "
        "This alarm is maintained by `scripts/rollout_alarm.py`; close it once every listed target is delivered.",
    ]
    return "\n".join(lines) + "\n"


def open_alarm(repository: str, tag: str) -> dict[str, Any] | None:
    text = run_gh([
        "issue", "list", "--repo", repository, "--label", ALERT_LABEL, "--state", "open",
        "--json", "number,title", "--limit", "100",
    ])
    try:
        issues = json.loads(text or "[]")
    except json.JSONDecodeError as exc:
        raise AlarmError(f"could not parse open alarm list: {exc}") from exc
    matches = [issue for issue in issues if issue.get("title") == alarm_title(tag)]
    if len(matches) > 1:
        raise AlarmError(f"more than one open alarm for {tag}: {[issue.get('number') for issue in matches]}")
    return matches[0] if matches else None


def write_summary(path: Path | None, text: str) -> None:
    if path is not None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)


def cmd_report(args: argparse.Namespace) -> int:
    tag = release_tag(args.planned_version, args.requested_version, args.version_file)
    jobs = run_jobs(args.repository, args.run_id, args.run_attempt)
    failures = [describe_failure(args.repository, job) for job in failed_jobs(jobs, args.alarm_job)]
    context = {
        "run_id": args.run_id,
        "attempt": args.run_attempt,
        "run_url": f"{args.server_url}/{args.repository}/actions/runs/{args.run_id}",
        "event": args.event,
        "actor": args.actor,
        "scope": f"`{args.requested_repository}`" if args.requested_repository else "all managed projects",
    }
    if not failures:
        existing = open_alarm(args.repository, tag)
        if existing is not None:
            number = str(existing["number"])
            run_gh([
                "issue", "comment", number, "--repo", args.repository, "--body",
                f"Run [{args.run_id}]({context['run_url']}) (attempt {args.run_attempt}) succeeded for "
                f"{context['scope']}. This alarm stays open until every listed target is delivered.",
            ])
            print(f"rollout_alarm: {tag} run {args.run_id} succeeded; noted on open alarm #{number}")
        else:
            print(f"rollout_alarm: {tag} run {args.run_id} succeeded; no alarm")
        return 0
    report = render_report(tag, failures, context)
    ensure_label(args.repository, ALERT_LABEL)
    existing = open_alarm(args.repository, tag)
    if existing is None:
        url = run_gh([
            "issue", "create", "--repo", args.repository, "--title", alarm_title(tag),
            "--body", report, "--label", ALERT_LABEL,
        ]).strip()
    else:
        number = str(existing["number"])
        run_gh(["issue", "comment", number, "--repo", args.repository, "--body", report])
        url = f"{args.repository}#{number}"
    stages = ", ".join(failure["stage"] for failure in failures)
    print(f"::error title=Managed rollout failed::{tag} failed for {stages}; alarm: {url}")
    write_summary(args.summary_output, f"\n#### Managed rollout alarm\n\nAlarm: {url}\n\n{report}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Raise one explicit alarm per release when a managed rollout run has a failed job."
    )
    parser.add_argument("--repository", required=True, help="platform repository owner/name (run and alarm)")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--alarm-job", required=True, help="name of the job running this script")
    parser.add_argument("--planned-version", required=True, help="plan job output; empty when plan did not resolve it")
    parser.add_argument("--requested-version", required=True, help="workflow 'version' input; may be empty")
    parser.add_argument("--requested-repository", required=True, help="workflow 'repository' input; may be empty")
    parser.add_argument("--version-file", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    for name in ("repository", "run_id", "run_attempt", "server_url", "event", "actor", "alarm_job"):
        if not getattr(args, name):
            parser.error(f"--{name.replace('_', '-')} must not be empty")
    try:
        return cmd_report(args)
    except (AlarmError, TrackerError, OSError) as exc:
        print(f"::error title=Managed rollout alarm not delivered::rollout_alarm failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
