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


MAX_MARKER_CHARS = 60000  # GitHub caps a comment at 65536 characters
_IDENTITY_REF = {"$ref": "task_identity"}


def _compact_identity(record: dict) -> dict:
    """Reference the record's identity from gates instead of repeating its path map."""
    identity = record.get("task_identity")
    if not isinstance(identity, dict):
        return record
    compact = dict(record)
    compact["gates"] = {name: {**gate, "identity": _IDENTITY_REF} if gate.get("identity") == identity else gate
                        for name, gate in record["gates"].items()}
    red = record.get("red_gate")
    if isinstance(red, dict) and red.get("identity") == identity:
        compact["red_gate"] = {**red, "identity": _IDENTITY_REF}
    job = record.get("next_job")
    if isinstance(job, dict) and job.get("task_identity") == identity:
        compact["next_job"] = {**job, "task_identity": _IDENTITY_REF}
    return compact


def _expand_identity(record):
    if not isinstance(record, dict) or not isinstance(record.get("task_identity"), dict):
        return record
    identity = record["task_identity"]
    if isinstance(record.get("gates"), dict):
        record["gates"] = {name: {**gate, "identity": deepcopy(identity)}
                           if isinstance(gate, dict) and gate.get("identity") == _IDENTITY_REF else gate
                           for name, gate in record["gates"].items()}
    red = record.get("red_gate")
    if isinstance(red, dict) and red.get("identity") == _IDENTITY_REF:
        record["red_gate"] = {**red, "identity": deepcopy(identity)}
    job = record.get("next_job")
    if isinstance(job, dict) and job.get("task_identity") == _IDENTITY_REF:
        record["next_job"] = {**job, "task_identity": deepcopy(identity)}
    return record


