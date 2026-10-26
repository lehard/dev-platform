"""Durable, source-repository final publication queue backed by GitHub PRs.

PR comments carry immutable admissions and coordinator update evidence. A single
GitHub Actions concurrency group owns branch updates and merge requests; this
module re-observes GitHub before every consequential action.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from _platform_common import GitCommandError, current_worktree_root, gate_message, read_platform_config, run_git
from publication_state import required_check_state_for_ref
from candidate_lifecycle import CLAIM_STATES, MalformedMarkerError, POST_MERGE_FLAG, PREFIX as V2_PREFIX, STATES, latest_record, build_handoff_record, derive_candidate, label_projection, marker_body, render_status

PREFIX = "dev-platform-publication-queue:v1 "
QUEUE = "publication:queued"
ACTIVE = "publication:active"
BLOCKED = "publication:blocked"
WORKFLOW = ".github/workflows/publication-queue.yml"
CHECK_WAIT_SECONDS = 240
MAX_INTEGRATION_REPAIRS = 2  # bounded integration-repair attempts before a candidate is blocked


class QueueError(RuntimeError):
    pass


class IntegrationRepairNeeded(QueueError):
    """Integration preparation failed deterministically and needs integration repair, not a block.

    ``gate`` names the red gate: a real merge conflict is ``integration``; failing required
    checks on the actual merged candidate are ``required-checks``. ``merge_only`` marks an
    ``integration`` failure whose trial merge with main is clean: it is offered as an LLM-free
    ``integration-merge`` job, not a writer repair.
    """

    def __init__(self, message: str, *, gate: str = "integration", merge_only: bool = False):
        super().__init__(message)
        self.gate = gate
        self.merge_only = merge_only


class TransientQueueError(QueueError):
    """A network, GitHub 5xx or timeout failure: the candidate waits for the next run, it is never blocked."""


def _transient(detail: str) -> bool:
    from _platform_common import is_transient_github_failure

    return is_transient_github_failure(detail) or bool(
        re.search(r"returned error: 5\d\d|could not resolve host|rpc failed", detail or "", re.IGNORECASE))


class NotFinalized(QueueError):
    """A completed OpenSpec change is still active: the candidate must be finalized first."""


class LifecycleOwnershipChanged(QueueError):
    """Another lifecycle job took the candidate between observation and transition."""


class AttentionError(RuntimeError):
    """The escalation was published but its human-readable GitHub indication could not be posted.

    Deliberately not a ``QueueError``: callers that recover from queue failures must not swallow it.
    """


class QueueEnvironmentError(RuntimeError):
    """The coordinator's own environment cannot prepare a candidate (for example a missing dependency).

    Deliberately not a ``QueueError``: it is no candidate defect, so it never blocks the candidate or offers
    integration repair; the run fails naming it (BR-768).
    """


class MalformedRecord(QueueError):
    """A trusted coordinator record is malformed.

    ``candidate_lifecycle.MalformedMarkerError`` converted at the queue boundary (`_latest`, `_record_comment_id`)
    so every queue path that maps ``QueueError`` handles it, with the message naming the comment id.
    """


def _gh(root: Path, *args: str, data: dict[str, str] | None = None) -> Any:
    cmd = ["gh", *args]
    if data:
        for key, value in data.items():
            cmd += ["-f", f"{key}={value}"]
    from _platform_common import is_github_read, run_github_with_retry

    if is_github_read(cmd):
        result = run_github_with_retry(cmd, cwd=root)
    else:
        result = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False, stdin=subprocess.DEVNULL)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"gh exit {result.returncode}"
        raise (TransientQueueError if _transient(detail) else QueueError)(detail)
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QueueError("GitHub returned non-JSON queue state") from exc


COORDINATOR_APP_ENV = "DEV_PLATFORM_COORDINATOR_APP"


def configured_coordinator_apps(root: Path) -> list[tuple[str, str]]:
    """``(source, App slug)`` pairs from project and operator config; unreadable sources raise."""
    from _platform_common import read_operator_config, read_project_config

    def source_error(name: str, cause: object) -> QueueError:
        return QueueError(f"trust source {name} is unreadable or invalid: {cause}")

    configured_apps: list[tuple[str, str]] = []
    for name, reader in ((".dev-platform.toml", read_project_config), ("operator config", read_operator_config)):
        try:
            config = reader(root)
        except Exception as exc:
            raise source_error(name, exc) from exc
        configured = config.get("publication")
        if configured is None:
            continue
        if not isinstance(configured, dict):
            raise source_error(name, "[publication] must be a table")
        app = configured.get("coordinator_app")
        if app is None:
            continue
        if not isinstance(app, str):
            raise source_error(name, "[publication] coordinator_app must be a string")
        if app.strip():
            configured_apps.append((name, app.strip()))
    return configured_apps


def trusted_apps(root: Path) -> frozenset[str]:
    """The coordinator App whose comments count as lifecycle records.

    The workflow exports the slug of the App token it minted. A local reader
    takes it from ``[publication] coordinator_app`` in the external operator
    config (operator identity stays out of committed project config) or the
    project config. No other App is trusted.
    """
    names = {os.environ.get(COORDINATOR_APP_ENV, "").strip()}
    names.update(app for _, app in configured_coordinator_apps(root))
    return frozenset(name for name in names if name)


_WRITER_PERMISSIONS = {"admin", "maintain", "write"}
_writer_cache: dict[tuple[str, str], bool] = {}


def trusted_writers(root: Path, comments: list[dict[str, Any]],
                    prefixes: tuple[str, ...] = (), *, repo: str | None = None) -> frozenset[str]:
    """MEMBER/COLLABORATOR marker authors whose repository write permission is proven."""
    writers: set[str] = set()
    for row in comments:
        user = row.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        body = str(row.get("body", ""))
        if (not isinstance(login, str) or row.get("author_association") not in {"MEMBER", "COLLABORATOR"}
                or not body.startswith(("dev-platform-publication-queue:v1 ", V2_PREFIX, *prefixes))):
            continue
        repo = repo or _repo(root)
        key = (repo, login)
        if key not in _writer_cache:
            try:
                data = _gh(root, "api", f"repos/{repo}/collaborators/{login}/permission")
            except QueueError as exc:
                # Fail closed and uncached: an unprovable author must neither be
                # trusted nor silently ignored (that could erase a real claim).
                raise QueueError(f"cannot prove write permission of marker author {login}: {exc}") from exc
            _writer_cache[key] = isinstance(data, dict) and data.get("permission") in _WRITER_PERMISSIONS
        if _writer_cache[key]:
            writers.add(login)
    return frozenset(writers)


def _derive(root: Path, pr: dict[str, Any], comments: list[dict[str, Any]], checks: dict[str, Any] | None = None) -> dict[str, Any]:
    return derive_candidate(pr, comments, checks, trusted_apps=trusted_apps(root),
                            trusted_writers=trusted_writers(root, comments))


def _latest(root: Path, number: int, comments: list[dict[str, Any]], head: str | None = None) -> dict[str, Any] | None:
    try:
        return latest_record(number, comments, trusted_apps=trusted_apps(root), head=head,
                             trusted_writers=trusted_writers(root, comments))
    except MalformedMarkerError as exc:
        raise MalformedRecord(str(exc)) from exc


def _repo(root: Path) -> str:
    data = _gh(root, "repo", "view", "--json", "nameWithOwner")
    name = data.get("nameWithOwner") if isinstance(data, dict) else None
    if not isinstance(name, str) or "/" not in name:
        raise QueueError("GitHub repository identity is unavailable")
    return name


def enabled(root: Path) -> bool:
    """Bootstrap safely: this change uses legacy finish until workflow is on main."""
    if read_platform_config(root).get("platform_version") != "source":
        return False
    return run_git(["cat-file", "-e", f"origin/main:{WORKFLOW}"], cwd=root, check=False).returncode == 0


def _comments(root: Path, repo: str, number: int) -> list[dict[str, Any]]:
    """The complete, validated, ordered PR comment history, or a named error.

    The whole observation is validated before anything is returned, so a failed
    or malformed later page never yields a prefix or a filtered history.
    """
    def fail(cause: str) -> QueueError:
        return QueueError(f"PR comment-history acquisition failed for #{number}: {cause}")

    try:
        pages = _gh(root, "api", "--paginate", "--slurp", f"repos/{repo}/issues/{number}/comments?per_page=100")
    except QueueError as exc:
        raise fail(str(exc)) from exc
    if pages is None:
        raise fail("empty response")
    if not isinstance(pages, list) or not pages:
        raise fail("response is not a non-empty array of pages")
    history: list[dict[str, Any]] = []
    previous: int | None = None
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, list):
            raise fail(f"page {index} is not an array")
        for row in page:
            if not isinstance(row, dict):
                raise fail(f"page {index} contains a non-object comment")
            comment_id = row.get("id")
            if not isinstance(comment_id, int) or isinstance(comment_id, bool):
                raise fail(f"page {index} contains a comment without an integer id")
            if previous is not None and comment_id <= previous:
                raise fail(f"comment id {comment_id} does not follow {previous} in API order")
            previous = comment_id
            history.append(row)
    return history


def _events(root: Path, repo: str, number: int) -> list[dict[str, Any]]:
    from candidate_lifecycle import trusted_marker_comment

    events = []
    comments = _comments(root, repo, number)
    apps, writers = trusted_apps(root), trusted_writers(root, comments)
    for row in comments:
        body = row.get("body")
        # Queue consumers and lifecycle status read the same trusted records.
        if not isinstance(body, str) or not body.startswith(PREFIX) or not trusted_marker_comment(row, apps, writers):
            continue
        try:
            payload = json.loads(body[len(PREFIX):])
        except json.JSONDecodeError as exc:
            raise QueueError(f"malformed publication marker on PR #{number}") from exc
        if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("number") != number:
            raise QueueError(f"invalid publication marker on PR #{number}")
        payload["comment_id"] = row.get("id")
        events.append(payload)
    return events


def _admission(events: list[dict[str, Any]], number: int) -> dict[str, Any] | None:
    """Concurrent retries share a slot; a blocked candidate may start a new one.

    An admission carrying ``supersedes`` opens the next slot only when it names the
    head the current slot proves (its admission or latest coordinator update) and a
    reason, on the same branch; any other differing admission is conflicting evidence.
    A block that lands between the developer's observation and its superseding
    admission already closed the superseded slot: that admission then opens a fresh
    slot like any admission after a block, keeping its supersession as provenance.
    """
    blocks = [event["comment_id"] for event in events if event.get("kind") == "block" and isinstance(event.get("comment_id"), int)]
    cutoff = max(blocks, default=0)
    slot: dict[str, Any] | None = None
    proven: Any = None
    for event in sorted((event for event in events if isinstance(event.get("comment_id"), int) and event["comment_id"] > cutoff),
                        key=lambda event: event["comment_id"]):
        if event.get("kind") == "update" and slot is not None:
            proven = event.get("head")
        if event.get("kind") != "admit":
            continue
        supersedes = event.get("supersedes")
        if slot is None and (supersedes is None or (
                cutoff and isinstance(supersedes, dict) and isinstance(supersedes.get("head"), str)
                and supersedes["head"] != event.get("head")
                and isinstance(supersedes.get("reason"), str) and supersedes["reason"].strip())):
            slot, proven = event, event.get("head")
        elif slot is not None and all(event.get(key) == slot.get(key) for key in ("head", "branch")):
            continue  # a concurrent retry of the same admission shares its slot
        elif (slot is not None and isinstance(supersedes, dict) and supersedes.get("head") == proven
              and event.get("head") != proven and event.get("branch") == slot.get("branch")
              and isinstance(supersedes.get("reason"), str) and supersedes["reason"].strip()):
            slot, proven = event, event.get("head")
        else:
            raise QueueError(f"PR #{number} has conflicting admission evidence")
    return slot


def _proven_head(events: list[dict[str, Any]], admission: dict[str, Any]) -> Any:
    """The head the admission slot proves: its admission head or its latest coordinator update."""
    updates = [event for event in events if event.get("kind") == "update"
               and event.get("comment_id", 0) > admission.get("comment_id", 0)]
    return updates[-1].get("head") if updates else admission.get("head")


def _record_comment_id(root: Path, number: int, comments: list[dict[str, Any]], head: str) -> int | None:
    """Comment id of the latest trusted, valid v2 record for ``head``, if any."""
    apps, writers = trusted_apps(root), trusted_writers(root, comments)
    found = None
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        try:
            record = latest_record(number, [row], trusted_apps=apps, head=head, trusted_writers=writers)
        except MalformedMarkerError as exc:
            raise MalformedRecord(str(exc)) from exc
        if record is not None:
            found = row.get("id")
    return found


def _comment(root: Path, repo: str, number: int, payload: dict[str, Any]) -> None:
    payload = {"version": 1, "number": number, **payload}
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", data={"body": PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":"))})


def _label(root: Path, repo: str, number: int, label: str, *, present: bool) -> None:
    if present:
        _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/labels", data={"labels[]": label})
    else:
        result = subprocess.run(["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/{number}/labels/{label.replace(':', '%3A')}"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if result.returncode and "404" not in result.stderr:
            raise QueueError(result.stderr.strip() or "cannot remove publication label")


EVIDENCE_PREFIX = "dev-platform-publication-queue:evidence:v1 "
_EVIDENCE_TEXT = ("category", "severity", "observation", "evidence", "hypothesis", "proposal")
_SHA = re.compile(r"[0-9a-f]{40}")
_DEDUPE = re.compile(r"coordinator:([0-9a-f]{24})")


def evidence_event_id(dedupe_key: str) -> str:
    """The deterministic event id shared by the durable record and its local mirror."""
    match = _DEDUPE.fullmatch(dedupe_key) if isinstance(dedupe_key, str) else None
    if match is None:
        raise QueueError("coordinator evidence dedupe key is malformed")
    return "coordinator-" + match.group(1)[:16]


def build_evidence_record(event: dict[str, Any], *, attribution: dict[str, str | None] | None) -> dict[str, Any]:
    """The bounded, sanitized durable record for one coordinator friction event.

    ``attribution`` is the candidate branch's public work identity (or ``None`` for an
    unmanaged branch); no private Requirement reference is written to the pull request.
    """
    from datetime import datetime, timezone

    import agent_friction

    missing = [key for key in ("task", "number", "head", "stage", "worker", "dedupe_key", "triggers", "reason", *_EVIDENCE_TEXT)
               if event.get(key) in (None, "", [])]
    if missing:
        raise QueueError("coordinator evidence event lacks " + ", ".join(missing))
    if not _SHA.fullmatch(str(event["head"])):
        raise QueueError("coordinator evidence head must be a full commit SHA")
    record: dict[str, Any] = {
        "version": 1, "kind": "coordinator-friction",
        "work_identity": (attribution or {}).get("work_identity"),
        "child_identity": (attribution or {}).get("child_identity"),
        "number": event["number"], "head": event["head"], "stage": event["stage"],
        "worker": event["worker"], "task": event["task"], "dedupe_key": event["dedupe_key"],
        "event_id": evidence_event_id(event["dedupe_key"]),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "triggers": sorted(set(event["triggers"])),
        "reason": agent_friction.normalize_text(event["reason"], "reason", agent_friction.REASON_MAX),
    }
    for key in _EVIDENCE_TEXT:
        record[key] = agent_friction.normalize_text(event[key], key, 100 if key == "category" else 1000)
    return record


def _evidence_records(root: Path, number: int, comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Trusted evidence records of one PR; a malformed trusted record raises."""
    from candidate_lifecycle import trusted_marker_comment

    apps = trusted_apps(root)
    writers = trusted_writers(root, comments, (EVIDENCE_PREFIX,))
    records = []
    for row in comments:
        body = row.get("body")
        if not isinstance(body, str) or not body.startswith(EVIDENCE_PREFIX) or not trusted_marker_comment(row, apps, writers):
            continue
        def invalid(cause: str) -> QueueError:
            return QueueError(f"invalid coordinator evidence record on PR #{number}: {cause}")
        try:
            payload = json.loads(body[len(EVIDENCE_PREFIX):])
        except json.JSONDecodeError as exc:
            raise invalid("not JSON") from exc
        if not isinstance(payload, dict) or payload.get("version") != 1 or payload.get("kind") != "coordinator-friction":
            raise invalid("unsupported version or kind")
        if payload.get("number") != number:
            raise invalid("PR number contradicts its comment")
        if not isinstance(payload.get("head"), str) or not _SHA.fullmatch(payload["head"]):
            raise invalid("head is not a full commit SHA")
        for key in ("stage", "worker", "task", "dedupe_key", "event_id", "at", *_EVIDENCE_TEXT):
            if not isinstance(payload.get(key), str) or not payload[key]:
                raise invalid(f"{key} is missing")
        if payload.get("requirement") is not None and not isinstance(payload["requirement"], str):
            raise invalid("requirement is malformed")
        from managed_work_identity import TOKEN
        for key, child in (("work_identity", False), ("child_identity", True)):
            value = payload.get(key)
            if value is not None and not (isinstance(value, str) and TOKEN.fullmatch(value) and ("/T" in value) == child):
                raise invalid(f"{key} is malformed")
        triggers = payload.get("triggers")
        if not isinstance(triggers, list) or not triggers or not all(isinstance(t, str) for t in triggers):
            raise invalid("triggers are missing")
        if payload["event_id"] != evidence_event_id(payload["dedupe_key"]):
            raise invalid("event id does not match its dedupe key")
        # Records written before reason was required carry none; routing withholds those.
        if "reason" in payload and (not isinstance(payload["reason"], str) or not payload["reason"].strip()):
            raise invalid("reason is malformed")
        payload["comment_id"] = row.get("id")
        records.append(payload)
    return records


