#!/usr/bin/env python3
"""Read-only lifecycle overview for the chat coordinator role.

Projects what GitHub already records (PR heads, checks, versioned lifecycle
markers, claim and result receipts, Requirement Issues and Project statuses)
into human-facing delivery stages, the review -> ... -> cleanup chain, named
exception findings and the operator actions the supported commands would
accept. It writes nothing, keeps no cache and no state store, and reports
``unknown`` for any source it cannot read instead of presenting it as healthy.
See ``docs/engineering/chat-coordinator.md``.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any

from _platform_common import current_worktree_root, read_platform_config

STAGES = ("in-development", "handed-off", "delivering", "merged-open-obligations", "closed", "needs-intervention", "unknown")
CHAIN = ("review", "repair", "re-review", "finalize", "integration", "retrospective", "terminal-reconciliation", "cleanup")
SETTING = "unclaimed_job_after_minutes"
SECTION = "chat_coordinator"
INTEGRATION_STATES = frozenset({"ready", "integrating", "integration-repair-pending",
                                "contribution-integration-pending", "contribution-integrated"})
REVIEW_STATES = frozenset({"review-pending", "reviewing"})
REPAIR_STATES = frozenset({"repair-pending", "repairing"})
# What a human may do about findings that no operator command resolves; never a substitute action.
FINDING_HINTS = {
    "unclaimed-next-job": "No operator command applies: a lifecycle worker (hosted run or local node) has to claim the job; check that workers are running.",
    "expired-claim": "No operator command applies: the claim expired, so any lifecycle worker may claim the job again; check that workers are running.",
    "stale-head": "Nothing to decide: the candidate is re-evaluated for its current head.",
    "post-merge-exhausted": "No supported re-offer command exists for a post-merge step; fix the cause named in the reason.",
    "provider-unavailable": "The automatic retry continues once the provider is available; switch-provider is listed when it applies.",
}
CLAIM_FINDINGS = frozenset({"unclaimed-next-job", "expired-claim"})
EXECUTOR_NOT_CONFIRMED = "executor not confirmed"
ACTIVITY_NOT_CONFIRMED = "executor activity: not confirmed"
READ_PARALLELISM = 8
BR_BRANCH = re.compile(r"(?:^|/)br-([0-9]+)(?:-|$)", re.IGNORECASE)


class OverviewError(RuntimeError):
    pass


def unclaimed_threshold_minutes(root: Path) -> int:
    """The required unclaimed-job threshold; a missing or invalid setting fails, never defaults."""
    section = read_platform_config(root).get(SECTION)
    value = section.get(SETTING) if isinstance(section, dict) else None
    if type(value) is not int or value <= 0:
        raise OverviewError(f"[{SECTION}] {SETTING} in .dev-platform.toml must be a positive integer (minutes); "
                            "it is required and has no default")
    return value


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _pr_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/pull/{number}"


def _comment_url(repo: str, number: int, comment_id: Any) -> str:
    return f"{_pr_url(repo, number)}#issuecomment-{comment_id}"


def _current_step(candidate: dict) -> str | None:
    """The chain step the candidate is at, or ``None`` when every step is complete."""
    from candidate_lifecycle import POST_MERGE_KINDS
    from lifecycle_workers import STATE_KIND

    state, attempts = candidate["state"], candidate.get("attempts") or {}
    red = (candidate.get("red_gate") or {}).get("name")
    job_kind = (candidate.get("next_job") or {}).get("kind") if isinstance(candidate.get("next_job"), dict) else None
    if state == "merged":
        return job_kind if job_kind in POST_MERGE_KINDS else None
    if state in REVIEW_STATES:
        return "re-review" if attempts.get("repair", 0) > 0 else "review"
    if state in REPAIR_STATES:
        return "repair"
    if state == "finalize-pending":
        return "finalize"
    if state in INTEGRATION_STATES:
        return "integration"
    kind = {"review": "re-review" if attempts.get("repair", 0) > 0 else "review", "repair": "repair",
            "finalize": "finalize", "required-checks": "integration", "integration": "integration"}.get(red)
    return kind or {"review": "review", "repair": "repair", "finalize": "finalize"}.get(job_kind or STATE_KIND.get(state, ""))


def stage_chain(candidate: dict) -> list[dict]:
    """The review -> ... -> cleanup chain with the step reached, derived from the record's state and counters."""
    current = _current_step(candidate)
    attempts = candidate.get("attempts") or {}
    position = CHAIN.index(current) if current in CHAIN else len(CHAIN)
    chain = []
    for index, step in enumerate(CHAIN):
        if step in {"repair", "re-review"} and attempts.get("repair", 0) == 0 and step != current:
            status = "not-needed" if index < position else "pending"
        elif index < position:
            status = "done"
        elif index == position:
            status = "current"
        else:
            status = "pending"
        chain.append({"step": step, "status": status})
    return chain