def marker_body(record: dict) -> str:
    validate_marker(record)
    body = PREFIX + json.dumps(_compact_identity(record), sort_keys=True, separators=(",", ":"))
    if len(body) > MAX_MARKER_CHARS:
        raise ValueError(f"lifecycle record is {len(body)} characters, above the {MAX_MARKER_CHARS} bound; "
                         "store compact evidence references instead of full evidence")
    return body


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
            record = _expand_identity(json.loads(body[len(PREFIX):]))
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
                record = _expand_identity(record)
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
        if result["state"] == "reviewing" and isinstance(result.get("next_job"), dict):
            # A review result posted before the interrupted advancement never retained its reports: repeat review.
            from lifecycle_workers import RESULT_PREFIX, job_id

            old = {**result["next_job"], "number": number}
            for row in comments:
                body = row.get("body", "")
                if not isinstance(body, str) or not body.startswith(RESULT_PREFIX) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
                    continue
                try:
                    receipt = json.loads(body[len(RESULT_PREFIX):])
                except ValueError:
                    continue
                if (isinstance(receipt, dict) and receipt.get("job") == job_id(old) and receipt.get("head") == head
                        and receipt.get("outcome") == "reviewed" and receipt.get("pushed_head") == head):
                    attempts = deepcopy(result.get("attempts", {}))
                    attempts["review"] = attempts.get("review", 0) + 1
                    result.update(state="review-pending", attempts=attempts,
                                  next_job={**{k: deepcopy(v) for k, v in old.items() if k != "number"},
                                            "attempt": attempts["review"]},
                                  reason="recover completed review result without advancement; repeat review")
                    break
        if result["state"] == "repairing" and isinstance(result.get("next_job"), dict):
            # A repair result posted before the interrupted advancement still decides the job.
            from lifecycle_workers import RESULT_PREFIX, job_id

            job = {**result["next_job"], "number": number}
            for row in comments:
                body = row.get("body", "")
                if not isinstance(body, str) or not body.startswith(RESULT_PREFIX) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
                    continue
                try:
                    receipt = json.loads(body[len(RESULT_PREFIX):])
                except ValueError:
                    continue
                outcome = str(receipt.get("outcome", "")) if isinstance(receipt, dict) else ""
                if (receipt.get("job") == job_id(job) and receipt.get("head") == head
                        and outcome.split(":")[0] in {"no-change", "failed", "rejected", "proposed-rejection"}):
                    result.update(state="blocked-escalation", next_job=None,
                                  reason="recover completed repair result without a change",
                                  red_gate={"name": "repair", "identity": result.get("task_identity"), "evidence": outcome})
                    break
    elif newest is not None and newest["state"] in CLAIM_STATES:
        # A review/repair/finalization claim survives a coordinator branch update:
        # show its job and attempts (its gates were bound to the earlier head).
        result.update(state=newest["state"], next_job=deepcopy(newest.get("next_job")),
                      attempts=deepcopy(newest.get("attempts", {})),
                      reason=f"claim recorded on earlier head {newest['head'][:12]}")
    # A harness publishes the validated destination and its content proof before
    # pushing. Recover only that exact destination, never an unrelated head move.
    if not matching and newest is not None and newest["state"] in {
            "reviewing", "repairing", "finalize-pending", "integration-repair-pending"}:
        from lifecycle_workers import RESULT_PREFIX, job_id

        kind = {"reviewing": "review", "repairing": "repair",
                "integration-repair-pending": "integration-repair"}.get(newest["state"], "finalize")
        old_job = {"number": number, "kind": kind, "head": newest["head"],
                   "attempt": newest.get("attempts", {}).get(kind, 0)}
        for row in sorted(comments, key=lambda item: item.get("id", 0), reverse=True):
            body = row.get("body", "")
            if not isinstance(body, str) or not body.startswith(RESULT_PREFIX) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
                continue
            try:
                receipt = json.loads(body[len(RESULT_PREFIX):])
            except ValueError:
                continue
            if (isinstance(receipt, dict) and receipt.get("outcome") == "validated-push"
                    and receipt.get("job") == job_id(old_job) and receipt.get("head") == newest["head"]
                    and receipt.get("pushed_head") == head and isinstance(receipt.get("task_identity"), dict)
                    and receipt["task_identity"].get("task_content")
                    and isinstance(newest.get("task_identity"), dict)
                    and receipt["task_identity"].get("change") == newest["task_identity"].get("change")):
                if kind == "integration-repair":
                    old_content = (newest.get("task_identity") or {}).get("task_content")
                    new_content = receipt["task_identity"].get("task_content")
                    if (isinstance(old_content, dict) and isinstance(new_content, dict)
                            and old_content.get("digest") == new_content.get("digest")):
                        # The harness pushed a repair that left task content unchanged: existing
                        # review/finalization evidence is reused; checks must rerun on the new head.
                        result.update(state="ready", task_identity=deepcopy(receipt["task_identity"]),
                                      gates={name: {**deepcopy(gate), "identity": deepcopy(receipt["task_identity"])}
                                             for name, gate in newest.get("gates", {}).items()
                                             if name != "required-checks"},
                                      attempts=deepcopy(newest.get("attempts", {})), red_gate=None,
                                      next_job=None, reason="recover validated integration-repair push")
                        break
                if kind == "finalize":
                    # The harness pushed the archive of this exact task content: it is ready,
                    # keeping the gates the finalization reused (identity is unchanged).
                    result.update(state="ready", task_identity=deepcopy(receipt["task_identity"]),
                                  gates={name: {**deepcopy(gate), "identity": deepcopy(receipt["task_identity"])}
                                         for name, gate in newest.get("gates", {}).items()},
                                  next_job=None, reason="recover validated finalization push")
                    break
                attempts = deepcopy(newest.get("attempts", {}))
                attempts["review"] = attempts.get("review", 0) + 1
                carried = (newest.get("next_job") or {}) if isinstance(newest.get("next_job"), dict) else {}
                recovered_job = {"kind": "review", "head": head, "task_identity": deepcopy(receipt["task_identity"]),
                                 "attempt": attempts["review"],
                                 **{key: deepcopy(carried[key]) for key in ("provider", "providers") if key in carried}}
                result.update(state="review-pending", task_identity=deepcopy(receipt["task_identity"]),
                              attempts=attempts, gates={}, next_job=recovered_job,
                              reason="recover validated worker push; repeat review")
                break
    if not matching and not (newest is not None and newest["state"] in CLAIM_STATES) and legacy:
        latest = legacy[-1]
        labels = {label if isinstance(label, str) else label.get("name") for label in pr.get("labels", [])}
        admissions = [event for event in legacy if event.get("kind") == "admit"]
        if latest.get("kind") == "block" or "publication:blocked" in labels:
            result.update(state="blocked-escalation", reason=latest.get("reason", "publication blocked"))
        elif admissions and latest.get("head") == head:
            result["state"] = "integrating" if "publication:active" in labels else "ready"
    if pr.get("merged") or pr.get("mergedAt"):
        job, reason = post_merge_job(result, comments, trusted_apps, trusted_writers)
        result.update(state="merged", next_job=job)
        if reason:
            result["reason"] = reason
    elif pr.get("state", "").lower() == "closed":
        result.update(state="blocked-escalation", reason="PR closed without merge")
    elif checks and checks.get("head") == head and result["state"] in {"ready", "integrating"}:
        kind = checks.get("kind")
        if kind == "failed":
            binding = result.get("task_identity") or head
            failing = {"name": "required-checks", "identity": binding, "evidence": deepcopy(checks)}
            result.update(state="integration-repair-pending" if result["state"] == "integrating" else "repair-pending",
                          red_gate=failing,
                          gates={**result["gates"], "required-checks": {"result": "failed", "identity": binding,
                                                                       "evidence": deepcopy(checks)}})
            result["next_job"] = None
        elif kind == "passed":
            result["gates"]["required-checks"] = {
                "result": "passed", "identity": result.get("task_identity") or head,
                "evidence": deepcopy(checks)}
        elif passed_content_gate(result, "required-checks"):
            # A trusted, content-bound pass survives bookkeeping-only heads.
            pass
        elif kind == "pending" and result["state"] == "integrating":
            # Integration (and its claim) remains active while exact-head checks run.
            result["reason"] = checks.get("detail") or "awaiting exact-head required checks"
        elif kind != "passed":
            result.update(state="blocked-retryable", reason=checks.get("detail") or "await exact-head required checks", next_job=None)
    elif checks and checks.get("head") != head:
        result.update(state="blocked-retryable", reason="checks do not match candidate head", gates={}, next_job=None)
    return _action(result)


