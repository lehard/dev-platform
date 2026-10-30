#!/usr/bin/env python3
"""Read-only lifecycle overview for the chat coordinator role.

Projects what GitHub already records (PR heads, checks, versioned lifecycle
markers, claim and result receipts, Requirement Issues and Project statuses)
into human-facing delivery stages, the review -> ... -> cleanup chain, named
exception findings and the operator actions the supported commands would
accept. It writes nothing to GitHub, keeps no state store and, besides GitHub, only an optional disposable local read cache
(``github_read_cache``: ETag revalidated, deleting it never changes the result, a corrupt cache fails
explicitly naming the file). It reports ``unknown`` for any source it cannot read instead of presenting it as healthy.
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
from urllib.parse import quote

from _platform_common import current_worktree_root, read_platform_config

STAGES = ("not-started", "in-development", "handed-off", "delivering", "merged-open-obligations", "closed", "needs-intervention", "unknown")
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
    "provider-unavailable": "The automatic retry continues once the provider is available; switch-provider is listed when it applies.",
}
# Post-merge kinds never run hosted: the local post-merge runner claims them, and the coordinator can run one now.
POST_MERGE_UNCLAIMED_HINT = (
    "No operator command applies: the local post-merge runner (LaunchAgent dev.platform.post-merge-runner) claims "
    "{kind} jobs every 10 minutes; to run it now from the integration checkout: "
    'GH_TOKEN="$(gh auth token)" python3 scripts/lifecycle_workers.py work-next --repo {repo} --kinds {kind} --pr {number} --run')
CLAIM_FINDINGS = frozenset({"unclaimed-next-job", "expired-claim"})
EXECUTOR_NOT_CONFIRMED = "executor not confirmed"
ACTIVITY_NOT_CONFIRMED = "executor activity: not confirmed"
READ_PARALLELISM = 8
BR_BRANCH = re.compile(r"(?:^|/)br-([0-9]+)(?:-|$)", re.IGNORECASE)
PROJECT_LABEL = re.compile(r"project:[A-Za-z0-9_.-]+")


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


def idle_reason(candidate: dict, *, job: dict | None, winning: dict | None, completed: bool, open_pr: bool) -> dict | None:
    """Why an open candidate has nothing executing now: what it waits for and who or what moves it.

    ``None`` for a candidate that is not open or whose job is claimed. Every rule reads only fields the
    assessment already holds; a state no rule explains is reported as ``unknown``, never guessed.
    """
    from hosted_workers import UNHOSTED
    from lifecycle_workers import WRITE_KINDS
    from pr_review_gate import MAX_ROUNDS
    from publication_queue import MAX_INTEGRATION_REPAIRS

    if not open_pr or winning:
        return None
    state, reason = candidate["state"], str(candidate.get("reason") or "")
    attempts, red = candidate.get("attempts") or {}, candidate.get("red_gate") or {}

    def idle(kind: str, waiting_for: str, moved_by: str, evidence: str) -> dict:
        return {"kind": kind, "waiting_for": waiting_for, "moved_by": moved_by, "evidence": evidence}

    if reason.startswith("malformed marker"):
        return idle("unknown", f"idle reason unknown: {reason}", "unknown", "lifecycle record")
    if candidate.get("task_identity") is None:
        return idle("developer", "the developer to hand the PR off: it has no trusted lifecycle record yet", "developer",
                    "no task identity in the lifecycle records")
    if state == "blocked-escalation":
        limits = {"repair": MAX_ROUNDS, "integration-repair": MAX_INTEGRATION_REPAIRS}
        gate = red.get("name")
        count = attempts.get(gate)
        if gate in limits and type(count) is int and count >= limits[gate]:
            return idle("attempt-limit-exhausted", f"a human decision: {gate} attempts reached the limit ({count}/{limits[gate]}) and nothing retries automatically",
                        "a human decision", f"attempts.{gate} in the latest lifecycle record")
        return idle("human-decision", f"a human decision: the candidate is escalated ({gate or 'unnamed gate'})", "a human decision",
                    "state blocked-escalation in the latest lifecycle record")
    if job and not completed:
        kind = job["kind"]
        if kind in WRITE_KINDS and kind in UNHOSTED:
            return idle("local-node-job", f"the {kind} job, which is executed only by an operator-run local macOS node "
                        "(no hosted worker runs it)", "an operator running work-next on a local node", f"{kind} job in the latest lifecycle record")
        if kind in UNHOSTED:
            return idle("local-node-job", f"the {kind} job, which is executed only by a local operator node (no hosted worker runs it)",
                        "an operator running work-next on a local node", f"{kind} job in the latest lifecycle record")
        return idle("worker-job", f"a lifecycle worker (hosted run or local node) to claim the {kind} job", "a lifecycle worker",
                    f"{kind} job in the latest lifecycle record")
    if state in {"ready", "integrating"}:
        return idle("publication-queue", "the publication queue to integrate the candidate", "the publication queue",
                    f"state {state} in the latest lifecycle record")
    if state == "blocked-retryable":
        return idle("retry-pending", f"the automatic retry of the red {red.get('name') or 'gate'}", "the publication queue",
                    "state blocked-retryable in the latest lifecycle record")
    if state == "contribution-integrated":
        return idle("requirement-composition", "the Requirement's other contributions and its composition", "the coordinator composing the Requirement",
                    "state contribution-integrated in the latest lifecycle record")
    return idle("unknown", f"idle reason unknown: state {state} matches no known waiting rule", "unknown",
                "state in the latest lifecycle record")


def assess_candidate(candidate: dict, pr: dict, comments: list[dict], *, repo: str, apps: frozenset[str],
                     writers: frozenset[str], now: datetime, threshold_minutes: int) -> dict:
    """Pure assessment of one derived candidate: stage, chain, executor, findings and permitted actions."""
    from candidate_lifecycle import POST_MERGE_FLAG
    from lifecycle_workers import build_job, job_completed, latest_claim, winning_claim
    from pr_review_gate import _repair_status, operational_escalation, permitted_actions, permitted_post_merge_actions
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
        operational = red.get("name") == "finalize" or operational_escalation(red)
        if red.get("name") in {"repair", "review"} and not operational:
            find("escalated-finding", reason or f"{red.get('name')} escalated for a finding-level reason ({status or 'review'})",
                 f"{url} ({red.get('name')} gate evidence in the latest lifecycle record)")
        elif operational:
            cause = (red.get("evidence") or {}).get("cause") if isinstance(red.get("evidence"), dict) else None
            label = "finalize" if red.get("name") == "finalize" else cause if status in {None, "None"} else status
            find("escalated-operational", reason or f"{red.get('name')} escalated for an operational reason ({label})",
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
    if open_pr:
        plan = permitted_actions(candidate, winning, number=number, retry_kind=retry_job_kind(candidate),
                                 job_completed=completed)
    elif any(f["kind"] == "post-merge-exhausted" for f in findings):
        plan = permitted_post_merge_actions(candidate, comments, number=number, now=now, **trust)
    else:
        plan = {"actions": [], "human_decision": None}
    if stage == "needs-intervention" and not plan["human_decision"]:
        from candidate_lifecycle import POST_MERGE_KINDS

        def hint(kind: str) -> str:
            if kind == "unclaimed-next-job" and job and job["kind"] in POST_MERGE_KINDS:
                return POST_MERGE_UNCLAIMED_HINT.format(kind=job["kind"], repo=repo, number=number)
            return FINDING_HINTS[kind]
        hints = list(dict.fromkeys(hint(f["kind"]) for f in findings if f["kind"] in FINDING_HINTS))
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
            "idle": idle_reason(candidate, job=job, winning=winning, completed=completed, open_pr=open_pr),
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
        stage, note = "not-started", "no linked child; pre-authoring state is machine-local and not visible from this checkout"
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
                "idle": {"kind": "unknown", "waiting_for": f"idle reason unknown: lifecycle state is unreadable: {exc}",
                         "moved_by": "unknown", "evidence": _pr_url(repo, number)},
                "actions": [], "human_decision": None, "next_operation": None, "expected_automation": "unknown",
                "merged": bool(pr.get("merged")), "branch": (pr.get("head") or {}).get("ref")}


def _observe_requirement(root: Path, requirement: str, candidates: list[dict]) -> dict:
    import requirement_intake as intake

    try:
        aggregate = intake.aggregate(root, requirement=requirement)
        return assess_requirement(requirement, aggregate, None, candidates)
    except (intake.RequirementIntakeError, OSError) as exc:
        return assess_requirement(requirement, None, str(exc), candidates)


def _cached_read(root: Path, *args: str) -> Any:
    """A GitHub GET through the disposable read cache; read failures surface as ``QueueError``."""
    import github_read_cache
    import publication_queue as queue

    try:
        return github_read_cache.cached_gh_json(root, *args)
    except github_read_cache.GithubReadError as exc:
        raise queue.QueueError(str(exc)) from exc


def _backlog_binding(root: Path) -> tuple[str, str]:
    section = read_platform_config(root).get("development_backlog")
    section = section if isinstance(section, dict) else {}
    value, label = section.get("repository"), section.get("project_label")
    if not isinstance(value, str) or "/" not in value:
        raise OverviewError("[development_backlog] repository in .dev-platform.toml must name the Backlog repository (owner/name)")
    if not isinstance(label, str) or not PROJECT_LABEL.fullmatch(label):
        raise OverviewError("[development_backlog] project_label in .dev-platform.toml must name this project's Backlog label (project:<slug>)")
    return value, label


def _open_requirements(root: Path, backlog: str, project_label: str) -> list[str]:
    """Open Requirements of this project only: the shared Backlog also holds other projects' Requirements."""
    import publication_queue as queue

    labels = quote(f"type:requirement,{project_label}", safe=",")
    rows = _cached_read(root, "api", "--paginate", f"repos/{backlog}/issues?state=open&labels={labels}&per_page=100")
    if not isinstance(rows, list):
        raise OverviewError(f"open Requirements of {backlog} labeled {project_label} could not be listed")
    return [f"{backlog}#{row['number']}" for row in rows if isinstance(row, dict) and "pull_request" not in row]