def post_evidence(root: Path, event: dict[str, Any], *, attribution: dict[str, str | None] | None) -> dict[str, Any]:
    """Persist one coordinator friction event on its candidate PR, once per dedupe key."""
    record = build_evidence_record(event, attribution=attribution)
    repo = _repo(root)
    number = record["number"]
    for existing in _evidence_records(root, number, _comments(root, repo, number)):
        if existing["dedupe_key"] == record["dedupe_key"]:
            return existing
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments",
        data={"body": EVIDENCE_PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))})
    return record


def requirement_evidence(root: Path, requirement: str, children: Sequence[str] = ()) -> list[dict[str, Any]]:
    """Trusted durable coordinator events of a Requirement's candidate PRs, as friction events.

    A record belongs to the Requirement by its public work identity; records written
    before work-identity attribution match by their stored Requirement reference.
    """
    from managed_work_identity import parent_identity

    repo = _repo(root)
    numbers, _ = _requirement_candidate_numbers(root, requirement, repo)
    owners = {requirement, *children}
    identity = parent_identity(requirement)
    events = []
    for number in numbers:
        for record in _evidence_records(root, number, _comments(root, repo, number)):
            if record.get("work_identity") != identity and record.get("requirement") not in owners:
                continue
            events.append({
                "id": record["event_id"], "at": record["at"], "task": record["task"], "branch": record["task"],
                "requirement": requirement if record.get("work_identity") == identity else record["requirement"],
                "attribution": "coordinator",
                "dedupe_key": record["dedupe_key"], "category": record["category"],
                "triggers": record["triggers"], "severity": record["severity"],
                "observation": record["observation"], "evidence": record["evidence"],
                "hypothesis": record["hypothesis"], "proposal": record["proposal"],
                **({"reason": record["reason"]} if "reason" in record else {}),
                "candidate": {"task": record["task"], "number": number, "head": record["head"]},
                "scope": "platform", "classification": "process-friction", "context": None,
                "durable": {"number": number, "head": record["head"], "stage": record["stage"],
                            "worker": record["worker"]},
            })
    return events


# Coordinator friction: recorded automatically, attributed to the candidate task and its
# Requirement. The sink is registered explicitly by real coordinator/worker entrypoints
# (``use_default_friction_sink``) so library use and tests never write a friction log.
_friction_sink = None
_FRICTION_STATES = {
    "repair-pending": ("coordinator-review-repair", "medium", ["repeated-error"],
                       "Independent review found material findings and a repair job was offered"),
    "blocked-retryable": ("coordinator-retry", "medium", ["excessive-retry"],
                          "A lifecycle gate was unavailable or failed and a bounded retry was scheduled"),
    "integration-repair-pending": ("coordinator-integration-repair", "medium", ["repeated-error"],
                                   "Integration found a real conflict or failing check and an integration-repair job was offered"),
    "blocked-escalation": ("lifecycle-blocked-escalation", "high", ["repeated-error"],
                           "The candidate was blocked and needs human escalation"),
}


_friction_worker: str | None = None


def set_friction_sink(sink, *, worker: str | None = None) -> None:
    """Register the coordinator friction sink with the run identity it records."""
    global _friction_sink, _friction_worker
    _friction_sink = sink
    _friction_worker = worker


def use_default_friction_sink(root: Path, *, worker: str) -> None:
    from integration_contour import default_friction_sink

    if not isinstance(worker, str) or not worker.strip():
        raise QueueError("the coordinator friction sink requires a worker run identity")
    set_friction_sink(default_friction_sink(root), worker=worker)


def friction_reason(number: int, kind: str, red_gate: dict[str, Any] | None) -> str:
    """One bounded line naming the red gate and its cause; a transition without one fails."""
    if not isinstance(red_gate, dict) or not isinstance(red_gate.get("name"), str) or not red_gate["name"]:
        raise QueueError(f"friction recording for PR #{number} ({kind}) requires a named red gate as its reason")
    parts = [str(red_gate[key]) for key in ("cause", "limitation") if red_gate.get(key)]
    if not parts:
        evidence = red_gate.get("evidence")
        if isinstance(evidence, (dict, list)):
            evidence = json.dumps(evidence, ensure_ascii=False, sort_keys=True, default=str)
        if evidence in (None, ""):
            raise QueueError(f"friction recording for PR #{number} ({kind}): red gate {red_gate['name']} carries no cause or evidence")
        parts = [str(evidence)]
    return " ".join(f"{red_gate['name']}: {'; '.join(parts)}".split())[:240]


def require_friction_attribution(branch: str | None) -> None:
    """Prove, before a job starts, that the registered sink can attribute this candidate's friction.

    Without a registered sink no friction is recorded (library and test use), so
    there is nothing to prove; with one, a missing branch or a malformed managed
    identity raises before any reviewer or writer runs and before any push.
    """
    if _friction_sink is None:
        return
    import managed_work_identity

    if not isinstance(branch, str) or not branch:
        raise QueueError("friction attribution requires a candidate branch")
    try:
        managed_work_identity.branch_attribution(branch)
    except managed_work_identity.IdentityError as exc:
        raise QueueError(f"friction cannot be attributed for {branch}: {exc}") from exc


def emit_friction(number: int, branch: str | None, kind: str, head: str, red_gate: dict[str, Any] | None, *,
                  attempts: dict[str, int] | None = None) -> None:
    """Record required friction before publishing a transition; failures leave it retryable."""
    if _friction_sink is None:
        return
    if not isinstance(branch, str) or not branch:
        raise QueueError("friction recording requires a candidate branch; retry transition")
    if kind == "blocked-retryable" and red_gate is None:
        # Waiting on exact-head required checks (see red_retry_blocks_integration): no gate failed, no event.
        return
    reason = friction_reason(number, kind, red_gate)
    detail = str(red_gate.get("evidence", ""))[:300]
    if not isinstance(_friction_worker, str) or not _friction_worker:
        raise QueueError("friction sink is installed without a worker run identity")
    import hashlib

    spec = _FRICTION_STATES.get(kind)
    category, severity, triggers, observation = spec if spec else (
        "coordinator-" + kind, "medium", ["nondefault-override"], detail)
    key = hashlib.sha256(json.dumps([number, kind, head, sorted((attempts or {}).items())]).encode()).hexdigest()[:24]
    try:
        _friction_sink({"task": branch, "number": number, "category": category, "severity": severity,
                        "triggers": triggers, "observation": observation,
                        "evidence": f"PR #{number} {kind} at head {head[:12]}: {detail}"[:1000],
                        "reason": reason,
                        "hypothesis": "Recorded automatically by the publication coordinator; see the PR lifecycle records.",
                        "proposal": "Review whether the gate, the evidence or the repair path should change.",
                        "dedupe_key": f"coordinator:{key}", "head": head, "stage": kind,
                        "worker": _friction_worker})
    except (Exception, SystemExit) as exc:
        raise QueueError(f"friction recording failed for PR #{number} ({kind}); retry transition: {exc}") from exc


def _transition(
    root: Path, repo: str, number: int, state: str, head: str, *,
    task_identity: str | dict[str, Any], red_gate: dict[str, Any] | None = None,
    gates: dict[str, Any] | None = None, attempt: str | None = None,
    set_attempts: dict[str, int] | None = None,
    refuse_from: set[str] | frozenset[str] = frozenset(), inherit_identity: bool = True,
    cross_head_claims: bool = False, next_job: dict[str, Any] | None = None,
    route: dict[str, str] | None = None, provider_switch: dict[str, list[str]] | None = None,
) -> dict[str, Any] | None:
    """Publish the v2 handoff record for one transition and project its lifecycle label.

    v1 admission/update markers stay authoritative for the existing queue; the
    v2 record is what a later executor or ``status`` reads to continue. The PR
    head and latest record are re-observed first: a moved head publishes
    nothing; a current-head record in ``refuse_from`` (another job's ownership)
    raises ``LifecycleOwnershipChanged``; a transition carrying nothing new is
    not re-published (scheduled retries must not grow the comment
    history) but still repairs the label projection. Gates, items not re-verified
    and the next job carry forward from the latest exact-head record; task
    identity and attempt counters carry forward across coordinator head updates
    unless the caller proves a fresh identity (``inherit_identity=False``).
    """
    from datetime import datetime, timezone

    observed = _pr(root, repo, number)
    if observed.get("head", {}).get("sha") != head:
        return None
    comments = _comments(root, repo, number)
    current = _derive(root, observed, comments)
    # Carry-forward and de-duplication use the persisted record, not the derived
    # view (which overlays checks, labels and a later v1 block).
    try:
        previous = _latest(root, number, comments, head)
        lineage = _latest(root, number, comments)
    except MalformedRecord as exc:
        if refuse_from:
            raise LifecycleOwnershipChanged(f"candidate is now {current['state']}; {exc}") from exc
        raise
    if previous is None:
        previous = {}  # legitimate absence: no record at this head yet (first transition, or a head the coordinator moved)
    if lineage is None:
        lineage = {}  # legitimate absence: no persisted record at all (first admission, or an admission that predates v2 records)
    if refuse_from:
        owner = None
        if review_owned(current) and "review-pending" in refuse_from:
            owner = current["state"]
        if current.get("head") == head and current.get("task_identity") is not None and current["state"] in refuse_from:
            owner = current["state"]
        elif cross_head_claims and lineage.get("state") in CLAIM_STATES & set(refuse_from):
            # A claim recorded on the head observed before a coordinator branch
            # update still owns the candidate.
            owner = lineage["state"]
        if owner is not None or _malformed(current):
            raise LifecycleOwnershipChanged(f"candidate is now {owner or current['state']}; {current.get('reason') or current.get('next_action')}")
    new_gates = any(previous.get("gates", {}).get(name) != gate for name, gate in (gates or {}).items())
    new_job = next_job is not None and next_job != previous.get("next_job")
    identity_changed = not inherit_identity and previous.get("task_identity") != task_identity
    final_identity = ((previous.get("task_identity") or lineage.get("task_identity") or task_identity)
                      if inherit_identity else task_identity)
    # The originating task route travels with the candidate: an explicit handoff route wins,
    # otherwise the previous exact-head record, then the lineage, keeps it across head changes.
    recorded_route = route or previous.get("route") or lineage.get("route")
    if recorded_route is not None and isinstance(final_identity, dict) and final_identity.get("change") not in (None, recorded_route["change"]):
        raise QueueError(f"PR #{number} task identity change {final_identity['change']} contradicts its recorded "
                         f"originating route change {recorded_route['change']}; re-run developer handoff")
    new_route = recorded_route is not None and recorded_route != previous.get("route")
    # An operator provider switch travels with the candidate like the route; a new switch replaces that kind only.
    carried_switch = previous.get("provider_switch") or lineage.get("provider_switch") or {}
    recorded_switch = {**carried_switch, **(provider_switch or {})} or None
    new_route = new_route or recorded_switch != previous.get("provider_switch")
    new_attempts = any(previous.get("attempts", {}).get(k) != v for k, v in (set_attempts or {}).items())
    branch = observed.get("head", {}).get("ref")
    if not identity_changed and not new_attempts and previous.get("state") == state and red_gate in (None, previous.get("red_gate")) and not new_gates and not new_job and not new_route:
        if state in _FRICTION_STATES:
            emit_friction(number, branch, state, head, previous.get("red_gate"), attempts=previous.get("attempts"))
        _project_lifecycle_label(root, repo, number, observed, state)
        if previous and needs_attention(previous):
            # A lost indication is repaired on the next observation of the same escalation.
            ensure_attention(root, repo, number, previous, comments)
        return previous
    # A proven coordinator update can retain content-bound gates from lineage.
    # Head-only legacy gates never survive a head move.
    if not previous and inherit_identity and isinstance(lineage.get("task_identity"), dict):
        carried = {name: gate for name, gate in lineage.get("gates", {}).items()
                   if gate.get("identity") == lineage["task_identity"] and lineage["task_identity"].get("task_content")}
    else:
        carried = previous.get("gates", {})
    merged_gates = {**(carried if inherit_identity or previous.get("task_identity") == task_identity else {}),
                    **(gates or {})}
    attempts = dict(previous.get("attempts") or lineage.get("attempts") or {})
    if attempt is not None and previous.get("state") != state and state not in {"reviewing", "repairing"}:
        attempts[attempt] = attempts.get(attempt, 0) + 1
    if isinstance(next_job, dict) and type(next_job.get("attempt")) is int:
        attempts[next_job["kind"]] = next_job["attempt"]
    attempts.update(set_attempts or {})
    record = build_handoff_record(
        number=number, state=state, head=head,
        task_identity=final_identity,
        gates=merged_gates, red_gate=red_gate,
        not_reverified=list(previous.get("not_reverified") or lineage.get("not_reverified") or []),
        attempts=attempts,
        next_job=next_job if next_job is not None else (previous.get("next_job") if state == previous.get("state") or state in {"reviewing", "repairing"} else None),
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        route=recorded_route,
        provider_switch=recorded_switch,
    )
    if state in _FRICTION_STATES:
        emit_friction(number, branch, state, head, red_gate, attempts=attempts)
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", data={"body": marker_body(record)})
    _project_lifecycle_label(root, repo, number, observed, state)
    if needs_attention(record):
        ensure_attention(root, repo, number, record, comments)
    return record


ATTENTION_PREFIX = "<!-- dev-platform-publication-queue:attention:v1 "
# A writer-needing repair is escalated to the operator, who runs it; no writer starts automatically (BR-768).
REPAIR_ATTENTION_KINDS = {"repair-pending": "repair", "integration-repair-pending": "integration-repair"}
ATTENTION_STATES = frozenset({"blocked-escalation", *REPAIR_ATTENTION_KINDS})


def needs_attention(record: dict[str, Any]) -> bool:
    """An escalation or a writer-needing repair round; an LLM-free integration merge needs no operator."""
    if record.get("state") not in ATTENTION_STATES:
        return False
    return not (record["state"] == "integration-repair-pending" and integration_job_kind(record.get("red_gate")) != "integration-repair")