POST_MERGE_KINDS = ("retrospective", "terminal-reconciliation", "cleanup")
MAX_POST_MERGE_ATTEMPTS = 3
POST_MERGE_FLAG = "post-merge"


def post_merge_job(candidate: dict, comments: list[dict], trusted_apps: frozenset[str] = frozenset(),
                   trusted_writers: frozenset[str] = frozenset()) -> tuple[dict | None, str]:
    """The next post-merge obligation of a merged candidate, derived only from trusted result receipts.

    A candidate the coordinator merged carries ``attempts["post-merge"] = 1``; anything merged
    earlier or elsewhere offers nothing. The chain is retrospective, terminal reconciliation,
    then cleanup. A receipt whose outcome starts with ``failed`` or ``blocked`` leaves the same
    obligation open for a new attempt, bounded by ``MAX_POST_MERGE_ATTEMPTS``; any other outcome
    completes it. Nothing is stored, so an interrupted run resumes by re-deriving.
    """
    from lifecycle_workers import RESULT_PREFIX, job_id

    identity = candidate.get("task_identity")
    if candidate.get("attempts", {}).get(POST_MERGE_FLAG) != 1 or identity is None:
        return None, ""
    outcomes: dict[str, list[str]] = {}
    for row in sorted(comments, key=lambda item: item.get("id", 0)):
        body = row.get("body", "")
        if not isinstance(body, str) or not body.startswith(RESULT_PREFIX) or not trusted_marker_comment(row, trusted_apps, trusted_writers):
            continue
        try:
            receipt = json.loads(body[len(RESULT_PREFIX):])
        except ValueError:
            continue
        outcome = str(receipt.get("outcome", "")) if isinstance(receipt, dict) else ""
        if (isinstance(receipt, dict) and receipt.get("head") == candidate["head"]
                and outcome != "validated-push" and not outcome.startswith("discarded")):
            outcomes.setdefault(str(receipt.get("job")), []).append(outcome)
    for kind in POST_MERGE_KINDS:
        for attempt in range(MAX_POST_MERGE_ATTEMPTS):
            job = {"number": candidate["number"], "kind": kind, "head": candidate["head"], "attempt": attempt}
            seen = outcomes.get(job_id(job))
            if not seen:
                return {"kind": kind, "head": candidate["head"], "task_identity": deepcopy(identity),
                        "attempt": attempt}, ""
            if not seen[-1].startswith(("failed", "blocked")):
                break
        else:
            return None, f"post-merge {kind} exhausted {MAX_POST_MERGE_ATTEMPTS} attempts; operator action required"
    return None, ""


def passed_content_gate(candidate: dict, name: str) -> bool:
    """Accept only a passed gate bound to this candidate's proven content."""
    identity = candidate.get("task_identity")
    gate = candidate.get("gates", {}).get(name)
    proof = identity.get("task_content") if isinstance(identity, dict) else None
    return (isinstance(proof, dict) and proof.get("version") == 1
            and isinstance(proof.get("paths"), dict)
            and isinstance(proof.get("base"), str) and bool(proof["base"])
            and isinstance(proof.get("digest"), str) and bool(proof["digest"])
            and isinstance(gate, dict) and gate.get("result") == "passed"
            and gate.get("identity") == identity)


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