def _requirement_of(assessment: dict) -> str | None:
    match = BR_BRANCH.search(assessment.get("branch") or "")
    return match.group(1) if match else None


def read_sessions(root: Path, *, now: datetime) -> dict:
    """The platform session registry as ``agent_sessions`` computed it; never inferred here (BR-887)."""
    import agent_sessions

    section = read_platform_config(root).get("agent_sessions")
    if not isinstance(section, dict):
        return {"configured": False, "sessions": []}
    for key in ("directory", "stale_after_seconds", "ended_keep_seconds"):
        if key not in section:
            raise OverviewError(f"[agent_sessions] {key} must be set in the platform configuration")
    try:
        items = agent_sessions.list_sessions(Path(str(section["directory"])).expanduser(), now=now,
                                             stale_after=int(section["stale_after_seconds"]),
                                             ended_keep=int(section["ended_keep_seconds"]))
    except (agent_sessions.SessionError, ValueError) as exc:
        return {"configured": True, "error": str(exc), "sessions": []}
    return {"configured": True, "sessions": items}


def read_owner_needed(root: Path, now: datetime) -> dict:
    """Open owner-needed signals from the agent board, exactly as ``agent_signal`` stores them (BR-888)."""
    import agent_signal

    return agent_signal.open_signals(root, now=now)


