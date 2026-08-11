from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_THRESHOLD = 3
TRACKING_LABEL = "rollout-failure-streak"
ALERT_LABEL = "rollout-alert"
STATE_RE = re.compile(r"<!--\s*rollout-failure-streak-state\n(.*?)\n-->", re.DOTALL)


class TrackerError(Exception):
    """Raised when the durable tracking record cannot be created/read/updated."""


def issue_title(repository: str) -> str:
    return f"Managed rollout repeatedly failing: {repository}"


def parse_state(body: str) -> dict[str, Any] | None:
    """Extract the embedded machine state block from an issue body.

    Returns None when no block is present, or when it is present but does not
    parse/validate as this exact repository's state -- callers must treat
    both as "state unreadable", never as "no prior failures".
    """
    match = STATE_RE.search(body or "")
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if not isinstance(payload.get("repository"), str) or not isinstance(payload.get("consecutive_failures"), int):
        return None
    return payload


def render_body(state: dict[str, Any]) -> str:
    lines = [
        f"Managed rollout has failed **{state['consecutive_failures']}** consecutive attempt(s) "
        f"against `{state['repository']}`.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Consecutive failures | {state['consecutive_failures']} |",
        f"| First failed release | {state['first_failed_release']} |",
        f"| Last failed release | {state['last_failed_release']} |",
        f"| Last category | {state['last_category']} |",
        f"| Last reason | {state['last_reason']} |",
        "",
        "This issue is maintained automatically by `scripts/rollout_failure_streak.py`. "
        "It closes itself the next time this project's managed rollout preparation succeeds.",
        "",
        "<!-- rollout-failure-streak-state",
        json.dumps(state, ensure_ascii=False, sort_keys=True),
        "-->",
    ]
    return "\n".join(lines) + "\n"


def next_state_on_failure(
    prior_body: str | None,
    *,
    repository: str,
    version: str,
    category: str,
    reason: str,
    last_updated: str,
    threshold: int,
) -> tuple[dict[str, Any], bool, bool]:
    """Compute the new state after a terminal blocked attempt.

    Returns (new_state, should_alert, prior_state_was_unreadable).
    """
    prior = parse_state(prior_body) if prior_body is not None else None
    unreadable = prior_body is not None and prior is None
    if prior is not None and prior.get("repository") == repository:
        consecutive = int(prior["consecutive_failures"]) + 1
        first_failed_release = str(prior.get("first_failed_release") or version)
    elif unreadable:
        # Fail closed: an unreadable prior record is evidence of a problem,
        # not evidence of a clean history. Escalate rather than reset.
        consecutive = max(threshold, 1)
        first_failed_release = version
    else:
        consecutive = 1
        first_failed_release = version
    state = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "consecutive_failures": consecutive,
        "first_failed_release": first_failed_release,
        "last_failed_release": version,
        "last_category": category,
        "last_reason": reason,
        "last_updated": last_updated,
    }
    return state, consecutive >= threshold, unreadable


def find_tracking_issue(repository: str, tracker_repo: str) -> dict[str, Any] | None:
    result = subprocess.run(
        [
            "gh", "issue", "list",
            "--repo", tracker_repo,
            "--label", TRACKING_LABEL,
            "--state", "open",
            "--json", "number,title,body",
            "--limit", "100",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise TrackerError(f"could not list tracking issues: {result.stderr.strip() or result.returncode}")
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise TrackerError(f"could not parse tracking issue list: {exc}") from exc
    marker = f'"repository": "{repository}"'
    marker_alt = f'"repository":"{repository}"'
    for issue in issues:
        body = issue.get("body") or ""
        if issue.get("title") == issue_title(repository) or marker in body or marker_alt in body:
            return issue
    return None


def run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["gh", *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise TrackerError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip() or result.returncode}")
    return result


def cmd_record_failure(args: argparse.Namespace) -> int:
    try:
        existing = find_tracking_issue(args.repository, args.tracker_repo)
        state, alert, unreadable = next_state_on_failure(
            existing.get("body") if existing else None,
            repository=args.repository,
            version=args.version,
            category=args.category,
            reason=args.reason,
            last_updated=args.last_updated,
            threshold=args.threshold,
        )
        body = render_body(state)
        if existing is None:
            created = run_gh([
                "issue", "create",
                "--repo", args.tracker_repo,
                "--title", issue_title(args.repository),
                "--body", body,
                "--label", TRACKING_LABEL,
            ])
            issue_url = created.stdout.strip()
            number = issue_url.rstrip("/").rsplit("/", 1)[-1]
        else:
            number = str(existing["number"])
            issue_url = f"{args.tracker_repo}#{number}"
            run_gh(["issue", "edit", number, "--repo", args.tracker_repo, "--body", body])
            comment = (
                f"Rollout against `{args.repository}` failed again at `{args.version}` "
                f"(consecutive failures: {state['consecutive_failures']}).\n\n"
                f"- category: `{args.category}`\n- reason: {args.reason}"
            )
            run_gh(["issue", "comment", number, "--repo", args.tracker_repo, "--body", comment])
        if unreadable:
            print(
                f"::warning::rollout_failure_streak: prior tracking state for {args.repository} was "
                "unreadable; escalating instead of resetting the streak.",
                file=sys.stderr,
            )
        if alert:
            run_gh(["issue", "edit", number, "--repo", args.tracker_repo, "--add-label", ALERT_LABEL])
            message = (
                f"{args.repository} has failed {state['consecutive_failures']} consecutive managed rollout "
                f"attempts (since {state['first_failed_release']}). See {issue_url}."
            )
            print(f"::warning title=Repeated managed rollout failure::{message}")
            if args.summary_output:
                with open(args.summary_output, "a", encoding="utf-8") as fh:
                    fh.write(f"\n#### Repeated managed rollout failure\n\n{message}\n")
        return 0
    except Exception as exc:  # noqa: BLE001 - tracking must never fail the rollout job
        print(f"::warning::rollout_failure_streak: could not update failure tracker: {exc}", file=sys.stderr)
        return 0


def cmd_record_success(args: argparse.Namespace) -> int:
    try:
        existing = find_tracking_issue(args.repository, args.tracker_repo)
        if existing is None:
            return 0
        number = str(existing["number"])
        prior = parse_state(existing.get("body") or "")
        streak = prior.get("consecutive_failures") if prior else "unknown"
        comment = (
            f"Resolved: `{args.repository}` rollout preparation succeeded at `{args.version}` "
            f"after {streak} consecutive failure(s)."
        )
        run_gh(["issue", "comment", number, "--repo", args.tracker_repo, "--body", comment])
        run_gh(["issue", "close", number, "--repo", args.tracker_repo])
        return 0
    except Exception as exc:  # noqa: BLE001 - tracking must never fail the rollout job
        print(f"::warning::rollout_failure_streak: could not close failure tracker: {exc}", file=sys.stderr)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Track and alert on consecutive managed-rollout failures against the same project."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repository", required=True)
    common.add_argument("--version", required=True)
    common.add_argument("--tracker-repo", default="lehard/dev-platform")

    p = sub.add_parser("record-failure", parents=[common])
    p.add_argument("--category", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--last-updated", required=True)
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    p.add_argument("--summary-output", type=Path)
    p.set_defaults(func=cmd_record_failure)

    p = sub.add_parser("record-success", parents=[common])
    p.set_defaults(func=cmd_record_success)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
