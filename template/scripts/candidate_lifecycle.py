"""Pure candidate lifecycle projections from GitHub snapshots.

Only trusted coordinators should publish the returned marker body. This module
performs no I/O; v1 queue writers and merge behavior remain independent.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import re

PREFIX = "dev-platform-publication-queue:v2 "
V1_PREFIX = "dev-platform-publication-queue:v1 "
STATES = frozenset({
    "review-pending", "reviewing", "repair-pending", "repairing",
    "finalize-pending", "ready", "integrating", "integration-repair-pending",
    "merged", "blocked-retryable", "blocked-escalation",
})
# Work that claims a candidate; such a claim survives a coordinator branch update.
CLAIM_STATES = frozenset({"review-pending", "reviewing", "repair-pending", "repairing", "finalize-pending"})
NEXT_ACTION = {
    "review-pending": "start review", "reviewing": "continue review",
    "repair-pending": "start repair", "repairing": "continue repair",
    "finalize-pending": "finalize candidate", "ready": "await integration",
    "integrating": "continue integration", "integration-repair-pending": "repair integration",
    "merged": "reconcile delivery", "blocked-retryable": "retry red gate",
    "blocked-escalation": "human escalation required",
}


def validate_marker(record: dict) -> None:
    """Reject incomplete handoffs rather than inventing missing gate evidence."""
    if not isinstance(record, dict) or record.get("version") != 2:
        raise ValueError("expected v2 marker object")
    if type(record.get("number")) is not int or record["number"] <= 0:
        raise ValueError("invalid candidate PR number")
    if record.get("state") not in STATES:
        raise ValueError("invalid lifecycle state")
    if not isinstance(record.get("head"), str) or not re.fullmatch(r"[0-9a-f]{40}", record["head"]):
        raise ValueError("invalid candidate head")
    identity = record.get("task_identity")
    if not isinstance(identity, (str, dict)) or not identity:
        raise ValueError("missing task-content identity")
    gates = record.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("invalid gates")
    for name, gate in gates.items():
        if (not isinstance(name, str) or not name or not isinstance(gate, dict)
                or gate.get("result") not in {"passed", "failed", "pending", "skipped"}
                or not isinstance(gate.get("identity"), (str, dict)) or not gate["identity"]
                or "evidence" not in gate):
            raise ValueError("invalid gate binding")
    if "red_gate" not in record or (record["red_gate"] is not None and (
            not isinstance(record["red_gate"], dict) or not record["red_gate"].get("name")
            or "evidence" not in record["red_gate"])):
        raise ValueError("invalid red gate")
    if not isinstance(record.get("not_reverified"), list) or not all(isinstance(item, str) for item in record["not_reverified"]):
        raise ValueError("invalid not-reverified items")
    if not isinstance(record.get("attempts"), dict) or any(
            not isinstance(key, str) or type(value) is not int or value < 0
            for key, value in record["attempts"].items()):
        raise ValueError("invalid attempt counters")
    if "next_job" not in record or (record["next_job"] is not None and not isinstance(record["next_job"], (str, dict))):
        raise ValueError("invalid next job")
    try:
        if datetime.fromisoformat(record["at"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timestamp needs timezone")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("invalid transition timestamp") from exc


def build_handoff_record(*, number: int, state: str, head: str,
                         task_identity: str | dict, gates: dict, red_gate: dict | None,
                         not_reverified: list, attempts: dict, next_job: str | dict | None,
                         at: str) -> dict:
    """Build one immutable-by-convention transition record, copying all inputs."""
    record = deepcopy({"version": 2, "number": number, "state": state, "head": head,
                       "task_identity": task_identity, "gates": gates, "red_gate": red_gate,
                       "not_reverified": not_reverified, "attempts": attempts,
                       "next_job": next_job, "at": at})
    validate_marker(record)
    return record


def marker_body(record: dict) -> str:
    validate_marker(record)
    return PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":"))


def label_projection(candidate: dict) -> list[str]:
    """Desired lifecycle labels; callers replace only the lifecycle namespace."""
    state = candidate.get("state")
    if state not in STATES:
        raise ValueError("invalid lifecycle state")
    return ["lifecycle:" + state]


TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def trusted_marker_comment(row: dict, trusted_apps: frozenset[str] = frozenset(),
                           trusted_writers: frozenset[str] = frozenset()) -> bool:
    """Coordinator records come from repository writers or the configured coordinator App.

    OWNER is a writer by definition. MEMBER and COLLABORATOR say nothing about
    write permission, so those authors count only when the caller proved write
    access (``trusted_writers``). Anyone else, including an unrelated GitHub App,
    could otherwise forge a lifecycle record and stall publication; such
    comments are ignored rather than trusted or blocking.
    """
    if row.get("author_association") == "OWNER":
        return True
    user = row.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    if row.get("author_association") in TRUSTED_ASSOCIATIONS and login in trusted_writers:
        return True
    app = row.get("performed_via_github_app")
    return isinstance(app, dict) and app.get("slug") in trusted_apps


def latest_record(number: int, comments: list[dict], *, trusted_apps: frozenset[str] = frozenset(),
                  head: str | None = None, trusted_writers: frozenset[str] = frozenset()) -> dict | None:
    """The latest valid trusted v2 record for this PR, for ``head`` or for any head (lineage)."""
    latest = None
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body", "")
        if not isinstance(body, str) or not body.startswith(PREFIX) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        try:
            record = json.loads(body[len(PREFIX):])
            validate_marker(record)
        except (ValueError, TypeError):
            continue
        if record.get("number") == number and (head is None or record.get("head") == head):
            latest = record
    return deepcopy(latest) if latest is not None else None


def derive_candidate(pr: dict, comments: list[dict], checks: dict | None = None, *,
                     trusted_apps: frozenset[str] = frozenset(), trusted_writers: frozenset[str] = frozenset()) -> dict:
    """Derive from the latest exact-head handoff; labels never grant v2 gates.

    Comment IDs provide GitHub's immutable ordering. Any malformed v2 marker
    fails closed, even if its head cannot be decoded. Stale heads contribute no
    gates, claims or next job. Required checks are an exact-head snapshot.
    """
    head = pr.get("head", {}).get("sha", pr.get("headRefOid"))
    number = pr.get("number")
    result = {"number": number, "head": head, "state": "review-pending",
              "task_identity": None, "gates": {}, "red_gate": None,
              "not_reverified": [], "attempts": {}, "next_job": None, "reason": ""}
    matching, legacy = [], []
    matched_at = blocked_at = 0
    newest: dict | None = None
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body", "")
        if not isinstance(body, str) or not body.startswith((PREFIX, V1_PREFIX)) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        v2 = body.startswith(PREFIX)
        try:
            record = json.loads(body[len(PREFIX if v2 else V1_PREFIX):])
            if v2:
                validate_marker(record)
            elif not isinstance(record, dict) or record.get("version") != 1:
                raise ValueError("invalid v1 marker")
            if record.get("number") != number:
                raise ValueError("marker names another PR")
        except (ValueError, TypeError) as exc:
            if pr.get("merged") or pr.get("mergedAt"):
                continue  # a confirmed merge stays authoritative over a malformed record
            result.update(state="blocked-escalation", reason=f"malformed marker comment {row.get('id')}: {exc}")
            return _action(result)
        if v2:
            newest = record
        if v2 and record["head"] == head:
            matching.append(record)
            matched_at = len(matching) + len(legacy)
        elif not v2:
            legacy.append(record)
            if record.get("kind") == "block":
                blocked_at = len(matching) + len(legacy)
    if matching:
        result.update(deepcopy(matching[-1]))
        # A v1 block written after the latest record (its v2 record lost to an
        # interruption) still governs: the candidate is durably blocked.
        if blocked_at > matched_at:
            reason = next(event for event in reversed(legacy) if event.get("kind") == "block").get("reason", "publication blocked")
            result.update(state="blocked-escalation", reason=reason, next_job=None,
                          red_gate={"name": "publication", "identity": head, "evidence": reason})
    elif newest is not None and newest["state"] in CLAIM_STATES:
        # A review/repair/finalization claim survives a coordinator branch update:
        # show its job and attempts (its gates were bound to the earlier head).
        result.update(state=newest["state"], next_job=deepcopy(newest.get("next_job")),
                      attempts=deepcopy(newest.get("attempts", {})),
                      reason=f"claim recorded on earlier head {newest['head'][:12]}")
    elif legacy:
        latest = legacy[-1]
        labels = {label if isinstance(label, str) else label.get("name") for label in pr.get("labels", [])}
        admissions = [event for event in legacy if event.get("kind") == "admit"]
        if latest.get("kind") == "block" or "publication:blocked" in labels:
            result.update(state="blocked-escalation", reason=latest.get("reason", "publication blocked"))
        elif admissions and latest.get("head") == head:
            result["state"] = "integrating" if "publication:active" in labels else "ready"
    if pr.get("merged") or pr.get("mergedAt"):
        result.update(state="merged", next_job=None)
    elif pr.get("state", "").lower() == "closed":
        result.update(state="blocked-escalation", reason="PR closed without merge")
    elif checks and checks.get("head") == head and result["state"] in {"ready", "integrating"}:
        kind = checks.get("kind")
        if kind == "failed":
            failing = {"name": "required-checks", "identity": head, "evidence": deepcopy(checks)}
            result.update(state="integration-repair-pending" if result["state"] == "integrating" else "repair-pending",
                          red_gate=failing,
                          gates={**result["gates"], "required-checks": {"result": "failed", "identity": head,
                                                                       "evidence": deepcopy(checks)}})
            result["next_job"] = None
        elif kind == "pending" and result["state"] == "integrating":
            # Integration (and its claim) remains active while exact-head checks run.
            result["reason"] = checks.get("detail") or "awaiting exact-head required checks"
        elif kind != "passed":
            result.update(state="blocked-retryable", reason=checks.get("detail") or "await exact-head required checks", next_job=None)
    elif checks and checks.get("head") != head:
        result.update(state="blocked-retryable", reason="checks do not match candidate head", gates={}, next_job=None)
    return _action(result)


def _action(candidate: dict) -> dict:
    candidate["next_action"] = candidate.get("next_job") or NEXT_ACTION[candidate["state"]]
    candidate["lifecycle_labels"] = label_projection(candidate)
    return candidate


def render_status(candidate: dict) -> str:
    """Compact operator view, with handoff evidence kept visible."""
    return (f"PR #{candidate['number']}: {candidate['state']}\n"
            f"head: {candidate['head']}\n"
            f"red gate: {json.dumps(candidate.get('red_gate'), sort_keys=True)}\n"
            f"attempts: {json.dumps(candidate.get('attempts', {}), sort_keys=True)}\n"
            f"next action: {json.dumps(candidate['next_action'], sort_keys=True)}\n"
            f"gate bindings: {json.dumps(candidate.get('gates', {}), sort_keys=True)}\n"
            f"not re-verified: {json.dumps(candidate.get('not_reverified', []))}\n"
            f"reason: {candidate.get('reason', '')}")