def attach_sessions(registry: dict, candidates: list[dict]) -> list[dict]:
    """Put each session on the candidate whose PR head ref is the session's branch; return the unattached ones."""
    by_branch: dict[str, list[dict]] = {}
    for item in registry["sessions"]:
        if item.get("branch"):
            by_branch.setdefault(item["branch"], []).append(item)
    attached: set[int] = set()
    for candidate in candidates:
        matches = by_branch.get(candidate.get("branch") or "", [])
        candidate["sessions"] = matches
        attached.update(id(m) for m in matches)
    return [item for item in registry["sessions"] if id(item) not in attached]


def _session_line(item: dict) -> str:
    detail = item.get("detail") or {}
    note = f" ({', '.join(f'{k}={v}' for k, v in detail.items() if v)})" if detail else ""
    return (f"{item['provider']} session {item['session_id'][:8]} pid {item.get('pid')} [{item['state']}]{note} "
            f"since {item['state_since']}; liveness {item.get('liveness')}")


def overview(root: Path, *, now: datetime) -> dict:
    """Summary of every candidate the workers consider and every open Requirement."""
    import publication_queue as queue
    from lifecycle_workers import MERGED_DISCOVERY_PAGE, candidate_prs
    from managed_work_identity import parent_identity

    threshold = unclaimed_threshold_minutes(root)
    repo = queue._repo(root)
    backlog, project_label = _backlog_binding(root)
    prs = candidate_prs(repo, include_merged=True, gh_json=lambda *args: _cached_read(root, *args))
    with ThreadPoolExecutor(max_workers=READ_PARALLELISM) as pool:  # independent read-only GitHub observations
        observed = list(pool.map(lambda pr: observe_candidate(root, repo, pr, now=now, threshold=threshold), prs))
        assessed = [item for item in observed if item is not None]
        without_record = len(observed) - len(assessed)
        listed = _open_requirements(root, backlog, project_label)
        requirements = list(pool.map(
            lambda requirement: _observe_requirement(root, requirement, [
                item for item in assessed if _requirement_of(item) == parent_identity(requirement).split("-")[-1]]),
            listed))
    claimed = {n for r in requirements for n in r["candidates"]}
    registry = read_sessions(root, now=now)
    unattached = attach_sessions(registry, assessed)
    return {"agent_sessions": {**{k: v for k, v in registry.items() if k != "sessions"}, "unattached": unattached},
            "owner_needed": read_owner_needed(root, now),
            "repository": repo, "backlog": backlog, "generated_at": now.isoformat(timespec="seconds"),
            "bounds": {"merged_discovery_page": MERGED_DISCOVERY_PAGE,
                       "note": "open PRs, the most recently updated closed merged PRs and every lifecycle:merged PR not "
                               "labeled post-merge:settled, exactly the workers' candidate set",
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
    registry = read_sessions(root, now=now)
    attach_sessions(registry, [item])
    return {"repository": repo, "generated_at": now.isoformat(timespec="seconds"), "candidate": item,
            "agent_sessions": {k: v for k, v in registry.items() if k != "sessions"}}


def show_requirement(root: Path, requirement: str, *, now: datetime) -> dict:
    import publication_queue as queue

    threshold = unclaimed_threshold_minutes(root)
    repo = queue._repo(root)
    numbers, lineage_note = queue._requirement_candidate_numbers(root, requirement, repo)
    items = [i for i in (observe_candidate(root, repo, queue._pr(root, repo, n), now=now, threshold=threshold)
                         for n in numbers) if i is not None]
    registry = read_sessions(root, now=now)
    attach_sessions(registry, items)
    result = {"repository": repo, "generated_at": now.isoformat(timespec="seconds"),
              "requirement": _observe_requirement(root, requirement, items), "candidates": items,
              "agent_sessions": {k: v for k, v in registry.items() if k != "sessions"}}
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
    for session in item.get("sessions", []):
        lines.append(f"  {_session_line(session)}")
    lines.append(f"  next: {item.get('next_operation')} | expected automation: {item.get('expected_automation')}")
    idle = item.get("idle")
    if idle:
        lines.append(f"  idle: {idle['waiting_for']} ({idle['evidence']})" if idle["kind"] == "unknown"
                     else f"  idle: waiting for {idle['waiting_for']}; moved by {idle['moved_by']} ({idle['evidence']})")
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


def _registry_status(registry: dict) -> str | None:
    """The explicit line for an unconfigured or unreadable registry; sessions are never silently shown as absent."""
    if not registry["configured"]:
        return "Sessions: not configured ([agent_sessions] directory in the platform configuration)"
    if registry.get("error"):
        return f"Sessions: registry unreadable: {registry['error']}"
    return None


def _owner_needed_lines(owner_needed: dict) -> list[str]:
    if not owner_needed["configured"]:
        return ["\nOwner needed: not shown (agent board capability is not enabled in the platform configuration)"]
    if owner_needed.get("error"):
        return [f"\nOwner needed: cannot be shown: {owner_needed['error']}"]
    lines = ["\nOwner needed:"]
    lines += [f"  [{s['project']}] {s['task']}: {s['question']} (id {s['id']}, {s['age_minutes']} min ago)"
              for s in owner_needed["signals"]] or ["  none"]
    return lines


def render(result: dict) -> str:
    lines = []
    if "bounds" in result:
        bounds = result["bounds"]
        lines.append(f"Dev Platform lifecycle overview {result['generated_at']} ({result['repository']})")
        lines.append(f"scope: {bounds['note']} (recent window: last {bounds['merged_discovery_page']} closed); "
                     f"{bounds['prs_without_lifecycle_record']} PR(s) without lifecycle record skipped")
        for req in result["requirements"]:
            note = " (merged, Requirement not Done)" if req.get("merged_not_done") else ""
            lines.append(f"\nRequirement {req['requirement']} [{req['stage']}]{note} status={req.get('status')} "
                         f"PRs={req['candidates']}" + (f" ({req['note']})" if req.get("note") else ""))
            for finding in req["findings"]:
                lines.append(f"  ! {finding['kind']}: {finding['detail']}")
        lines += _owner_needed_lines(result["owner_needed"])
        lines.append("\nCandidates:")
        lines += [render_candidate(item, detail=False) for item in result["candidates"]] or ["  none"]
        registry = result["agent_sessions"]
        status = _registry_status(registry)
        if status:
            lines.append(f"\n{status}")
        else:
            lines.append("\nSessions not attached to a candidate PR:")
            lines += [f"  {_session_line(item)} branch={item.get('branch') or '-'} project={item.get('project') or '-'}"
                      for item in registry["unattached"]] or ["  none"]
    elif "requirement" in result:
        req = result["requirement"]
        lines.append(f"Requirement {req['requirement']} [{req['stage']}] status={req.get('status')}"
                     + (" (merged, Requirement not Done)" if req.get("merged_not_done") else ""))
        lines += [f"  ! {f['kind']}: {f['detail']}" for f in req["findings"]]
        lines += [render_candidate(item, detail=True) for item in result["candidates"]] or ["  no candidate PRs"]
        if status := _registry_status(result["agent_sessions"]):
            lines.append(status)
        if result.get("shared_lineage"):
            lines.append(result["shared_lineage"])
    else:
        lines.append(render_candidate(result["candidate"], detail=True))
        if status := _registry_status(result["agent_sessions"]):
            lines.append(status)
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
    from github_read_cache import GithubReadCacheError
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
    except (OverviewError, QueueError, GithubReadCacheError) as exc:
        print(f"lifecycle overview: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