def integration_job_kind(red_gate: dict[str, Any] | None) -> str:
    """The job of an ``integration-repair-pending`` round: the LLM-free merge when the round is merge-only."""
    from lifecycle_workers import MERGE_ONLY_KIND

    return MERGE_ONLY_KIND if (red_gate or {}).get("merge_only") is True else "integration-repair"


def repair_attention_body(repo: str, number: int, candidate: dict[str, Any]) -> str:
    """The operator-facing "Repair needed" text: why, the evidence and the command that runs the published job."""
    kind = REPAIR_ATTENTION_KINDS[candidate["state"]]
    red = candidate.get("red_gate") or {}
    return "\n".join([
        f"{ATTENTION_PREFIX}{attention_key(number, candidate)} -->",
        f"**Repair needed: PR #{number} is `{candidate['state']}`.**", "",
        f"- Reason: {candidate.get('reason') or str(red.get('evidence') or red.get('name') or 'no reason recorded')[:300]}",
        f"- Head: `{candidate.get('head')}`",
        f"- Evidence: https://github.com/{repo}/pull/{number} (latest lifecycle record and `{red.get('name', kind)}` evidence)",
        f"- Attempts: `{json.dumps(candidate.get('attempts', {}), sort_keys=True)}`", "",
        f"The `{kind}` job is published and needs a writer; no writer runs automatically. An operator runs it:",
        f"- `python3 scripts/lifecycle_workers.py work-next --repo {repo} --kinds {kind} --writer claude-sandboxed --run`",
        "", "This comment is posted once per exact repair round; normal progress posts nothing."])


def attention_key(number: int, candidate: dict[str, Any]) -> str:
    """Identity of one exact escalation: head, state, reason and the attempt counters of that round."""
    import hashlib

    red = candidate.get("red_gate") or {}
    material = [number, candidate.get("head"), candidate.get("state"), red.get("name"),
                sorted((candidate.get("attempts") or {}).items())]
    return hashlib.sha256(json.dumps(material, default=str).encode()).hexdigest()[:24]


def attention_body(repo: str, number: int, candidate: dict[str, Any], claim: dict[str, Any] | None) -> str:
    """The human-readable comment: what stopped, the evidence, and what a human can or must decide."""
    from pr_review_gate import permitted_actions

    if candidate.get("state") in REPAIR_ATTENTION_KINDS:
        return repair_attention_body(repo, number, candidate)
    plan = permitted_actions(candidate, claim, number=number, retry_kind=retry_job_kind(candidate))
    if candidate.get("state") == "merged":
        plan = {"actions": [], "human_decision": candidate.get("reason") or "A post-merge obligation needs an operator."}
    red = candidate.get("red_gate") or {}
    lines = [f"{ATTENTION_PREFIX}{attention_key(number, candidate)} -->",
             f"**Needs attention: PR #{number} is `{candidate['state']}`.**", "",
             f"- Reason: {candidate.get('reason') or str(red.get('evidence') or red.get('name') or 'no reason recorded')[:300]}",
             f"- Head: `{candidate.get('head')}`",
             f"- Evidence: https://github.com/{repo}/pull/{number} (latest lifecycle record and `{red.get('name', 'gate')}` evidence)",
             f"- Attempts: `{json.dumps(candidate.get('attempts', {}), sort_keys=True)}`", ""]
    if plan["actions"]:
        lines.append("Permitted next action (an operator decision, not automatic):")
        lines += [f"- `{item['command']}`" for item in plan["actions"]]
    else:
        lines.append("No supported automatic recovery applies. " + (plan["human_decision"] or "A human decision is needed."))
    lines += ["", "This comment is posted once per exact escalation; normal progress posts nothing."]
    return "\n".join(lines)


def ensure_attention(root: Path, repo: str, number: int, candidate: dict[str, Any],
                     comments: list[dict[str, Any]]) -> bool:
    """Post the attention comment for this exact escalation unless a trusted one exists; True if posted."""
    from candidate_lifecycle import trusted_marker_comment
    from lifecycle_workers import CLAIM_PREFIX, build_job, winning_claim

    marker = f"{ATTENTION_PREFIX}{attention_key(number, candidate)} -->"
    apps, writers = trusted_apps(root), trusted_writers(root, comments, (ATTENTION_PREFIX,), repo=repo)
    if any(isinstance(row.get("body"), str) and row["body"].startswith(marker)
           and trusted_marker_comment(row, apps, writers) for row in comments):
        return False
    job = build_job(candidate)
    claim = winning_claim(job, comments, trusted_apps=apps,
                          trusted_writers=trusted_writers(root, comments, (CLAIM_PREFIX,), repo=repo)) if job else None
    try:
        _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments",
            data={"body": attention_body(repo, number, candidate, claim)})
    except QueueError as exc:
        raise AttentionError(f"PR #{number} escalation was published but the attention comment failed: {exc}") from exc
    return True


def ensure_post_merge_attention(root: Path, repo: str, number: int) -> bool:
    """Indicate on the merged PR that a post-merge obligation spent its attempts (once per exact state)."""
    pr = _pr(root, repo, number)
    comments = _comments(root, repo, number)
    candidate = _derive(root, pr, comments)
    reason = str(candidate.get("reason", ""))
    if candidate.get("state") != "merged" or not (reason.startswith("post-merge") and "exhausted" in reason):
        return False
    return ensure_attention(root, repo, number, candidate, comments)


def _require_route(candidate: dict[str, Any], number: int, kind: str) -> dict[str, str]:
    """The originating task route recorded on the candidate, or an explicit failure."""
    from model_routing import PROVIDERS

    route = candidate.get("route")
    if not isinstance(route, dict):
        raise QueueError(f"{kind} job for PR #{number} has no originating task route; re-run developer handoff")
    if route.get("provider") not in PROVIDERS:
        raise QueueError(f"{kind} job for PR #{number} has unsupported originating route provider {route.get('provider')!r}")
    identity = candidate.get("task_identity")
    if isinstance(identity, dict) and identity.get("change") not in (None, route.get("change")):
        raise QueueError(f"PR #{number} task identity change {identity['change']} contradicts its recorded "
                         f"originating route change {route.get('change')}; re-run developer handoff")
    return route


# Owner decision (BR-768, variant A): a candidate without a developer route (Requirement composition, quick
# task) is repaired by the Claude writer on the balanced R2 tier; the route is recorded on the candidate.
DEFAULT_REPAIR_PROVIDER = "claude"
DEFAULT_REPAIR_PROFILE = "standard"


def _repair_route(candidate: dict[str, Any], observed: dict[str, Any], number: int, kind: str) -> tuple[dict[str, str], bool]:
    """``(route, recorded_now)`` for a repair or integration-repair job.

    A recorded route wins. Without one, a Requirement composition or a quick task (an ``agent/`` branch whose
    identity names no managed change) gets the default route; any other candidate fails explicitly naming why.
    """
    if isinstance(candidate.get("route"), dict):
        return _require_route(candidate, number, kind), False
    identity = candidate.get("task_identity")
    branch = str(observed.get("head", {}).get("ref") or "")
    if isinstance(identity, dict) and identity.get("kind") == "requirement-composition":
        change = identity.get("change")
    elif branch.startswith("agent/") and not (isinstance(identity, dict) and identity.get("change")):
        change = branch.removeprefix("agent/")
    else:
        raise QueueError(f"{kind} job for PR #{number} has no originating task route and is not a Requirement "
                         "composition or quick task, which alone get the default route; re-run developer handoff")
    if not isinstance(change, str) or not change:
        raise QueueError(f"{kind} job for PR #{number} cannot name the change of its default route")
    return {"provider": DEFAULT_REPAIR_PROVIDER, "profile": DEFAULT_REPAIR_PROFILE, "change": change}, True


def publish_job(root: Path, repo: str, number: int, kind: str, head: str, *,
                task_identity: str | dict[str, Any], attempt: int | None = None,
                providers=None, target_head=None, phase=None, reoffer=None) -> dict[str, Any] | None:
    """Publish a head-bound job record for the candidate's current state (no new state)."""
    from lifecycle_workers import WorkerError, authorized_repair_providers, job_record

    observed = _pr(root, repo, number)
    current = _derive(root, observed, _comments(root, repo, number))
    if attempt is None:
        attempt = current.get("attempts", {}).get(kind, 0)
    recorded_route = None
    if kind in {"repair", "integration-repair"}:
        route, recorded_now = _repair_route(current, observed, number, kind)
        recorded_route = route if recorded_now else None
        switched = (current.get("provider_switch") or {}).get("repair")
        providers = (list(switched) if switched else [route["provider"]]) if providers is None else list(providers)
        try:
            authorized_repair_providers(route, providers, reoffer, f"{kind} job for PR #{number}", switched=switched)
        except WorkerError as exc:
            raise QueueError(str(exc)) from exc
    elif kind == "review" and providers is None and (current.get("provider_switch") or {}).get("review"):
        providers = list(current["provider_switch"]["review"])
    elif kind == "review" and providers is None:
        from independent_review_runner import settings

        providers = settings(root).get("providers")
        if providers is None:
            providers = [_require_route(current, number, kind)["provider"]]
    return _transition(root, repo, number, current["state"], head,
                       task_identity=current.get("task_identity") or task_identity,
                       red_gate=current.get("red_gate") if kind in {"repair", "integration-repair", "integration-merge"} else None,
                       route=recorded_route,
                       next_job=job_record(kind, head, current.get("task_identity") or task_identity, attempt,
                                           providers=providers, target_head=target_head, phase=phase, reoffer=reoffer))


def _raise_if_owned_elsewhere(root: Path, repo: str, number: int, head: str) -> None:
    comments = _comments(root, repo, number)
    claimed = _derive(root, _pr(root, repo, number), comments)
    if _malformed(claimed):
        raise LifecycleOwnershipChanged(f"candidate is now {claimed['state']}; {claimed.get('reason') or claimed.get('next_action')}")
    newest = _latest(root, number, comments)
    if newest is None:
        newest = {}  # legitimate absence: no trusted record, so no record claims the candidate
    exact_owner = claimed.get("head") == head and claimed.get("task_identity") is not None and claimed["state"] in NOT_INTEGRABLE
    if exact_owner or newest.get("state") in CLAIM_STATES:
        raise LifecycleOwnershipChanged(
            f"candidate is now {newest.get('state') or claimed['state']}; {claimed.get('reason') or claimed.get('next_action')}")


def _malformed(candidate: dict[str, Any]) -> bool:
    return candidate.get("state") == "blocked-escalation" and str(candidate.get("reason", "")).startswith("malformed marker")