def _results(comments: list[dict], apps: frozenset[str], writers: frozenset[str]) -> list[dict]:
    from candidate_lifecycle import trusted_marker_comment
    from lifecycle_workers import RESULT_PREFIX

    found = []
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body")
        if not isinstance(body, str) or not body.startswith(RESULT_PREFIX) or not trusted_marker_comment(row, apps, writers):
            continue
        try:
            record = json.loads(body[len(RESULT_PREFIX):])
        except ValueError:
            continue
        if isinstance(record, dict):
            found.append({**record, "comment_id": row.get("id")})
    return found


def assess_candidate(candidate: dict, pr: dict, comments: list[dict], *, repo: str, apps: frozenset[str],
                     writers: frozenset[str], now: datetime, threshold_minutes: int) -> dict:
    """Pure assessment of one derived candidate: stage, chain, executor, findings and permitted actions."""
    from candidate_lifecycle import POST_MERGE_FLAG
    from lifecycle_workers import build_job, job_completed, latest_claim, winning_claim
    from pr_review_gate import OPERATIONAL_REPAIR_OUTCOMES, _repair_status, permitted_actions
    from publication_queue import retry_job_kind

    number, head, state = candidate["number"], candidate["head"], candidate["state"]
    url = _pr_url(repo, number)
    merged = bool(pr.get("merged") or pr.get("merged_at") or pr.get("mergedAt"))
    reason = str(candidate.get("reason") or "")
    red = candidate.get("red_gate") or {}
    attempts = candidate.get("attempts") or {}
    findings: list[dict] = []

    def find(kind: str, detail: str, evidence: str) -> None:
        findings.append({"kind": kind, "detail": detail, "evidence": evidence})

    job = build_job(candidate)
    trust = {"trusted_apps": apps, "trusted_writers": writers}
    winning = winning_claim(job, comments, now=now, **trust) if job else None
    last = latest_claim(job, comments, **trust) if job else None
    completed = job_completed(job, comments, **trust) if job else False
    if winning:
        executor = {"claimed_by": winning["worker"], "provider": winning.get("provider"),
                    "claim_expires_at": winning["expires_at"], "activity": ACTIVITY_NOT_CONFIRMED,
                    "evidence": _comment_url(repo, number, winning.get("comment_id"))}
    else:
        executor = {"claimed_by": None, "activity": EXECUTOR_NOT_CONFIRMED}

    if reason.startswith("malformed marker"):
        find("unknown-source", reason, url)
    elif state == "blocked-escalation":
        status = _repair_status(red) if red.get("name") == "repair" else None
        operational = red.get("name") == "finalize" or (red.get("name") == "repair" and status in OPERATIONAL_REPAIR_OUTCOMES)
        if red.get("name") in {"repair", "review"} and not operational:
            find("escalated-finding", reason or f"{red.get('name')} escalated for a finding-level reason ({status or 'review'})",
                 f"{url} ({red.get('name')} gate evidence in the latest lifecycle record)")
        elif operational:
            find("escalated-operational", reason or f"{red.get('name')} escalated for an operational reason ({status or 'finalize'})",
                 f"{url} ({red.get('name')} gate evidence in the latest lifecycle record)")
        else:
            find("escalated-other", reason or "blocked by the coordinator", url)
    if merged and reason.startswith("post-merge") and "exhausted" in reason:
        find("post-merge-exhausted", reason, url)
    if state == "blocked-retryable" and retry_job_kind(candidate):
        evidence = ((candidate.get("gates") or {}).get("repair") or {}).get("evidence")
        limitation = (evidence.get("limitation") if isinstance(evidence, dict) else None) or reason or "provider unavailable"
        find("provider-unavailable", f"providers {(job or {}).get('providers') or (evidence or {}).get('providers')}: {limitation}", url)
    unavailable = [r for r in _results(comments, apps, writers)
                   if r.get("head") == head and str(r.get("outcome", "")).startswith("unavailable")]
    if unavailable and not completed and not winning and not any(f["kind"] == "provider-unavailable" for f in findings):
        find("provider-unavailable", f"provider {unavailable[-1].get('provider')}: {unavailable[-1]['outcome']}",
             _comment_url(repo, number, unavailable[-1].get("comment_id")))
    if reason.startswith(("claim recorded on earlier head", "checks do not match candidate head")):
        find("stale-head", f"{reason}; a result bound to another head is discarded, not applied", url)
    age_minutes = None
    if job and not completed and not winning:
        if last is not None:
            find("expired-claim", f"claim by {last['worker']} (provider {last.get('provider')}) expired at {last['expires_at']} "
                 "without a completing result", _comment_url(repo, number, last.get("comment_id")))
        else:
            recorded = _parse_time(candidate.get("at"))
            if recorded is None:
                find("unknown-source", "the age of the published job cannot be determined (no timestamp in the record)", url)
            else:
                age_minutes = int((now - recorded).total_seconds() // 60)
                if age_minutes > threshold_minutes:
                    find("unclaimed-next-job", f"{job['kind']} job published {age_minutes} min ago has no claim "
                         f"(threshold {threshold_minutes} min)", f"{url} (record at {candidate.get('at')})")
    if job and age_minutes is not None:
        executor["job_age_minutes"] = age_minutes

    if any(f["kind"] == "unknown-source" for f in findings):
        stage = "unknown"
    elif findings:
        stage = "needs-intervention"
    elif merged or state == "merged":
        # a merged contribution still awaits its Requirement's composition
        stage = "merged-open-obligations" if candidate.get("next_job") or state.startswith("contribution") else "closed"
    elif state == "review-pending" and not winning and not candidate.get("gates") and not attempts.get("repair"):
        stage = "handed-off"
    else:
        stage = "delivering"

    open_pr = pr.get("state") == "open" and not merged
    plan = (permitted_actions(candidate, winning, number=number, retry_kind=retry_job_kind(candidate),
                              job_completed=completed)
            if open_pr else {"actions": [], "human_decision": None})
    if stage == "needs-intervention" and not plan["human_decision"]:
        hints = list(dict.fromkeys(FINDING_HINTS[f["kind"]] for f in findings if f["kind"] in FINDING_HINTS))
        if hints:
            plan = {**plan, "human_decision": " ".join(hints)}
        elif not plan["actions"]:
            plan = {**plan, "human_decision": reason or "A human decision is needed; no supported recovery command applies."}
    next_action = candidate.get("next_action")
    if isinstance(next_action, dict):
        next_action = f"{next_action.get('kind')} job (attempt {next_action.get('attempt')})"
    overdue = bool(findings) and all(f["kind"] in CLAIM_FINDINGS for f in findings)
    if stage == "needs-intervention" and not overdue:
        expected = "none: intervention required"
    elif overdue:
        expected = f"overdue: a lifecycle worker should claim the {job['kind']} job"
    elif state in INTEGRATION_STATES:
        expected = "publication coordinator integration"
    elif job and winning:
        expected = f"{job['kind']} job claimed by {winning['worker']} until {winning['expires_at']}"
    elif job:
        expected = f"a lifecycle worker to claim the {job['kind']} job"
    else:
        expected = "none scheduled"
    return {"number": number, "url": url, "head": head, "state": state, "stage": stage, "reason": reason,
            "post_merge_tracked": bool(attempts.get(POST_MERGE_FLAG)),
            "attempts": attempts, "chain": stage_chain(candidate),
            "job": ({"kind": job["kind"], "attempt": job["attempt"], "providers": job.get("providers")} if job else None),
            "executor": executor, "findings": findings, "actions": plan["actions"],
            "human_decision": plan["human_decision"], "next_operation": next_action,
            "expected_automation": expected, "merged": merged,
            "branch": (pr.get("head") or {}).get("ref")}


def assess_requirement(requirement: str, aggregate: dict | None, error: str | None, candidates: list[dict]) -> dict:
    """Requirement-level stage from its read-through progress and its candidates' assessments."""
    if error is not None or aggregate is None:
        return {"requirement": requirement, "stage": "unknown", "status": None, "progress": None,
                "findings": [{"kind": "unknown-source", "detail": error or "Requirement progress is unavailable",
                              "evidence": requirement}], "candidates": [c["number"] for c in candidates]}
    status, progress = aggregate.get("status"), aggregate.get("progress") or {}
    stages = {c["stage"] for c in candidates}
    note = None
    sources = {d.get("source") for d in progress.get("diagnostics") or []}
    if status == "pre-authoring" and progress.get("stage") == "unknown" and sources == {"orchestrator"}:
        # No linked child and no pre-authoring state in this checkout (that state is machine-local):
        # the Requirement has not produced a technical child that this view can see.
        stage, note = "in-development", "no linked child; pre-authoring state is machine-local and not visible from this checkout"
    elif status == "Done":
        stage = "closed"
    elif progress.get("stage") == "unknown" or status == "unknown":
        stage = "unknown"
    elif progress.get("stage") == "blocked" or status == "Blocked" or "needs-intervention" in stages:
        stage = "needs-intervention"
    elif "unknown" in stages:
        stage = "unknown"
    elif candidates and stages <= {"merged-open-obligations", "closed"}:
        stage = "merged-open-obligations"  # merged delivery, but the Requirement is not Done yet
    elif candidates and "delivering" in stages:
        stage = "delivering"
    elif candidates:
        stage = "handed-off"
    else:
        stage = "in-development"
    return {"requirement": requirement, "stage": stage, "status": status, "progress": progress, "note": note,
            "merged_not_done": stage == "merged-open-obligations", "findings": [],
            "candidates": [c["number"] for c in candidates]}


# ---- GitHub observation (read-only) ----------------------------------------------------------

def _has_lifecycle_record(comments: list[dict], apps: frozenset[str], writers: frozenset[str]) -> bool:
    from candidate_lifecycle import PREFIX, V1_PREFIX, trusted_marker_comment

    return any(isinstance(row.get("body"), str) and row["body"].startswith((PREFIX, V1_PREFIX))
               and trusted_marker_comment(row, apps, writers) for row in comments)


def observe_candidate(root: Path, repo: str, pr: dict, *, now: datetime, threshold: int) -> dict | None:
    """Assess one PR from live GitHub state; ``None`` when it carries no lifecycle record."""
    import publication_queue as queue
    from candidate_lifecycle import MalformedMarkerError
    from lifecycle_workers import CLAIM_PREFIX, RESULT_PREFIX

    number = pr["number"]
    try:
        comments = queue._comments(root, repo, number)
        apps = queue.trusted_apps(root)
        writers = queue.trusted_writers(root, comments, (CLAIM_PREFIX, RESULT_PREFIX), repo=repo)
        if not _has_lifecycle_record(comments, apps, writers):
            return None
        merged = bool(pr.get("merged") or pr.get("merged_at"))
        candidate = queue.candidate_from_snapshot(root, repo, pr, comments, None)
        if not merged and candidate["state"] in {"ready", "integrating", "contribution-integration-pending"}:
            checks = queue.observe_checks(root, number, pr["head"]["sha"])
            candidate = queue.candidate_from_snapshot(root, repo, pr, comments, checks)
        return assess_candidate(candidate, pr, comments, repo=repo, apps=apps, writers=writers, now=now,
                                threshold_minutes=threshold)
    except (queue.QueueError, MalformedMarkerError, ValueError) as exc:
        return {"number": number, "url": _pr_url(repo, number), "head": (pr.get("head") or {}).get("sha"),
                "state": None, "stage": "unknown", "reason": str(exc), "chain": [], "attempts": {}, "job": None,
                "executor": {"claimed_by": None, "activity": EXECUTOR_NOT_CONFIRMED},
                "findings": [{"kind": "unknown-source", "detail": f"lifecycle state of PR #{number} is unreadable: {exc}",
                              "evidence": _pr_url(repo, number)}],
                "actions": [], "human_decision": None, "next_operation": None, "expected_automation": "unknown",
                "merged": bool(pr.get("merged")), "branch": (pr.get("head") or {}).get("ref")}


def _observe_requirement(root: Path, requirement: str, candidates: list[dict]) -> dict:
    import requirement_intake as intake

    try:
        aggregate = intake.aggregate(root, requirement=requirement)
        return assess_requirement(requirement, aggregate, None, candidates)
    except (intake.RequirementIntakeError, OSError) as exc:
        return assess_requirement(requirement, None, str(exc), candidates)


def _backlog_repository(root: Path) -> str:
    section = read_platform_config(root).get("development_backlog")
    value = section.get("repository") if isinstance(section, dict) else None
    if not isinstance(value, str) or "/" not in value:
        raise OverviewError("[development_backlog] repository in .dev-platform.toml must name the Backlog repository (owner/name)")
    return value


def _open_requirements(root: Path, backlog: str) -> list[str]:
    import publication_queue as queue

    rows = queue._gh(root, "api", "--paginate", f"repos/{backlog}/issues?state=open&labels=type%3Arequirement&per_page=100")
    if not isinstance(rows, list):
        raise OverviewError(f"open Requirements of {backlog} could not be listed")
    return [f"{backlog}#{row['number']}" for row in rows if isinstance(row, dict) and "pull_request" not in row]


def _requirement_of(assessment: dict) -> str | None:
    match = BR_BRANCH.search(assessment.get("branch") or "")
    return match.group(1) if match else None


def overview(root: Path, *, now: datetime) -> dict:
    """Summary of every candidate the workers consider and every open Requirement."""
    import publication_queue as queue
    from lifecycle_workers import MERGED_DISCOVERY_PAGE, candidate_prs
    from managed_work_identity import parent_identity

    threshold = unclaimed_threshold_minutes(root)
    repo = queue._repo(root)
    backlog = _backlog_repository(root)
    prs = candidate_prs(repo, include_merged=True, gh_json=lambda *args: queue._gh(root, *args))
    with ThreadPoolExecutor(max_workers=READ_PARALLELISM) as pool:  # independent read-only GitHub observations
        observed = list(pool.map(lambda pr: observe_candidate(root, repo, pr, now=now, threshold=threshold), prs))
        assessed = [item for item in observed if item is not None]
        without_record = len(observed) - len(assessed)
        listed = _open_requirements(root, backlog)
        requirements = list(pool.map(
            lambda requirement: _observe_requirement(root, requirement, [
                item for item in assessed if _requirement_of(item) == parent_identity(requirement).split("-")[-1]]),
            listed))
    claimed = {n for r in requirements for n in r["candidates"]}
    return {"repository": repo, "backlog": backlog, "generated_at": now.isoformat(timespec="seconds"),
            "bounds": {"merged_discovery_page": MERGED_DISCOVERY_PAGE,
                       "note": "open PRs plus the most recently updated closed merged PRs, exactly the workers' candidate set",
                       "prs_without_lifecycle_record": without_record, "unclaimed_job_after_minutes": threshold},
            "requirements": requirements,
            "candidates": assessed,
            "unlinked_candidates": [item["number"] for item in assessed if item["number"] not in claimed]}


def show_pr(root: Path, number: int, *, now: datetime) -> dict:
    import publication_queue as queue

    threshold = unclaimed_threshold_minutes(root)
    repo = queue._repo(root)
    item = observe_candidate(root, repo, queue._pr(root, repo, number), now=now, threshold=threshold)
    if item is None:
        raise OverviewError(f"PR #{number} carries no lifecycle record")
    return {"repository": repo, "generated_at": now.isoformat(timespec="seconds"), "candidate": item}


def show_requirement(root: Path, requirement: str, *, now: datetime) -> dict:
    import publication_queue as queue

    threshold = unclaimed_threshold_minutes(root)
    repo = queue._repo(root)
    numbers, lineage_note = queue._requirement_candidate_numbers(root, requirement, repo)
    items = [i for i in (observe_candidate(root, repo, queue._pr(root, repo, n), now=now, threshold=threshold)
                         for n in numbers) if i is not None]
    result = {"repository": repo, "generated_at": now.isoformat(timespec="seconds"),
              "requirement": _observe_requirement(root, requirement, items), "candidates": items}
    if lineage_note:
        result["shared_lineage"] = lineage_note
    return result


# ---- rendering -------------------------------------------------------------------------------

def render_candidate(item: dict, *, detail: bool) -> str:
    head = f"PR #{item['number']} [{item['stage']}] {item.get('state') or '?'} head {str(item.get('head'))[:12]}  {item['url']}"
    lines = [head]
    executor = item["executor"]
    if executor.get("claimed_by"):
        lines.append(f"  executor: claimed by {executor['claimed_by']} until {executor['claim_expires_at']}; {executor['activity']}")
    else:
        age = executor.get("job_age_minutes")
        lines.append(f"  executor: {executor['activity']}" + (f"; job published {age} min ago" if age is not None else ""))
    lines.append(f"  next: {item.get('next_operation')} | expected automation: {item.get('expected_automation')}")
    for finding in item["findings"]:
        lines.append(f"  ! {finding['kind']}: {finding['detail']} ({finding['evidence']})")
    if item.get("human_decision") and item["stage"] in {"needs-intervention", "unknown"}:
        lines.append(f"  decision needed: {item['human_decision']}")
    if detail:
        lines.append("  chain: " + " > ".join(f"{s['step']}={s['status']}" for s in item["chain"]))
        lines.append(f"  attempts: {json.dumps(item['attempts'], sort_keys=True)}")
        for action in item["actions"]:
            lines.append(f"  permitted: {action['command']}")
    return "\n".join(lines)


def render(result: dict) -> str:
    lines = []
    if "bounds" in result:
        bounds = result["bounds"]
        lines.append(f"Dev Platform lifecycle overview {result['generated_at']} ({result['repository']})")
        lines.append(f"scope: {bounds['note']} (last {bounds['merged_discovery_page']} merged); "
                     f"{bounds['prs_without_lifecycle_record']} PR(s) without lifecycle record skipped")
        for req in result["requirements"]:
            note = " (merged, Requirement not Done)" if req.get("merged_not_done") else ""
            lines.append(f"\nRequirement {req['requirement']} [{req['stage']}]{note} status={req.get('status')} "
                         f"PRs={req['candidates']}" + (f" ({req['note']})" if req.get("note") else ""))
            for finding in req["findings"]:
                lines.append(f"  ! {finding['kind']}: {finding['detail']}")
        lines.append("\nCandidates:")
        lines += [render_candidate(item, detail=False) for item in result["candidates"]] or ["  none"]
    elif "requirement" in result:
        req = result["requirement"]
        lines.append(f"Requirement {req['requirement']} [{req['stage']}] status={req.get('status')}"
                     + (" (merged, Requirement not Done)" if req.get("merged_not_done") else ""))
        lines += [f"  ! {f['kind']}: {f['detail']}" for f in req["findings"]]
        lines += [render_candidate(item, detail=True) for item in result["candidates"]] or ["  no candidate PRs"]
        if result.get("shared_lineage"):
            lines.append(result["shared_lineage"])
    else:
        lines.append(render_candidate(result["candidate"], detail=True))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only lifecycle overview for the chat coordinator (writes nothing)")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("summary", help="all candidates and open Requirements (default)")
    show = sub.add_parser("show", help="drill down into one PR or Requirement")
    target = show.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int)
    target.add_argument("--requirement")
    args = parser.parse_args(argv)
    from publication_queue import QueueError

    root = current_worktree_root()
    now = datetime.now(timezone.utc)
    try:
        if args.command == "show" and args.pr:
            result = show_pr(root, args.pr, now=now)
        elif args.command == "show":
            result = show_requirement(root, args.requirement, now=now)
        else:
            result = overview(root, now=now)
    except (OverviewError, QueueError) as exc:
        print(f"lifecycle overview: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