def _project_lifecycle_label(root: Path, repo: str, number: int, observed: dict[str, Any], state: str) -> None:
    wanted = label_projection({"state": state})[0]
    present = {label.get("name") for label in observed.get("labels", []) if isinstance(label, dict)}
    for other in sorted(STATES):
        name = f"lifecycle:{other}"
        if name != wanted and name in present:
            _label(root, repo, number, name, present=False)
    if wanted not in present:
        subprocess.run(["gh", "label", "create", wanted, "--color", "c5def5", "--force"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        _label(root, repo, number, wanted, present=True)


# v2 states owned by other lifecycle work; the integration worker must not take them over.
# Escalation and integration repair must be resolved first; integration never clears a red gate.
NOT_INTEGRABLE = {
    "review-pending", "reviewing", "repair-pending", "repairing", "finalize-pending",
    "blocked-escalation", "integration-repair-pending",
}


def retry_job_kind(candidate: dict) -> str | None:
    """The review or repair job a blocked-retryable candidate waits on (provider unavailable), if any."""
    if candidate.get("state") != "blocked-retryable":
        return None
    kind = (candidate.get("next_job") or {}).get("kind")
    if kind in {"review", "repair"}:
        return kind
    if (candidate.get("red_gate") or {}).get("name") == "review":
        return "review"
    repair = (candidate.get("gates") or {}).get("repair")
    if isinstance(repair, dict) and (repair.get("evidence") or {}).get("cause") == "provider-unavailable":
        return "repair"
    return None


def review_owned(candidate: dict) -> bool:
    """Review- and repair-owned retry states belong to their jobs; publication leaves them alone."""
    return retry_job_kind(candidate) is not None


def red_retry_blocks_integration(candidate: dict) -> bool:
    """A blocked-retryable candidate integrates only while it waits on its exact-head required checks.

    Any other red gate (for example a finalize that stopped on ``semantic-verification``) is a gate the
    candidate has not passed: the archive alone must never let it merge.
    """
    if candidate.get("state") != "blocked-retryable":
        return False
    return (candidate.get("red_gate") or {}).get("name") not in {None, "required-checks"}


def _ensure_labels(root: Path) -> None:
    for name, color in ((QUEUE, "a2eeef"), (ACTIVE, "fbca04"), (BLOCKED, "b60205")):
        result = subprocess.run(["gh", "label", "create", name, "--color", color, "--force"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if result.returncode:
            raise QueueError(result.stderr.strip() or f"cannot ensure label {name}")


def _pr(root: Path, repo: str, number: int) -> dict[str, Any]:
    data = _gh(root, "api", f"repos/{repo}/pulls/{number}")
    if not isinstance(data, dict) or data.get("number") != number:
        raise QueueError(f"PR #{number} is unavailable")
    return data


def _main(root: Path) -> str:
    from _platform_common import GitCommandError, github_retry_attempts, is_transient_github_failure

    attempts = github_retry_attempts()
    for attempt in range(1, attempts + 1):
        try:
            result = run_git(["ls-remote", "origin", "refs/heads/main"], cwd=root)
            break
        except GitCommandError as exc:
            # A transient network failure is retried with bounded backoff; others fail closed.
            if attempt >= attempts or not is_transient_github_failure(str(exc)):
                raise QueueError(f"authoritative main SHA is unavailable: {exc}") from exc
            time.sleep(min(2 ** (attempt - 1), 8))
    sha = result.stdout.split()[0] if result.stdout.split() else ""
    if len(sha) != 40:
        raise QueueError("authoritative main SHA is unavailable")
    return sha


def _managed_state(root: Path) -> dict[str, Any] | None:
    from managed_task import ManagedTaskError, read_task_state

    try:
        return read_task_state(root)
    except (ManagedTaskError, OSError) as exc:
        raise QueueError(f"managed task state is unreadable: {exc}") from exc


def _touches_openspec_change(root: Path, head: str) -> bool:
    """Whether the admitted head, read from git, changes any OpenSpec change directory."""
    base = run_git(["merge-base", head, "origin/main"], cwd=root, check=False)
    if base.returncode != 0 or not base.stdout.strip():
        raise QueueError(f"cannot determine the merge base of {head} with origin/main: {base.stderr.strip()}")
    changed = run_git(["diff", "--name-only", f"{base.stdout.strip()}...{head}"], cwd=root, check=False)
    if changed.returncode != 0:
        raise QueueError(f"cannot list the files changed by {head}: {changed.stderr.strip()}")
    return any(line.startswith("openspec/changes/") for line in changed.stdout.splitlines())


def _admission_handoff(root: Path, branch: str, head: str) -> dict[str, Any]:
    """Task-content identity for the admitted head.

    A managed candidate (managed task state present, or a head that touches an
    OpenSpec change) must carry exact task-content provenance from a checkout at
    the admitted head, or admission fails; it never degrades to quick-task
    branch/head identity. Only a candidate with neither marker is a quick task.
    """
    from task_content_identity import content_identity

    state = _managed_state(root)
    if state is None and not _touches_openspec_change(root, head):
        return {"task_identity": {"branch": branch, "head": head}, "gates": {}}

    def lacks(cause: str) -> QueueError:
        return QueueError(f"managed candidate {branch} lacks valid exact task-content provenance: {cause}")

    if state is None:
        raise lacks("the head changes an OpenSpec change but the checkout has no managed task state")
    local = run_git(["rev-parse", "HEAD"], cwd=root, check=False)
    if local.returncode != 0 or not local.stdout.strip():
        raise QueueError(f"cannot read the checkout HEAD: {local.stderr.strip()}")
    if local.stdout.strip() != head:
        raise lacks(f"the checkout is at {local.stdout.strip()}, not the admitted head {head}")
    change = state["change"]
    active = root / "openspec" / "changes" / change
    archives = [path for path in (root / "openspec" / "changes" / "archive").glob(f"*-{change}") if path.is_dir()]
    if not active.is_dir() and len(archives) != 1:
        raise lacks(f"change {change} has no unique active or archived package")
    proof = content_identity(root, change)
    digest = proof.get("digest") if isinstance(proof, dict) else None
    if not (isinstance(digest, str) and digest):
        raise lacks(f"no task-content proof could be computed for change {state['change']}")
    return {"task_identity": {"task_content": digest}, "gates": _archived_verification_gate(root)}


def _archived_verification_gate(root: Path) -> dict[str, Any]:
    """The archived automated-checks evidence of this managed task, as a satisfied gate.

    Admission itself proves no validation; it binds the gate the archive helper
    already recorded (successful outcome, the task content and head it ran on,
    and the evidence file digest). Absent or unsuccessful evidence claims no
    gate; unreadable or malformed evidence is an error.
    """
    import hashlib

    state = _managed_state(root)
    if state is None:
        return {}
    change = state["change"]
    matches = sorted((root / "openspec" / "changes" / "archive").glob(f"*-{change}/automated-checks.json"))
    if not matches:
        return {}
    if len(matches) != 1:
        raise QueueError(f"archived verification evidence for {change} is ambiguous: {len(matches)} files")
    path = matches[0].relative_to(root).as_posix()
    try:
        raw = matches[0].read_bytes()
        evidence = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QueueError(f"archived verification evidence {path} is unreadable or malformed: {exc}") from exc
    if not isinstance(evidence, dict):
        raise QueueError(f"archived verification evidence {path} is not a JSON object")
    checkout = evidence.get("managed_checkout")
    content = checkout.get("task_content") if isinstance(checkout, dict) else None
    outcome = evidence.get("outcome")
    digest = content.get("digest") if isinstance(content, dict) else None
    head = checkout.get("head") if isinstance(checkout, dict) else None
    if (outcome not in ("success", "failure")
            or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None):
        raise QueueError(f"archived verification evidence {path} has malformed outcome or managed-checkout identity")
    if outcome != "success":
        return {}
    return {"archived-verification": {
        "result": "passed",
        "identity": {"task_content": content["digest"], "head": head},
        "evidence": {"path": path, "sha256": hashlib.sha256(raw).hexdigest()},
    }}


def _handoff_route(root: Path, identity: Any) -> dict[str, str]:
    """Resolve the originating task route from the developer checkout's durable routing evidence."""
    import model_routing

    change = identity.get("change") if isinstance(identity, dict) else None
    if not isinstance(change, str) or not change:
        raise QueueError("handoff cannot resolve the originating task route: its task identity names no change")
    try:
        return model_routing.read_route_for_change(root, change)
    except model_routing.RoutingError as exc:
        raise QueueError(f"handoff cannot resolve the originating task route for {change}: {exc}") from exc


# Candidate states a fresh developer handoff for a new head may supersede: they wait on a human,
# a retry or an unclaimed head-bound job (which can never run once the head moved), not on an
# in-flight job. Every other state keeps the admitted head.
READMISSION_STATES = frozenset({"review-pending", "repair-pending", "blocked-retryable", "blocked-escalation"})
_SAME_TASK_KEYS = ("kind", "change", "requirement", "source_issue", "work_identity", "target_branch", "contribution_base")


def _material_findings(evidence: Any) -> bool:
    """Whether review-shaped evidence (``{perspective: {"findings": [...]}}``) holds a material finding."""
    return isinstance(evidence, dict) and any(
        isinstance(report, dict) and isinstance(report.get("findings"), list)
        and any(isinstance(finding, dict) and finding.get("severity") == "material" for finding in report["findings"])
        for report in evidence.values())


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    """Whether ``descendant`` contains ``ancestor`` (a fast-forward or a merge).

    Three-valued: exit 0 is an ancestor, exit 1 is not, and any other exit is a git failure that
    raises with the command, exit code and git's output instead of reading as "not an ancestor".
    """
    command = ["merge-base", "--is-ancestor", ancestor, descendant]
    done = run_git(command, cwd=root, check=False)
    if done.returncode == 0:
        return True
    if done.returncode == 1:
        return False
    raise QueueError(f"cannot prove that {descendant} descends from {ancestor}: git {' '.join(command)} "
                     f"exited {done.returncode}: " + (done.stderr or done.stdout).strip()[:200])


def _supersession(root: Path, repo: str, number: int, pr: dict[str, Any], proven: str, head: str,
                  identity: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """The explicit supersession of the admitted ``proven`` head by a developer handoff at ``head``.

    Returns the ``supersedes`` payload and the superseded lineage record.

    Allowed only when the latest trusted record is bound to the proven head in a state of
    ``READMISSION_STATES``, names the same task, and its offered job holds no live claim, and
    when ``head`` descends from ``proven``: coordinator updates and harness pushes on the
    admitted head are never discarded by a history rewrite. A finding-level escalation (a
    rejected review, a proposed rejection, exhausted repair rounds) or a record carrying
    material review findings is superseded only by changed task content, so an
    unchanged-content commit cannot re-roll the review; operational states need no change.
    Anything else is a named refusal.
    """
    from lifecycle_workers import CLAIM_PREFIX, build_job, winning_claim
    from pr_review_gate import OPERATIONAL_REPAIR_OUTCOMES, _repair_status

    def refuse(cause: str) -> QueueError:
        return QueueError(f"PR has an earlier or ambiguous admission at {proven[:12]}; "
                          f"re-admission of {head[:12]} refused: {cause}")

    comments = _comments(root, repo, number)
    if _malformed(_derive(root, pr, comments)):
        raise refuse("a coordinator record is malformed")
    lineage = _latest(root, number, comments)
    if lineage is None or lineage.get("head") != proven:
        raise refuse("the latest coordinator record is not bound to the admitted head")
    if lineage.get("state") not in READMISSION_STATES:
        raise refuse(f"the candidate is {lineage.get('state')}; only "
                     f"{', '.join(sorted(READMISSION_STATES))} accept a new developer head")
    old = lineage.get("task_identity")
    if (not isinstance(old, dict) or not old.get("change") or not isinstance(identity, dict)
            or any(old.get(key) != identity.get(key) for key in _SAME_TASK_KEYS)):
        raise refuse("the handoff does not name the same task as the admitted candidate")
    red = lineage.get("red_gate") or {}
    review = (lineage.get("gates") or {}).get("review") or {}
    finding_level = lineage["state"] == "blocked-escalation" and (
        red.get("name") == "review"
        or (red.get("name") == "repair" and _repair_status(red) not in OPERATIONAL_REPAIR_OUTCOMES))
    if finding_level or _material_findings(red.get("evidence")) or (
            review.get("result") == "failed" and _material_findings(review.get("evidence"))):
        # Findings are answered by changed content; an unchanged-content head would re-roll the review.
        what = (f"finding-level escalation ({'review' if red.get('name') == 'review' else _repair_status(red)})"
                if finding_level else "material review findings of the admitted head")
        def digest(value: Any) -> Any:
            content = value.get("task_content") if isinstance(value, dict) else None
            return content.get("digest") if isinstance(content, dict) else content
        if not digest(old) or not digest(identity):
            raise refuse(f"re-admitting over the {what} needs task-content digests to prove changed task content")
        if digest(old) == digest(identity):
            raise refuse(f"re-admitting over the {what} needs changed task content; the handoff carries the same content")
    job = build_job({**lineage, "number": number})
    if job is not None:
        claim = winning_claim(job, comments, trusted_apps=trusted_apps(root),
                              trusted_writers=trusted_writers(root, comments, (CLAIM_PREFIX,), repo=repo))
        if claim is not None:
            raise refuse(f"its {job['kind']} job is claimed by {claim['worker']} until {claim['expires_at']}")
    if not _is_ancestor(root, proven, head):
        raise refuse("the new head does not descend from the admitted head; push a fast-forward or merge, not a rewrite")
    return {"head": proven, "state": lineage["state"], "reason": "fresh developer handoff for a descendant head"}, lineage


def _carried_gates(root: Path, lineage: dict[str, Any], identity: dict[str, Any], handoff_gates: dict[str, Any]) -> dict[str, Any]:
    """Lineage gates still provably bound to the re-admitted identity, rebound to it.

    ``required-checks`` is bound to an integration head and main, and fresh handoff evidence
    wins, so neither is carried. Only passed gates are reusable, so a failed review never is.
    """
    from pr_review_gate import reusable

    gates = lineage.get("gates") or {}
    if not isinstance(gates, dict):
        raise QueueError("superseded coordinator record has malformed gates")
    return {name: {**gate, "identity": identity} for name, gate in gates.items()
            if name != "required-checks" and name not in handoff_gates and reusable(root, gate, identity)}


def _awaiting_readmission(root: Path, repo: str, number: int, pr: dict[str, Any], comments: list[dict[str, Any]],
                          admission: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The pushed head that awaits developer re-admission, or ``None``.

    That is a PR head moved away from the admitted (proven) head while the newest trusted
    record there is in ``READMISSION_STATES``; the coordinator neither integrates nor blocks it.
    """
    newest = _latest(root, number, comments)
    if newest is None:
        return None  # legitimate absence: no trusted record, so nothing awaits re-admission
    head = pr.get("head", {}).get("sha")
    if newest.get("state") not in READMISSION_STATES or newest.get("head") == head:
        return None
    if admission is None:
        admission = _admission(_events(root, repo, number), number)
    if admission is None or newest.get("head") != _proven_head(_events(root, repo, number), admission):
        return None
    return {"reason": f"new head awaits developer re-admission (proven head {newest['head']}, PR head {head})",
            "state": newest["state"], "proven_head": newest["head"], "head": head}


def _earlier_slot_record(root: Path, repo: str, number: int, comments: list[dict[str, Any]], head: str,
                         admission: dict[str, Any]) -> bool:
    """Whether the exact-head record belongs to an earlier admission slot than ``admission``.

    It does when it was written before the admission comment, or when it is the
    ``blocked-escalation`` projection of a v1 block that the admission follows (``_block``
    writes the v1 block first, so its projection may land after the admission).
    """
    record_id = _record_comment_id(root, number, comments, head)
    if record_id is None:
        return False
    if record_id < admission["comment_id"]:
        return True
    record = _latest(root, number, comments, head)
    if record is None:
        # `_record_comment_id` just found a trusted record for this head; its disappearance is a lost record.
        raise QueueError(f"PR #{number} record at {head[:12]} (comment {record_id}) is no longer readable")
    blocks = [event["comment_id"] for event in _events(root, repo, number)
              if event.get("kind") == "block" and isinstance(event.get("comment_id"), int)]
    return (record.get("state") == "blocked-escalation" and (record.get("red_gate") or {}).get("name") == "publication"
            and bool(blocks) and max(blocks) < admission["comment_id"])


def _require_handoff_progress(root: Path, repo: str, number: int, head: str, admission: dict[str, Any]) -> None:
    """A developer handoff reports success only once this admission reached review at the exact head.

    The exact-head record must belong to this admission slot and be ``review-pending`` with its
    published review job, or later lifecycle progress; a blocked candidate or a missing job raises.
    """
    from lifecycle_workers import build_job

    comments = _comments(root, repo, number)
    candidate = _derive(root, _pr(root, repo, number), comments)
    state = candidate.get("state")
    if candidate.get("head") != head or _earlier_slot_record(root, repo, number, comments, head, admission):
        raise QueueError(f"developer handoff for PR #{number} is not recorded at {head[:12]} for this admission")
    published = candidate.get("next_job") if isinstance(candidate.get("next_job"), dict) else {}
    if state == "review-pending" and (published.get("kind") != "review" or build_job(candidate) is None):
        raise QueueError(f"developer handoff for PR #{number} is review-pending without a published review job; rerun finish")
    if state == "blocked-escalation" or (state == "blocked-retryable" and not review_owned(candidate)):
        raise QueueError(f"developer handoff for PR #{number} did not reach review: candidate is {state}: "
                         f"{candidate.get('reason') or (candidate.get('red_gate') or {}).get('evidence')}")


def admit(root: Path, number: int, expected_head: str, *, handoff: dict | None = None) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    identity = (handoff or {}).get("task_identity", {})
    target = identity.get("target_branch", "main") if isinstance(identity, dict) else "main"
    if pr.get("state") != "open" or pr.get("base", {}).get("ref") != target or pr.get("head", {}).get("sha") != expected_head:
        raise QueueError("queue admission requires one open PR at the exact validated head against main")
    branch = pr.get("head", {}).get("ref")
    if isinstance(branch, str) and branch.startswith("requirement/BR-") and not handoff:
        composed = _latest(root, number, _comments(root, repo, number), expected_head)
        if composed is None:
            raise QueueError(f"requirement composition PR #{number} has no trusted coordinator record at {expected_head[:12]}; "
                             "re-run the composition handoff")
        identity = composed.get("task_identity", {})
    if not isinstance(branch, str) or not (branch.startswith("agent/")
        or (identity.get("kind") == "requirement-composition" and branch.startswith("requirement/BR-"))):
        raise QueueError("queue admission requires an owned task branch")
    if target == "main" and branch.startswith("requirement/BR-"):
        resolved_handoff = require_composition_finalized(root, repo, number, expected_head)
    else:
        resolved_handoff = handoff if handoff is not None else _admission_handoff(root, branch, expected_head)
    route = _handoff_route(root, identity) if handoff else None
    events = _events(root, repo, number)
    admitted = _admission(events, number)
    if admitted and handoff:
        prior = _latest(root, number, _comments(root, repo, number))
        old_identity = prior.get("task_identity") if prior else None
        keys = ("kind", "change", "requirement", "source_issue", "work_identity", "target_branch", "contribution_base")
        proven = _proven_head(events, admitted)
        if (prior and prior.get("head") == proven and prior.get("head") != expected_head
                and prior.get("state") == "blocked-retryable"
                and (prior.get("red_gate") or {}).get("name") == "semantic-verification"
                and isinstance(old_identity, dict) and old_identity.get("kind") == "contribution"
                and all(old_identity.get(k) == identity.get(k) for k in keys)
                and prior["red_gate"].get("identity") == old_identity
                and handoff.get("gates", {}).get("developer-friction", {}).get("evidence", {}).get("head") == expected_head
                and all(handoff.get("gates", {}).get(g, {}).get("result") == "passed"
                        and handoff["gates"][g].get("identity") == identity
                        and handoff["gates"][g].get("evidence")
                        for g in ("developer-friction", "selected-checks", "semantic-verification"))):
            _comment(root, repo, number, {"kind": "block", "head": prior["head"],
                                        "reason": "fresh semantic-verification developer handoff"})
            events = _events(root, repo, number)
            admitted = _admission(events, number)
            if admitted is not None:
                raise QueueError("semantic-verification admission reset was not confirmed")
    if admitted:
        proven = _proven_head(events, admitted)
        if proven != expected_head and not handoff:
            raise QueueError("PR has an earlier or ambiguous admission; resolve it before re-admission")
        if proven != expected_head:
            supersedes, _ = _supersession(root, repo, number, pr, str(proven), expected_head, identity)
            handoff_gates = resolved_handoff.get("gates")
            if not isinstance(handoff_gates, dict):
                raise QueueError("re-admission handoff carries no gates")
            base = identity["contribution_base"] if identity.get("kind") == "contribution" else _main(root)
            # Off the queue until the fresh review record exists: no worker integrates the unreviewed head.
            _label(root, repo, number, QUEUE, present=False)
            _comment(root, repo, number, {"kind": "admit", "head": expected_head, "base": base, "branch": branch,
                                          "supersedes": supersedes})
            admitted = _admission(_events(root, repo, number), number)
            if admitted is None or admitted.get("head") != expected_head:
                raise QueueError("superseding admission comment was not confirmed")
            _label(root, repo, number, BLOCKED, present=False)
    else:
        base = identity["contribution_base"] if identity.get("kind") == "contribution" else _main(root)
        _ensure_labels(root)
        _comment(root, repo, number, {"kind": "admit", "head": expected_head, "base": base, "branch": branch})
        admitted = _admission(_events(root, repo, number), number)
        if admitted is None or admitted.get("head") != expected_head:
            raise QueueError("admission comment was not confirmed")
        _label(root, repo, number, BLOCKED, present=False)
    # A retry after an interrupted admission recovers the missing record, but never
    # rewinds a candidate that later lifecycle work already advanced on this head.
    comments = _comments(root, repo, number)
    current = _derive(root, _pr(root, repo, number), comments)
    stale = _earlier_slot_record(root, repo, number, comments, expected_head, admitted)
    if current.get("task_identity") is None or current.get("head") != expected_head or stale:
        # Recover carry-forward from the persisted supersession even when an earlier
        # attempt published admission but stopped before writing the review record.
        supersedes = admitted.get("supersedes")
        if handoff and isinstance(supersedes, dict):
            lineage = _latest(root, number, comments, supersedes["head"])
            if lineage is None:
                raise QueueError(f"PR #{number} supersedes {str(supersedes['head'])[:12]} but its lineage record is missing; "
                                 "carry-forward of its gates cannot be proven")
            handoff_gates = resolved_handoff.get("gates")
            if not isinstance(handoff_gates, dict):
                raise QueueError("re-admission handoff carries no gates")
            resolved_handoff = {**resolved_handoff,
                                "gates": {**_carried_gates(root, lineage, identity, handoff_gates), **handoff_gates}}
        try:
            # A record of an earlier slot (written before this admission, or the projection of a
            # block this admission follows) is never later lifecycle work: only claims refuse.
            _transition(root, repo, number, "review-pending" if handoff else "ready", expected_head, inherit_identity=False,
                        refuse_from=CLAIM_STATES if stale else STATES, route=route, **resolved_handoff)
        except LifecycleOwnershipChanged:
            pass  # lifecycle work recorded this head in the meantime; never rewind it
    if handoff:
        comments = _comments(root, repo, number)
        confirmed = _latest(root, number, comments, expected_head)
        if confirmed is None or _pr(root, repo, number).get("head", {}).get("sha") != expected_head:
            raise QueueError("developer handoff admission is not confirmed at the exact PR head")
        if confirmed["state"] == "review-pending":
            publish_job(root, repo, number, "review", expected_head, task_identity=handoff["task_identity"])
        _require_handoff_progress(root, repo, number, expected_head, admitted)
    _label(root, repo, number, QUEUE, present=True)
    return {"number": number, "position_key": admitted["comment_id"], "head": expected_head, "state": "queued"}


QUEUE_INVENTORY_LIMIT = 300
MAX_MERGE_REFUSALS = 3


def _queued(root: Path, repo: str, skipped: list[str] | None = None) -> list[tuple[int, int, dict[str, Any]]]:
    """Admitted queued PRs in admission order; a labeled PR without a valid admission is listed in ``skipped``."""
    # Filter remotely before bounding. Merged queued contributions still need
    # recovery if the worker stopped between GitHub merge and manifest publication.
    rows = _gh(root, "pr", "list", "--state", "all", "--label", QUEUE, "--limit", str(QUEUE_INVENTORY_LIMIT),
               "--json", "number,labels")
    if not isinstance(rows, list) or len(rows) >= QUEUE_INVENTORY_LIMIT:
        raise QueueError("queued PR inventory is unavailable or exceeds the bounded limit")
    queue = []
    for row in rows:
        if not isinstance(row, dict) or QUEUE not in {label.get("name") for label in row.get("labels", []) if isinstance(label, dict)}:
            continue
        number = row.get("number")
        if not isinstance(number, int):
            raise QueueError("queued PR has no number")
        try:
            admission = _admission(_events(root, repo, number), number)
        except QueueError as exc:
            admission, cause = None, str(exc)
        else:
            cause = "lacks a valid admission"
        if admission is None:
            # One PR's label without an admission never stops the queue for the others.
            if skipped is not None:
                skipped.append(f"#{number} queued but {cause}"[:300])
            continue
        queue.append((admission["comment_id"], number, admission))
    return sorted(queue)


def status(root: Path, number: int) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    events = _events(root, repo, number)
    admission = _admission(events, number)
    if admission is None:
        blocks = [event for event in events if event.get("kind") == "block"]
        if blocks:
            return {"state": "blocked", "number": number, "reason": blocks[-1].get("reason", "unknown")}
        return {"state": "not-admitted", "number": number}
    if pr.get("merged") or pr.get("state") == "closed":
        return {"state": "merged" if pr.get("merged") else "blocked", "number": number, "reason": "PR closed without merge" if not pr.get("merged") else ""}
    blocks = [e for e in events if e.get("kind") == "block" and e.get("comment_id", 0) > admission["comment_id"]]
    if blocks:
        return {"state": "blocked", "number": number, "reason": blocks[-1].get("reason", "unknown")}
    labels = {label.get("name") for label in pr.get("labels", []) if isinstance(label, dict)}
    queue = _queued(root, repo)
    # The inventory comes from GitHub search, which indexes a just-added queue
    # label with a delay; this PR's own label set is read directly and is
    # authoritative for its membership, so admission is never misreported as
    # "lacks queue label" while the index catches up.
    if QUEUE in labels and number not in {candidate for _, candidate, _ in queue}:
        queue = sorted([*queue, (admission["comment_id"], number, admission)])
    for index, (_, candidate, _) in enumerate(queue, 1):
        if candidate == number:
            awaiting = _awaiting_readmission(root, repo, number, pr, _comments(root, repo, number), admission)
            if awaiting is not None:
                # Kept "waiting" for existing consumers; the reason names the developer action it waits on.
                return {"state": "waiting", "number": number, "position": index, "owner": "developer re-admission",
                        "reason": awaiting["reason"], "proven_head": awaiting["proven_head"], "head": awaiting["head"]}
            active = index == 1 and ACTIVE in labels
            return {"state": "active" if active else "waiting", "number": number, "position": index, "owner": "publication-queue workflow" if active else None}
    return {"state": "blocked", "number": number, "reason": "admitted PR lacks queue label"}


def observe_checks(root: Path, number: int, head: str) -> dict[str, Any]:
    """Exact-head required-check snapshot of a candidate."""
    # The shared classifier resolves the required set from the final protected
    # target and binds the snapshot to this head before and after reading.
    observed = required_check_state_for_ref(root, os.environ.copy(), str(number), head)
    checks = {"head": None if observed.cause == "head-mismatch" else head, "kind": observed.kind,
              "detail": observed.detail, "checks": list(observed.checks)}
    if observed.cause:
        checks["cause"] = observed.cause
    return checks


def candidate_from_snapshot(root: Path, repo: str, pr: dict[str, Any], comments: list[dict[str, Any]],
                            checks: dict[str, Any] | None) -> dict[str, Any]:
    """Derive a candidate from an already observed PR, comment history and optional checks snapshot."""
    candidate = _derive(root, pr, comments, checks)
    awaiting = _awaiting_readmission(root, repo, pr["number"], pr, comments)
    if awaiting is not None:
        candidate.update(reason=awaiting["reason"], awaiting_readmission=awaiting,
                         next_action="developer re-admission: rerun finish for the pushed head")
    return candidate


def candidate_status(root: Path, number: int, *, repo: str | None = None) -> dict[str, Any]:
    """Observe a lifecycle handoff without changing v1 queue consumers."""
    repo = repo or _repo(root)
    pr = _pr(root, repo, number)
    comments = _comments(root, repo, number)
    head = pr.get("head", {}).get("sha", "")
    return candidate_from_snapshot(root, repo, pr, comments, observe_checks(root, number, head))


def lifecycle_summary(root: Path, number: int) -> dict[str, Any]:
    """Compact derived lifecycle state for task status, including exact-head checks."""
    candidate = candidate_status(root, number)
    return {key: candidate.get(key) for key in ("state", "head", "red_gate", "attempts", "next_action", "reason")}


def _requirement_candidate_numbers(root: Path, requirement: str, repo: str) -> tuple[list[int], str | None]:
    """Candidate PR numbers of a Requirement (shared candidates plus child branches) and a lineage note."""
    from requirement_integration import ISSUE_RE, _candidate_slug

    if not ISSUE_RE.fullmatch(requirement):
        raise QueueError("Requirement must be owner/repository#number")
    public_requirement: str | None = requirement
    lineage_note: str | None = None
    import private_lineage

    if private_lineage.enabled(root):
        try:
            public_requirement = private_lineage.handle_for_issue(
                root, requirement, "requirement-integration", create=False)
        except private_lineage.PrivateLineageError as exc:
            # No resolvable shared candidate lineage (single child, not yet
            # composed, or a lookup failure): child branches are still listed and
            # the missing shared lineage is reported, never silently omitted.
            public_requirement = None
            lineage_note = f"shared candidate lineage unavailable: {exc}"
    branch = "agent/" + _candidate_slug(public_requirement) if public_requirement else None
    # Candidate generations keep their PRs after their branches are deleted, so
    # the repository's PR list is read in full (paginated, filtered server-side
    # output) rather than inferred from live branches or one bounded page.
    listed = subprocess.run(
        ["gh", "api", "--paginate", f"repos/{repo}/pulls?state=all&per_page=100", "--jq", ".[] | [.number, .head.ref] | @tsv"],
        cwd=root, text=True, capture_output=True, check=False,
        stdin=subprocess.DEVNULL,
    )
    if listed.returncode:
        raise QueueError(listed.stderr.strip() or "Requirement candidate inventory is unavailable")
    # Shared candidates plus the Requirement's own child branches, which carry a
    # single-child (or not yet composed) publication directly.
    from managed_work_identity import parent_identity

    child_prefix = "agent/" + parent_identity(requirement).lower() + "-t"
    children = re.escape(child_prefix) + r"[1-9][0-9]*-[A-Za-z0-9][A-Za-z0-9._-]*"
    shared = re.escape("requirement/" + parent_identity(requirement))
    legacy = re.escape(branch) + r"(?:-[0-9a-f]{12})?|" if branch else ""
    pattern = re.compile(legacy + shared + "|" + children)
    numbers = sorted({int(number) for number, _, ref in (line.partition("\t") for line in listed.stdout.splitlines())
                      if number.isdigit() and pattern.fullmatch(ref)})
    return numbers, lineage_note


def requirement_status(root: Path, requirement: str) -> dict[str, Any]:
    """List shared candidate generations by canonical branch identity, read-only."""
    repo = _repo(root)
    numbers, lineage_note = _requirement_candidate_numbers(root, requirement, repo)
    result: dict[str, Any] = {"requirement": requirement, "candidates": [candidate_status(root, number, repo=repo) for number in numbers]}
    if lineage_note:
        result["shared_lineage"] = lineage_note
    return result


def local_status(root: Path, branch: str) -> dict[str, Any] | None:
    """Observe this task's admitted PR even after the coordinator updates its head."""
    from _platform_common import run_github_with_retry

    result = run_github_with_retry(["gh", "pr", "view", branch, "--json", "number,baseRefName,headRefName"], cwd=root)
    if result.returncode:
        candidates = _gh(root, "pr", "list", "--state", "all", "--head", branch,
                         "--limit", "100", "--json", "number,baseRefName,headRefName")
        if not isinstance(candidates, list) or len(candidates) >= 100:
            raise QueueError("task PR inventory is unavailable or exceeds the bounded page")
        matches = [candidate for candidate in candidates if candidate.get("baseRefName") == "main"
                   and candidate.get("headRefName") == branch and isinstance(candidate.get("number"), int)]
        admitted = [candidate for candidate in matches
                    if any(event.get("kind") == "admit" for event in _events(root, _repo(root), candidate["number"]))]
        if len(admitted) > 1:
            raise QueueError("multiple admitted task PRs use the same branch")
        if not admitted:
            return None
        data = admitted[0]
    else:
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise QueueError("task PR lookup returned invalid JSON") from None
    if data.get("baseRefName") != "main" or data.get("headRefName") != branch or not isinstance(data.get("number"), int):
        return None
    repo = _repo(root)
    events = _events(root, repo, data["number"])
    admission = _admission(events, data["number"])
    if admission is None:
        old = [event for event in events if event.get("kind") == "admit"]
        local_head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
        if old and old[-1].get("head") == local_head:
            return status(root, data["number"])
        return None
    local_head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    if admission.get("head") != local_head:
        # After local fast-forward recovery the current head is a coordinator
        # descendant, so a matching update marker is also accepted.
        updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
        if not updates or updates[-1].get("head") != local_head:
            observed = status(root, data["number"])
            # A developer head already pushed (for example by reconcile) awaits this
            # finish's re-admission; admission's supersession proves it descends from the proven head.
            if observed.get("owner") == "developer re-admission" and observed.get("head") == local_head:
                return {**observed, "state": "readmission"}
            raise QueueError("local task head is not the admitted or proven coordinator head")
    return status(root, data["number"])


def semantic_readmission(root: Path, branch: str) -> dict[str, Any] | None:
    """This branch's admitted PR when it awaits a fresh semantic-verification handoff of the local head.

    Only a candidate whose proven head stopped ``blocked-retryable`` on the
    ``semantic-verification`` red gate, and whose PR head is exactly the local
    head awaiting developer re-admission, qualifies; anything else is ``None``.
    """
    observed = local_status(root, branch)
    if observed is None or observed.get("state") != "readmission":
        return None
    number = observed["number"]
    lineage = _latest(root, number, _comments(root, _repo(root), number), observed["proven_head"])
    if (lineage is None or lineage.get("state") != "blocked-retryable"
            or (lineage.get("red_gate") or {}).get("name") != "semantic-verification"):
        return None
    return {**observed, "lineage": lineage}


def sync_merged_task(root: Path, branch: str, number: int) -> None:
    """Fast-forward only this clean task branch to its proven merged PR head."""
    repo = _repo(root)
    pr = _pr(root, repo, number)
    if not pr.get("merged") or pr.get("head", {}).get("ref") != branch:
        raise QueueError("exact task PR is not confirmed merged")
    remote_head = pr.get("head", {}).get("sha")
    events = _events(root, repo, number)
    admission = _admission(events, number)
    updates = [e for e in events if e.get("kind") == "update" and admission and e.get("comment_id", 0) > admission["comment_id"]]
    proven = updates[-1].get("head") if updates else admission.get("head") if admission else None
    if remote_head != proven:
        raise QueueError("merged PR head lacks coordinator update proof")
    local = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    if local == remote_head:
        return
    if run_git(["status", "--porcelain"], cwd=root).stdout.strip():
        raise QueueError("task worktree is dirty; cannot synchronize merged PR head")
    run_git(["fetch", "origin", f"pull/{number}/head"], cwd=root)
    if run_git(["rev-parse", "FETCH_HEAD"], cwd=root).stdout.strip() != remote_head:
        raise QueueError("fetched PR head differs from GitHub observation")
    if not _is_ancestor(root, local, remote_head):
        raise QueueError("coordinator head does not descend from local task head")
    run_git(["merge", "--ff-only", remote_head], cwd=root)


def _block(root: Path, repo: str, number: int, reason: str, *, head: str | None = None) -> dict[str, Any]:
    _comment(root, repo, number, {"kind": "block", "reason": reason[:500]})
    # Dequeue first: the v1 block already invalidated the admission, so a queued
    # label left behind would stall every later candidate's inventory.
    _label(root, repo, number, BLOCKED, present=True)
    _label(root, repo, number, ACTIVE, present=False)
    _label(root, repo, number, QUEUE, present=False)
    if head is None:
        observed = _pr(root, repo, number).get("head", {})
        head = observed.get("sha") if isinstance(observed, dict) else None
    if isinstance(head, str) and len(head) == 40:
        try:
            # The blocked head may be unproven (changed outside the coordinator), so
            # it never inherits the previous candidate's task-content identity.
            _transition(root, repo, number, "blocked-escalation", head, task_identity={"head": head},
                        inherit_identity=False,
                        red_gate={"name": "publication", "identity": head, "evidence": reason[:500]})
        except QueueError:
            pass  # status still derives the block from the v1 marker written above
    return {"state": "blocked", "number": number, "reason": reason}


def _task_paths(root: Path, repo: str, admission: dict[str, Any]) -> set[str]:
    # PR files include prior coordinator main merges. Compare immutable admission
    # endpoints so later unrelated main changes do not look task-owned.
    base, head = admission.get("base"), admission.get("head")
    if not all(isinstance(value, str) and len(value) == 40 for value in (base, head)):
        raise QueueError("admission endpoints are invalid")
    response = _gh(root, "api", f"repos/{repo}/compare/{base}...{head}")
    rows = response.get("files") if isinstance(response, dict) else None
    if not isinstance(rows, list) or len(rows) >= 300:
        raise QueueError("admitted task file inventory is unavailable or exceeds the bounded limit")
    paths = {row.get("filename") for row in rows if isinstance(row, dict)}
    if not paths or not all(isinstance(path, str) for path in paths):
        raise QueueError("PR has no provable task paths")
    return paths


def _require_finalized(root: Path, number: int, head: str) -> None:
    """Integration admission and merge need every completed OpenSpec change archived at the exact head."""
    run_git(["fetch", "origin", f"pull/{number}/head"], cwd=root)
    if run_git(["rev-parse", "FETCH_HEAD"], cwd=root).stdout.strip() != head:
        raise QueueError("fetched PR head differs from GitHub observation")
    from openspec_lifecycle import completed_active_changes_at

    try:
        stale = completed_active_changes_at(root, head)
    except SystemExit as exc:
        raise QueueError(str(exc)) from exc
    if stale:
        raise NotFinalized("completed OpenSpec change is still active at integration: " + ", ".join(stale)
                         + "; verify and archive it (finalization) before integration")


def _prepare(root: Path, repo: str, number: int, admission: dict[str, Any], pr: dict[str, Any]) -> tuple[str, str]:
    head = pr.get("head", {}).get("sha")
    if not isinstance(head, str) or len(head) != 40:
        raise QueueError("PR head is unavailable")
    events = _events(root, repo, number)
    updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
    proven = admission.get("head") if not updates else updates[-1].get("head")
    if pr.get("head", {}).get("ref", "").startswith("requirement/BR-"):
        require_composition_finalized(root, repo, number, head, through_update=True)
    if head != proven:
        # A runner can die after GitHub updates the branch but before it writes
        # the update comment. Recover only a clean merge of proven head + main.
        run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
        parents = run_git(["rev-list", "--parents", "-n", "1", head], cwd=root).stdout.split()
        if len(parents) != 3 or parents[1] != proven:
            raise QueueError("PR head changed outside coordinator control")
        prior_main = parents[2]
        run_git(["fetch", "origin", "main"], cwd=root)
        if not _is_ancestor(root, prior_main, "origin/main"):
            raise QueueError("unrecorded branch update is not based on main")
        expected_tree = run_git(["merge-tree", "--write-tree", proven, prior_main], cwd=root, check=False)
        actual_tree = run_git(["rev-parse", f"{head}^{{tree}}"], cwd=root).stdout.strip()
        if expected_tree.returncode or expected_tree.stdout.splitlines()[0].strip() != actual_tree:
            # A re-derivation push whose update marker was lost: accept only that exact shape.
            from _platform_common import generated_files
            from post_review_finalization import derived_merge_only

            declared = [item.path for item in generated_files(root, "HEAD")]
            if not derived_merge_only(root, head, proven, prior_main, _task_paths(root, repo, admission), declared):
                raise QueueError("unrecorded branch update is not a clean main merge")
        _comment(root, repo, number, {"kind": "update", "previous": proven, "head": head, "base": prior_main})
    base = admission.get("base")
    if not isinstance(base, str) or len(base) != 40:
        raise QueueError("admission base is invalid")
    current_main = _main(root)
    if current_main == base and head == admission.get("head"):
        # The admission base is main as observed at admission, not proof that the head contains
        # it (a Requirement composition head can be admitted on an older main): check ancestry.
        run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
        if _is_ancestor(root, current_main, head):
            return head, current_main
    run_git(["fetch", "origin", "main"], cwd=root)
    if not _is_ancestor(root, base, current_main):
        raise QueueError("main no longer descends from admitted base")
    changed = set(run_git(["diff", "--name-only", f"{base}..{current_main}"], cwd=root).stdout.splitlines())
    task_paths = _task_paths(root, repo, admission)
    overlap = changed & task_paths
    from _platform_common import generated_files
    from post_review_finalization import (RederivationEnvironmentFailed, RederivationFailed, derived_spec_paths,
                                          prepare_derived_specs)

    # The declaration comes from the queue's own default-branch checkout, never from the candidate.
    generated = {item.path for item in generated_files(root, "HEAD")}
    derived = derived_spec_paths(task_paths, overlap)
    run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
    # If the previously prepared head already contains current main, do not
    # perform a redundant update or trigger another CI run.
    if _is_ancestor(root, current_main, head):
        return head, current_main
    # Derived merge when main changed a declared generated file the task also changed, or only
    # derived paths overlap main (existing), or the merge conflicts only in derived paths.
    route = bool(generated & overlap) or (bool(derived) and overlap == derived)
    if not route:
        # Path overlap alone never blocks: a clean merge is judged by the merge result and the
        # checks on the actual merged candidate; a real conflict becomes integration repair.
        conflicts = merge_conflicts(root, head, current_main)
        if conflicts and set(conflicts) <= derived_spec_paths(task_paths, set(conflicts)) | generated:
            route = True
        elif conflicts:
            raise IntegrationRepairNeeded("merge of current main conflicts in: " + ", ".join(conflicts[:8]))
    if route:
        # Re-derive archive-derived specs and regenerate declared generated files on the actual
        # base. A failure is integration repair; checks still run on the result.
        _raise_if_owned_elsewhere(root, repo, number, head)
        try:
            return prepare_derived_specs(root, repo, number, pr, head, task_paths)
        except RederivationEnvironmentFailed as exc:
            raise QueueEnvironmentError(f"PR #{number} derived merge cannot run on this coordinator: {exc}") from exc
        except RederivationFailed as exc:
            raise IntegrationRepairNeeded(f"derived merge (archive-derived specs, generated files) failed: {exc}",
                                          merge_only=not merge_conflicts(root, head, current_main)) from exc
    # Last observation before mutating the branch: never update a head that review or repair
    # claimed meanwhile (atomic job claims arrive with the worker contract).
    _raise_if_owned_elsewhere(root, repo, number, head)
    try:
        _gh(root, "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/update-branch", data={"expected_head_sha": head})
    except QueueError as exc:
        if "conflict" in str(exc).lower():
            raise IntegrationRepairNeeded(f"GitHub could not merge current main cleanly: {exc}") from exc
        raise
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        observed = _pr(root, repo, number).get("head", {}).get("sha")
        if isinstance(observed, str) and observed != head:
            _comment(root, repo, number, {"kind": "update", "previous": head, "head": observed, "base": current_main})
            return observed, current_main
        time.sleep(3)
    raise TransientQueueError("GitHub branch update is still pending; retry coordinator")


def merge_conflicts(root: Path, head: str, main: str) -> list[str]:
    """Paths a deterministic merge of ``main`` into ``head`` cannot resolve (empty means a clean merge)."""
    done = run_git(["merge-tree", "--write-tree", "--name-only", "--no-messages", head, main], cwd=root, check=False)
    if done.returncode == 0:
        return []
    if done.returncode == 1:
        names = [line.strip() for line in done.stdout.splitlines()[1:] if line.strip()]
        return names or ["(conflict paths unavailable)"]
    raise QueueError("cannot evaluate the merge of main: " + (done.stderr or done.stdout).strip()[:200])


# ---- coordinator configuration preflight ------------------------------------

PREFLIGHT_MODES = ("ci", "local")
PREFLIGHT_PHASES = ("inputs", "runtime", "all")
_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class PreflightFailure(Exception):
    """A required coordinator input is missing or contradictory; carries only names and categories."""

    def __init__(self, name: str, detail: str):
        super().__init__(f"{name}: {detail}")
        self.name, self.detail = name, detail


def _probe(root: Path, name: str, *args: str) -> Any:
    """A read-only GitHub probe; failures are classified without echoing any response."""
    try:
        return _gh(root, *args)
    except QueueError as exc:
        text = str(exc)
        if re.search(r"\b(401|403)\b|Bad credentials|Resource not accessible", text):
            category = "unauthorized"
        elif re.search(r"\b404\b|Not Found", text):
            category = "not-found"
        else:
            category = "unreachable"
        raise PreflightFailure(name, f"GitHub probe failed: {category}") from None


def _require_tools(env: Mapping[str, str]) -> None:
    import shutil

    for tool in ("gh", "git"):
        if shutil.which(tool, path=env.get("PATH")) is None:
            raise PreflightFailure(f"tool:{tool}", "required executable is not available")
    if sys.version_info < (3, 11):
        raise PreflightFailure("tool:python", "Python 3.11 or newer (tomllib) is required")


def _preflight_inputs(root: Path, mode: str, env: Mapping[str, str]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    def ok(name: str, detail: str) -> None:
        checks.append({"name": name, "status": "ok", "detail": detail})

    if mode == "ci":
        for flag in ("PREFLIGHT_APP_CLIENT_ID_SET", "PREFLIGHT_APP_PRIVATE_KEY_SET"):
            if env.get(flag) != "true":
                raise PreflightFailure(flag, "must be exactly 'true'; the variable or secret behind it is not configured")
            ok(flag, "set")
        if not _REPOSITORY.fullmatch(env.get("GITHUB_REPOSITORY", "")):
            raise PreflightFailure("GITHUB_REPOSITORY", "missing or not owner/name")
        ok("GITHUB_REPOSITORY", "well formed")
        for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            if not re.fullmatch(r"[1-9][0-9]*", env.get(name, "")):
                raise PreflightFailure(name, "missing or not a positive integer")
            ok(name, "well formed")
    _require_tools(env)
    ok("tools", "gh, git and Python 3.11 are available")
    if mode == "local":
        result = subprocess.run(["gh", "auth", "status"], cwd=root, capture_output=True, check=False, stdin=subprocess.DEVNULL)
        if result.returncode:
            raise PreflightFailure("gh-auth", "gh is not authenticated (run gh auth login)")
        ok("gh-auth", "authenticated")
    return checks


def _resolve_app_identity(root: Path, mode: str, env: Mapping[str, str]) -> tuple[str, list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    from_env = env.get(COORDINATOR_APP_ENV, "").strip()
    try:
        configured = configured_coordinator_apps(root)
    except QueueError as exc:
        raise PreflightFailure("trust-configuration", str(exc)) from exc
    if mode == "ci":
        if not from_env:
            raise PreflightFailure(COORDINATOR_APP_ENV, "empty; the App token step did not export an App slug")
        if not _SLUG.fullmatch(from_env):
            raise PreflightFailure(COORDINATOR_APP_ENV, "is not a valid GitHub App slug")
    elif not configured:
        raise PreflightFailure("[publication] coordinator_app", "must be configured in operator or project config for a local run")
    identities = {from_env, *(app for _, app in configured)} - {""}
    if len(identities) != 1:
        sources = ", ".join(f"{source} names {app}" for source, app in configured) or "no configuration names one"
        raise PreflightFailure("coordinator App identity", f"contradiction: environment names {from_env or 'none'}, {sources}")
    identity = next(iter(identities))
    if not _SLUG.fullmatch(identity):
        raise PreflightFailure("[publication] coordinator_app", "is not a valid GitHub App slug")
    checks.append({"name": "coordinator-app", "status": "ok", "detail": f"identity {identity}"})
    return identity, checks


def _preflight_runtime(root: Path, mode: str, env: Mapping[str, str]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    def ok(name: str, detail: str) -> None:
        checks.append({"name": name, "status": "ok", "detail": detail})

    if mode == "ci":
        if not env.get("GH_TOKEN"):
            raise PreflightFailure("GH_TOKEN", "empty; the App token step did not produce a token")
        ok("GH_TOKEN", "present")
    identity, found = _resolve_app_identity(root, mode, env)
    checks.extend(found)
    try:
        trusted = trusted_apps(root)
    except QueueError as exc:
        raise PreflightFailure("trust-configuration", str(exc)) from exc
    if identity not in trusted:
        raise PreflightFailure("trust-configuration", "trusted App set does not contain the coordinator App identity")
    ok("trust-configuration", "readable and contains the coordinator App")
    try:
        is_enabled = enabled(root)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise PreflightFailure("platform-config", f"cannot determine whether the coordinator is enabled ({type(exc).__name__})") from None
    if not is_enabled:
        raise PreflightFailure("coordinator-enabled", "this repository is not a source repository with the publication workflow on origin/main")
    ok("coordinator-enabled", "enabled")
    try:
        repo = _repo(root)
    except QueueError:
        raise PreflightFailure("repository", "GitHub repository identity is unavailable") from None
    if mode == "ci" and repo != env.get("GITHUB_REPOSITORY"):
        raise PreflightFailure("GITHUB_REPOSITORY", f"checkout repository {repo} differs from the workflow repository")
    ok("repository", "resolved")
    _probe(root, "pulls-read", "api", f"repos/{repo}/pulls?per_page=1")
    ok("pulls-read", "pull requests are readable")
    if mode == "ci":
        installation = _probe(root, "installation-token", "api", "installation/repositories")
        repositories = [r for r in installation.get("repositories", []) if isinstance(r, dict)] \
            if isinstance(installation, dict) else []
        if {r.get("full_name") for r in repositories} != {repo}:
            raise PreflightFailure("installation-token", "token is not an installation token scoped to exactly this repository")
        ok("installation-token", "scoped to this repository")
        # A GitHub App is never a repository collaborator (the collaborator API
        # reports "none" for its bot) and an installation token exposes no
        # repository permissions to itself. Its write access is enforced at token
        # mint: the workflow requests contents and pull-requests write, and GitHub
        # refuses a token the installation cannot grant.
        ok("bot-permission", "contents and pull-requests write granted at token mint")
    # A local run is observe-only (see run_worker), so it proves no push permission.
    return checks


def preflight(root: Path, mode: str, phase: str, env: Mapping[str, str]) -> dict[str, Any]:
    """Prove coordinator configuration; stop at the first failed check and name it."""
    if mode not in PREFLIGHT_MODES or phase not in PREFLIGHT_PHASES:
        raise QueueError("preflight needs --mode ci|local and --phase inputs|runtime|all")
    checks: list[dict[str, str]] = []
    try:
        if phase in ("inputs", "all"):
            checks.extend(_preflight_inputs(root, mode, env))
        if phase in ("runtime", "all"):
            checks.extend(_preflight_runtime(root, mode, env))
    except PreflightFailure as failure:
        checks.append({"name": failure.name, "status": "failed", "detail": failure.detail})
        return {"state": "error", "mode": mode, "phase": phase, "checks": checks,
                "reason": gate_message("publication-preflight", f"preflight failed: {failure.name}: {failure.detail}")}
    return {"state": "ok", "mode": mode, "phase": phase, "checks": checks}


def run_identity(mode: str, env: Mapping[str, str]) -> str:
    """One worker run identity, constructed per run from validated inputs."""
    if mode == "ci":
        parts = [env.get(name, "") for name in ("GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")]
        if not all(parts):
            raise QueueError("CI worker identity needs GITHUB_REPOSITORY, GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT")
        return "github-actions:" + ":".join(parts)
    raise QueueError("only the CI coordinator has a worker run identity")


LOCAL_WORKER_REFUSAL = (
    "the local coordinator is observe-only: only the CI publication-queue workflow (coordinator GitHub App) "
    "integrates or merges into main; diagnose locally with `publication_queue.py status` and "
    "`publication_queue.py preflight --mode local --phase all`"
)

# Worker outcomes that are a completed step. ``blocked`` and ``error`` exit non-zero.
WORKER_PROGRESS_STATES = frozenset({
    "merged", "empty", "queued", "active", "waiting", "not-admitted",
    "contribution-integrated", "discarded", "repair-pending", "integration-repair-pending",
})


def run_worker(root: Path, mode: str, env: Mapping[str, str], *, install_sink: bool) -> dict[str, Any]:
    """The coordinator command: full preflight, then one run identity, then candidate work.

    Only the CI coordinator integrates; a local run is refused before any GitHub read.
    """
    if mode == "local":
        return {"state": "error", "mode": mode, "reason": LOCAL_WORKER_REFUSAL}
    result = preflight(root, mode, "all", env)
    if result["state"] != "ok":
        return result
    identity = run_identity(mode, env)
    if install_sink:
        use_default_friction_sink(root, worker=identity)
    return worker(root)


def worker(root: Path) -> dict[str, Any]:
    """Integrate ready candidates one at a time; a candidate that cannot proceed never stalls the rest.

    A candidate owned by other lifecycle work, blocked, awaiting finalization or integration
    repair is skipped and the next ready candidate is evaluated in the same run. A candidate
    that holds final integration ownership (checks pending, main moved, merge accepted) ends
    the run so at most one candidate integrates at a time.
    """
    from lifecycle_workers import WorkerError
    from requirement_integration import RequirementIntegrationError

    repo = _repo(root)
    skipped: list[str] = []
    queue = _queued(root, repo, skipped)
    if not queue:
        return {"state": "empty", **({"skipped": skipped} if skipped else {})}
    blocked: dict[str, Any] | None = None
    # At most one candidate holds final integration ownership: resume the one
    # already active before granting ownership to any other.
    observed_prs: dict[int, dict[str, Any]] = {}
    failures = 0
    for _, number, _ in queue:
        try:
            observed_prs[number] = _pr(root, repo, number)
        except QueueError as exc:
            skipped.append(f"#{number} not observable: {exc}"[:300])
            failures += 1
    candidates = len(queue)
    queue = [item for item in queue if item[1] in observed_prs]

    def active(number: int) -> bool:
        return ACTIVE in {label.get("name") for label in observed_prs[number].get("labels", []) if isinstance(label, dict)}

    queue = sorted(queue, key=lambda item: not active(item[1]))
    environment: list[str] = []

    def environment_failure(progress: dict[str, Any] | None = None) -> dict[str, Any]:
        # Not a progress state: the run exits non-zero naming every cause, after trying the rest.
        return {"state": "environment-error", "reason": "; ".join(environment), "skipped": skipped,
                **({"progress": progress} if progress is not None else {})}

    for _, number, admission in queue:
        try:
            outcome, block = _worker_candidate(root, repo, number, admission, observed_prs[number], skipped, active)
        except QueueEnvironmentError as exc:
            # The candidate is left as it is: no block, no integration-repair job.
            environment.append(str(exc)[:500])
            continue
        except (QueueError, WorkerError, RequirementIntegrationError, GitCommandError) as exc:
            # One candidate's failure (GitHub read, harness git, contribution contract) never stops the rest.
            skipped.append(f"#{number} skipped: {type(exc).__name__}: {exc}"[:300])
            failures += 1
            continue
        if block is not None:
            blocked = block
        if outcome is not None:
            return environment_failure(outcome) if environment else outcome
    if environment:
        return environment_failure(blocked)
    if blocked is not None:
        return {**blocked, "skipped": skipped}  # the run still reports a block (non-zero exit), after trying the rest
    if failures == candidates:
        # Every candidate failed: that is the explicit failure of this run, not a quiet wait.
        raise QueueError("no queue candidate could be evaluated: " + "; ".join(skipped))
    return {"state": "waiting", "reason": "no integrable candidate; " + "; ".join(skipped)}


def _worker_candidate(root: Path, repo: str, number: int, admission: dict[str, Any], pr: dict[str, Any],
                      skipped: list[str], active: Callable[[int], bool]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """One queue candidate: ``(outcome that ends the run, block to report)``; ``(None, None)`` moves on."""
    if pr.get("state") == "closed" and not pr.get("merged"):
        # A PR closed without merge leaves the queue; its label must not stall the inventory.
        _label(root, repo, number, ACTIVE, present=False)
        _label(root, repo, number, QUEUE, present=False)
        skipped.append(f"#{number} closed without merge: dequeued")
        return None, None
    comments = _comments(root, repo, number)
    try:
        newest_record = _latest(root, number, comments)
    except MalformedRecord as exc:
        if pr.get("merged"):  # a confirmed merge stays authoritative over a malformed record
            _label(root, repo, number, QUEUE, present=False)
            return {"state": "merged", "number": number}, None
        skipped.append(f"#{number} blocked: {exc}"[:300])
        return None, _block(root, repo, number, str(exc))
    # legitimate absence: a candidate admitted before v2 records exists has no task identity to classify.
    identity = newest_record.get("task_identity", {}) if newest_record is not None else {}
    if isinstance(identity, dict) and identity.get("kind") == "contribution":
        from requirement_contributions import merge_reviewed_contribution, ContributionError
        current = candidate_status(root, number, repo=repo)
        if (current["state"] == "repair-pending"
                and (current.get("red_gate") or {}).get("name") == "required-checks"
                and (current.get("next_job") or {}).get("kind") != "repair"):
            failure = current["red_gate"]
            if "required-checks" in failure["evidence"]:
                red_gate = failure  # State was recorded before an interrupted job publication.
            else:
                red_gate = {**failure, "evidence": {"required-checks": {"findings": [{
                    "id": "required-checks-failed", "severity": "material",
                    "summary": "Repair failed required contribution checks", "evidence": failure["evidence"]}]}}}
            _transition(root, repo, number, "repair-pending", current["head"],
                        task_identity=current["task_identity"], inherit_identity=False,
                        gates=current.get("gates", {}), red_gate=red_gate)
            try:
                publish_job(root, repo, number, "repair", current["head"], task_identity=current["task_identity"],
                            attempt=max(1, current.get("attempts", {}).get("repair", 0) + 1))
            except QueueError as exc:
                skipped.append(f"#{number} contribution repair job not published: {exc}"[:300])
                return None, None
            return {"state": "repair-pending", "number": number}, None
        if current["state"] in {"contribution-integration-pending", "contribution-integrated"}:
            try:
                outcome = merge_reviewed_contribution(root, repo, current)
            except (ContributionError, QueueError) as exc:
                skipped.append(f"#{number} contribution: {exc}")
                return None, None
            _label(root, repo, number, QUEUE, present=False)
            return outcome, None
        skipped.append(f"#{number} contribution: {current['state']}")
        return None, None
    if pr.get("merged"):
        _label(root, repo, number, QUEUE, present=False)
        return {"state": "merged", "number": number}, None
    # Without any v2 record the v1 admission alone governs (it reads as ready).
    has_v2 = any(str(row.get("body", "")).startswith(V2_PREFIX) for row in comments)
    current = _derive(root, pr, comments) if has_v2 else {"state": "ready"}
    if has_v2 and str(current.get("reason", "")).startswith("recover validated integration-repair push"):
        # A repair job pushed its validated result but was interrupted before advancing: record it.
        from integration_contour import recover_integration_repair

        if recover_integration_repair(root, repo, number, pr, comments):
            comments = _comments(root, repo, number)
            current = _derive(root, pr, comments)
    if (has_v2 and current.get("state") == "ready"
            and str(current.get("reason", "")).startswith("recover validated finalization push")):
        # A finalize job pushed its validated archive but its ready record was lost: record it.
        from lifecycle_workers import WorkerError
        from post_review_finalization import recover_finalization_push

        try:
            recorded = recover_finalization_push(root, repo, number, pr, comments)
        except WorkerError as exc:
            skipped.append(f"#{number} finalization push not recovered: {exc}"[:300])
            return None, None
        if recorded:
            comments = _comments(root, repo, number)
            current = _derive(root, pr, comments)
    if current["state"] == "blocked-escalation" and current.get("reason", "").startswith("malformed marker"):
        skipped.append(f"#{number} blocked: {current['reason']}"[:300])
        return None, _block(root, repo, number, current["reason"])
    # Only a record for the exact current head can hand the candidate to other
    # work; otherwise _prepare must still recover an interrupted branch update.
    exact_head_record = current.get("task_identity") is not None and current.get("head") == pr.get("head", {}).get("sha")
    newest = _latest(root, number, comments) if has_v2 else None
    if newest is None:
        # legitimate absence: a v1-only candidate, or v2 comments that are all untrusted and ignored by design.
        newest = {}
    awaiting = _awaiting_readmission(root, repo, number, pr, comments, admission) if has_v2 else None
    if awaiting is not None:
        # The developer pushed a new head onto a candidate waiting for a human, a retry or an unclaimed
        # job: it awaits developer re-admission, never integration or a block of the unrecorded head.
        skipped.append(f"#{number} {awaiting['reason']}")
        if active(number):
            _label(root, repo, number, ACTIVE, present=False)
        return None, None
    if newest.get("state") in CLAIM_STATES:
        # A review/repair claim on an earlier head still owns the candidate:
        # never prepare (update or block) it under that work.
        skipped.append(f"#{number} {newest['state']} claim on {str(newest.get('head'))[:12]}")
        if active(number):
            _label(root, repo, number, ACTIVE, present=False)  # relinquish to the claiming work
        return None, None
    if exact_head_record and (current["state"] in NOT_INTEGRABLE or review_owned(current)
                              or red_retry_blocks_integration(current)):
        # A candidate owned by other work does not hold up the rest of the queue.
        skipped.append(f"#{number} {current['state']}: {current['next_action']}")
        if current["state"] == "integration-repair-pending" and not current.get("next_job"):
            # Interrupted between the state record and its job: publish the missing job (idempotent).
            try:
                publish_job(root, repo, number, integration_job_kind(current.get("red_gate")), current["head"],
                            task_identity=current["task_identity"],
                            attempt=max(1, current.get("attempts", {}).get("integration-repair", 1)))
            except QueueError as exc:
                skipped.append(f"#{number} integration-repair job not published: {exc}"[:300])
        if active(number):
            _label(root, repo, number, ACTIVE, present=False)
        return None, None
    outcome = _integrate(root, repo, number, admission, pr)
    if outcome.pop("released", False):
        skipped.append(f"#{number} {outcome.get('state')}: {outcome.get('reason', '')}"[:300])
        return None, outcome if outcome.get("state") == "blocked" else None
    if skipped:
        outcome["skipped"] = skipped
    return outcome, None


def _released(result: dict[str, Any]) -> dict[str, Any]:
    """Mark a result as one that leaves integration ownership, so the queue moves on."""
    return {**result, "released": True}


def _integrate(root: Path, repo: str, number: int, admission: dict[str, Any], pr: dict[str, Any]) -> dict[str, Any]:
    _label(root, repo, number, ACTIVE, present=True)
    try:
        _require_finalized(root, number, pr.get("head", {}).get("sha"))
        head, base = _prepare(root, repo, number, admission, pr)
        if pr.get("head", {}).get("ref", "").startswith("requirement/BR-") and head != pr["head"]["sha"]:
            refresh_composition_checks(root, repo, number, head)
        identity = {"branch": admission.get("branch"), "head": head}
        integrating = _transition(root, repo, number, "integrating", head, task_identity=identity, attempt="integration",
                    refuse_from=NOT_INTEGRABLE, cross_head_claims=True,
                    set_attempts={POST_MERGE_FLAG: 1},
                    next_job={"kind": "integration", "claim": "publication-queue workflow", "head": head})
        if integrating is not None:
            identity = integrating["task_identity"]
        deadline = time.monotonic() + CHECK_WAIT_SECONDS
        while True:
            if integrating is not None and _checks_proven_on(integrating, base):
                checks_evidence = integrating["gates"]["required-checks"]["evidence"]
                break
            state = required_check_state_for_ref(root, os.environ.copy(), str(number), head)
            if state.kind == "passed":
                checks_evidence = {"detail": state.detail or "required checks passed", "main": base, "head": head}
                break
            if state.kind in {"failed", "not_registered"}:
                # Review or repair may have claimed the head while checks ran.
                _raise_if_owned_elsewhere(root, repo, number, head)
            if state.kind == "failed":
                # A failing integration check is repaired within a bound, not an immediate block.
                raise IntegrationRepairNeeded("required check failed on the integrated candidate: " + state.detail,
                                              gate="required-checks")
            if state.kind == "not_registered":
                return _released(_block(root, repo, number, "required check is not registered for the PR head", head=head))
            if state.kind == "unknown":
                if state.cause in {"transport", "head-mismatch"}:
                    # Non-terminal and visible: the next coordinator run re-observes.
                    _label(root, repo, number, ACTIVE, present=False)
                    return _released({"state": "waiting", "number": number,
                                      "reason": f"required check observation unusable ({state.cause}): {state.detail}"})
                raise QueueError(f"required check state is unknown ({state.cause}): {state.detail}")
            if time.monotonic() >= deadline:
                if state.checks and all(check.get("state") == "EXPECTED" for check in state.checks):
                    # GitHub never attached the required checks to this head within the bound: block, naming them.
                    _raise_if_owned_elsewhere(root, repo, number, head)
                    names = ", ".join(str(check.get("name")) for check in state.checks)
                    return _released(_block(root, repo, number, "required checks were not reported on the integrated "
                                            f"head within {CHECK_WAIT_SECONDS} s: {names}", head=head))
                return {"state": "waiting", "number": number, "reason": "required CI pending"}
            time.sleep(10)
        if isinstance(identity, dict) and isinstance(identity.get("task_content"), dict):
            _transition(root, repo, number, "integrating", head, task_identity=identity,
                        gates={"required-checks": {"result": "passed", "identity": identity,
                                                   "evidence": checks_evidence}})
        if _main(root) != base or _pr(root, repo, number).get("head", {}).get("sha") != head:
            return {"state": "waiting", "number": number, "reason": "main or PR head moved; coordinator will re-evaluate"}
        # Review or repair may have claimed this head during the check wait.
        _raise_if_owned_elsewhere(root, repo, number, head)
        _require_finalized(root, number, head)
        if pr.get("head", {}).get("ref", "").startswith("requirement/BR-"):
            require_composition_finalized(root, repo, number, head)
        result = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/merge", "-f", "merge_method=squash", "-f", f"sha={head}"], cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
        if _pr(root, repo, number).get("merged"):
            _label(root, repo, number, ACTIVE, present=False)
            _label(root, repo, number, QUEUE, present=False)
            try:
                _transition(root, repo, number, "merged", head, task_identity=identity,
                            gates={"required-checks": {"result": "passed", "identity": identity, "evidence": checks_evidence}})
            except QueueError:
                # The merge is the authoritative fact; a lost record must not turn it into a block.
                pass
            return {"state": "merged", "number": number, "head": head}
        if result.returncode:
            refusal = (result.stderr.strip() or "unknown")[:300]
            _comment(root, repo, number, {"kind": "merge-refused", "head": head, "reason": refusal})
            refusals = sum(1 for event in _events(root, repo, number)
                           if event.get("kind") == "merge-refused" and event.get("head") == head
                           and event.get("comment_id", 0) > admission["comment_id"])
            if refusals >= MAX_MERGE_REFUSALS:
                return _released(_block(root, repo, number, f"protected merge refused {refusals} times: {refusal}", head=head))
            # Released: a refused merge never holds integration ownership from the rest of the queue.
            _label(root, repo, number, ACTIVE, present=False)
            return _released({"state": "waiting", "number": number,
                              "reason": f"protected merge refused ({refusals}/{MAX_MERGE_REFUSALS}); will re-evaluate: {refusal}"})
        return {"state": "waiting", "number": number, "reason": "merge accepted; awaiting GitHub confirmation"}
    except LifecycleOwnershipChanged as exc:
        _label(root, repo, number, ACTIVE, present=False)
        return _released({"state": "waiting", "number": number, "reason": str(exc)})
    except NotFinalized as exc:
        head_now = _pr(root, repo, number).get("head", {}).get("sha")
        current = _derive(root, _pr(root, repo, number), _comments(root, repo, number))
        identity_now = current.get("task_identity")
        if not (isinstance(identity_now, dict) and identity_now.get("change") and current.get("head") == head_now):
            return _released(_block(root, repo, number, str(exc)))  # no coordinator identity to finalize
        try:
            _transition(root, repo, number, "finalize-pending", head_now, task_identity=identity_now,
                        refuse_from=CLAIM_STATES - {"finalize-pending"}, cross_head_claims=True)
            publish_job(root, repo, number, "finalize", head_now, task_identity=identity_now)
        except LifecycleOwnershipChanged:
            pass
        _label(root, repo, number, ACTIVE, present=False)
        return _released({"state": "waiting", "number": number, "reason": str(exc)})
    except IntegrationRepairNeeded as exc:
        return _released(_integration_repair(root, repo, number, admission, exc))
    except QueueEnvironmentError:
        # No candidate defect: release integration ownership so later candidates proceed; the run fails naming it.
        _label(root, repo, number, ACTIVE, present=False)
        raise
    except GitCommandError as exc:
        if not _transient(str(exc)):
            raise  # not a candidate defect the queue can classify: the worker skips this candidate, naming it
        _label(root, repo, number, ACTIVE, present=False)
        return _released({"state": "waiting", "number": number, "reason": f"transient failure; will re-evaluate: {exc}"[:500]})
    except (QueueError, subprocess.CalledProcessError) as exc:
        detail = str(exc) if isinstance(exc, QueueError) else f"{exc}: {(exc.stderr or '').strip()}"
        if isinstance(exc, TransientQueueError) or (isinstance(exc, subprocess.CalledProcessError) and _transient(detail)):
            # A network, GitHub 5xx or timeout failure is not a candidate defect: wait, never block.
            _label(root, repo, number, ACTIVE, present=False)
            return _released({"state": "waiting", "number": number, "reason": f"transient failure; will re-evaluate: {detail}"[:500]})
        head_now = pr.get("head", {}).get("sha")
        try:
            # Never block a candidate that review or repair claimed meanwhile.
            if isinstance(head_now, str):
                _raise_if_owned_elsewhere(root, repo, number, head_now)
        except LifecycleOwnershipChanged as owned:
            _label(root, repo, number, ACTIVE, present=False)
            return _released({"state": "waiting", "number": number, "reason": str(owned)})
        except QueueError as unobservable:
            # Ownership cannot be observed: never overwrite a possible claim with a
            # block; the next coordinator run re-evaluates.
            _label(root, repo, number, ACTIVE, present=False)
            return _released({"state": "waiting", "number": number,
                              "reason": f"{exc}; lifecycle ownership unobservable: {unobservable}"})
        return _released(_block(root, repo, number, str(exc)))


def _checks_proven_on(candidate: dict[str, Any], base: str) -> bool:
    """A recorded content-bound check pass is reused only for the main it was proven against.

    Evidence written by this contour names the main it ran on; a pass recorded against an earlier
    main is not proof for the current merged candidate. Legacy evidence without that binding keeps
    its previous reuse rule.
    """
    from candidate_lifecycle import passed_content_gate

    if not passed_content_gate(candidate, "required-checks"):
        return False
    evidence = candidate["gates"]["required-checks"].get("evidence")
    return not (isinstance(evidence, dict) and evidence.get("main") not in (None, base))


def _integration_repair(root: Path, repo: str, number: int, admission: dict[str, Any],
                        exc: IntegrationRepairNeeded) -> dict[str, Any]:
    """Offer a bounded integration-repair job, or block the candidate once the bound is spent."""
    observed = _pr(root, repo, number)
    head_now = observed.get("head", {}).get("sha")
    comments = _comments(root, repo, number)
    current = _derive(root, observed, comments)
    try:
        lineage = _latest(root, number, comments)
    except MalformedRecord as exc:
        return _block(root, repo, number, f"integration repair cannot read the lifecycle record: {exc}"[:500], head=head_now)
    if lineage is None:
        lineage = {}  # legitimate absence: an admission that predates v2 records has no attempts to count
    spent = max(current.get("attempts", {}).get("integration-repair", 0),
                lineage.get("attempts", {}).get("integration-repair", 0))
    _label(root, repo, number, ACTIVE, present=False)
    if spent >= MAX_INTEGRATION_REPAIRS:
        return _block(root, repo, number,
                      f"integration repair exhausted after {spent} attempts: {exc}"[:500], head=head_now)
    fallback = current.get("task_identity") or lineage.get("task_identity") or {
        "branch": admission.get("branch"), "head": head_now}
    red_gate = {"name": exc.gate, "identity": head_now, "evidence": str(exc)[:500],
                **({"merge_only": True} if exc.merge_only else {})}
    try:
        _transition(root, repo, number, "integration-repair-pending", head_now, task_identity=fallback,
                    red_gate=red_gate, set_attempts={"integration-repair": spent + 1},
                    refuse_from=CLAIM_STATES, cross_head_claims=True)
        publish_job(root, repo, number, integration_job_kind(red_gate), head_now,
                    task_identity=fallback, attempt=spent + 1)
    except LifecycleOwnershipChanged:
        pass
    except QueueError as failure:
        # No originating route (or another contradiction): the job cannot be published under a default.
        return _block(root, repo, number, f"integration repair job cannot be published: {failure}"[:500], head=head_now)
    return {"state": "waiting", "number": number, "reason": str(exc)}


def restore_gates(root: Path, repo: str, number: int, *, expected_head: str | None = None) -> dict[str, Any]:
    """Restore content-bound gates a candidate lost across trusted harness pushes.

    Publishes one record on the current head that keeps its state and adds only the
    proven gates; it runs no review, registers no claim and rewrites no history.
    Any break in the proof refuses before a write. A finalize job of that head that
    already holds a result (it stopped on the lost gates) is never offered again, so
    the record re-offers finalize under a fresh job id.
    """
    from datetime import datetime, timezone

    from candidate_lifecycle import restorable_gates
    from lifecycle_workers import RESULT_PREFIX, build_job, job_completed, job_record

    pr = _pr(root, repo, number)
    head = pr.get("head", {}).get("sha")
    if expected_head is not None and expected_head != head:
        raise QueueError(f"PR #{number} head is {head}, not the expected {expected_head}; nothing was restored")
    comments = _comments(root, repo, number)
    apps = trusted_apps(root)
    writers = trusted_writers(root, comments, (RESULT_PREFIX,), repo=repo)
    try:
        candidate, gates = restorable_gates(pr, comments, trusted_apps=apps, trusted_writers=writers)
    except MalformedMarkerError as exc:
        raise QueueError(f"PR #{number} has a malformed lifecycle record: {exc}") from exc
    except ValueError as exc:
        raise QueueError(f"PR #{number} gates cannot be restored: {exc}") from exc
    reoffer: dict[str, Any] = {}
    job = build_job(candidate)
    if (candidate["state"] == "finalize-pending" and job is not None
            and job_completed(job, comments, trusted_apps=apps, trusted_writers=writers)):
        attempts = candidate.get("attempts") or {}
        seq = attempts.get("reoffers", 0) + 1
        event = {"seq": seq, "action": "restore-gates", "head": candidate["head"],
                 "reason": "the finalize job of this head completed before its gates were restored",
                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        reoffer = {"set_attempts": {"reoffers": seq},
                   "next_job": job_record("finalize", candidate["head"], candidate["task_identity"],
                                          attempts.get("finalize", 0), reoffer=event)}
    record = _transition(root, repo, number, candidate["state"], candidate["head"],
                         task_identity=candidate["task_identity"], inherit_identity=False, gates=gates, **reoffer)
    if record is None:
        raise QueueError(f"PR #{number} head moved while restoring gates; nothing was restored")
    return {"state": record["state"], "head": record["head"], "restored": sorted(gates),
            "gates": sorted(record["gates"]), **({"job": record["next_job"]} if reoffer else {})}


def _actor(root: Path) -> str:
    """The authenticated GitHub login performing an operator action; an unresolved identity fails."""
    data = _gh(root, "api", "user")
    login = data.get("login") if isinstance(data, dict) else None
    if not isinstance(login, str) or not login.strip():
        raise QueueError("the acting GitHub identity cannot be resolved; authenticate gh as the operator")
    return login.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Source repository final publication queue")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("admit")
    add.add_argument("--pr", type=int, required=True)
    add.add_argument("--head", required=True)
    show = sub.add_parser("status")
    target = show.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int)
    target.add_argument("--requirement")
    show.add_argument("--json", action="store_true")
    run = sub.add_parser("worker")
    run.add_argument("--mode", choices=PREFLIGHT_MODES, required=True)
    check = sub.add_parser("preflight")
    check.add_argument("--mode", choices=PREFLIGHT_MODES, required=True)
    check.add_argument("--phase", choices=PREFLIGHT_PHASES, required=True)
    for name, summary in (("switch-provider", "re-offer an unfinished review or repair job on other providers"),
                          ("resume", "re-offer a retryable or operationally escalated review/repair/finalize job after a human decision")):
        operator = sub.add_parser(name, help=summary)
        operator.add_argument("--pr", type=int, required=True)
        operator.add_argument("--provider", action="append", required=name == "switch-provider",
                              help="supported provider, repeat for an ordered list")
        operator.add_argument("--reason", required=True, help="the operator's reason, recorded in the candidate record")
        operator.add_argument("--expected-head", help="refuse, before any write, when the PR head differs (the head the decision was made for)")
        operator.add_argument("--via", help="optional label for the acting surface (for example chat-coordinator), recorded with the actor")
    restore = sub.add_parser("restore-gates", help="restore content-bound gates lost across trusted harness pushes")
    restore.add_argument("--pr", type=int, required=True)
    restore.add_argument("--expected-head", help="refuse, before any write, when the PR head differs")
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "admit":
            result = admit(root, args.pr, args.head)
        elif args.command == "status":
            result = requirement_status(root, args.requirement) if args.requirement else candidate_status(root, args.pr)
        elif args.command in {"switch-provider", "resume"}:
            from pr_review_gate import reoffer

            print(json.dumps(reoffer(root, _repo(root), args.pr, action=args.command, providers=args.provider,
                                     reason=args.reason, actor=_actor(root), via=args.via,
                                     expected_head=args.expected_head), sort_keys=True))
            return 0
        elif args.command == "restore-gates":
            print(json.dumps(restore_gates(root, _repo(root), args.pr, expected_head=args.expected_head), sort_keys=True))
            return 0
        elif args.command == "preflight":
            result = preflight(root, args.mode, args.phase, os.environ)
            print(json.dumps(result, sort_keys=True))
            return 0 if result["state"] == "ok" else 2
        else:
            # Real coordinator runs record friction automatically (install_sink).
            result = run_worker(root, args.mode, os.environ, install_sink=True)
    except (QueueError, AttentionError) as exc:
        print(json.dumps({"state": "error", "reason": str(exc)}))
        return 2
    if args.command == "status":
        if args.json:
            print(json.dumps(result, sort_keys=True))
        elif args.requirement:
            print("Requirement " + args.requirement)
            for candidate in result["candidates"]:
                print(render_status(candidate))
            if not result["candidates"]:
                print("No candidate PRs")
            if result.get("shared_lineage"):
                print(result["shared_lineage"])
        else:
            print(render_status(result))
        return 0
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("state") in WORKER_PROGRESS_STATES else 2





def branch_head(root: Path, branch: str) -> str:
    result = run_git(["ls-remote", "origin", f"refs/heads/{branch}"], cwd=root).stdout.split()
    if not result:
        raise QueueError("integration target branch is unavailable")
    return result[0]


def _composition_lineage(root: Path, repo: str, number: int, head: str) -> dict[str, Any]:
    """The latest composition record at ``head`` or at the head the coordinator's own update moved it from.

    Records are exact-head, and the queue merges current ``main`` into a ready
    composition itself (``update`` markers): the new head has no record until the
    final-head refresh re-establishes it. Only that recorded chain is followed; a
    record at a visited head that is not a composition record stops the walk.
    """
    comments = _comments(root, repo, number)
    moved_from = {event.get("head"): event.get("previous") for event in _events(root, repo, number)
                  if event.get("kind") == "update"}
    seen: set[str] = set()
    current: Any = head
    while isinstance(current, str) and current not in seen:
        seen.add(current)
        record = _latest(root, number, comments, current)
        if record is not None:
            identity = record.get("task_identity")
            if isinstance(identity, dict) and identity.get("kind") == "requirement-composition":
                return record
            break
        current = moved_from.get(current)
    raise QueueError("Requirement publication lacks composition identity")


def require_composition_finalized(root: Path, repo: str, number: int, head: str, *,
                                  through_update: bool = False) -> dict[str, Any]:
    """Prove the final composition gates at ``head``.

    ``through_update`` accepts gates proven at the head the coordinator's own
    recorded ``main`` update replaced (integration preparation only); admission
    and merge always need the exact head.
    """
    import tempfile
    from lifecycle_workers import prepare_checkout
    from requirement_composition import candidate_manifest, require_final_gates
    from requirement_contributions import ContributionError

    if through_update:
        current = _composition_lineage(root, repo, number, head)
    else:
        current = _derive(root, _pr(root, repo, number), _comments(root, repo, number))
    identity = current.get("task_identity")
    if not isinstance(identity, dict) or identity.get("kind") != "requirement-composition":
        raise QueueError("Requirement publication lacks composition identity")
    proven = current.get("head")
    try:
        with tempfile.TemporaryDirectory(prefix="requirement-merge-gates-") as temporary:
            checkout = prepare_checkout(f"https://github.com/{repo}.git", temporary, "harness", proven)
            manifest = candidate_manifest(checkout, identity["requirement"])
            require_final_gates(checkout, manifest, current, proven)
            return {"task_identity": identity, "gates": current["gates"]}
    except ContributionError as exc:
        raise QueueError(str(exc)) from exc


def refresh_composition_checks(root: Path, repo: str, number: int, head: str) -> None:
    import tempfile
    from lifecycle_workers import prepare_checkout
    from requirement_composition import candidate_manifest, advance_final_publication

    # The coordinator has just merged main into the composition: its gates are on the replaced head.
    candidate = _composition_lineage(root, repo, number, head)
    identity = candidate["task_identity"]
    with tempfile.TemporaryDirectory(prefix="composition-main-refresh-") as temporary:
        checkout = prepare_checkout(f"https://github.com/{repo}.git", temporary, "harness", head)
        manifest = candidate_manifest(checkout, identity["requirement"])
    result = advance_final_publication(root, repo, manifest, head, number, adapter=sys.modules[__name__],
                                       enqueue=False, candidate=candidate)
    if result["status"] != "ready":
        raise QueueError("Requirement final-head checks await fresh composition gates")


if __name__ == "__main__":
    raise SystemExit(main())
