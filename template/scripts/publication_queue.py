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
from typing import Any

from _platform_common import current_worktree_root, read_platform_config, run_git
from publication_state import _classify_required_checks, required_check_state_for_ref
from candidate_lifecycle import CLAIM_STATES, POST_MERGE_FLAG, PREFIX as V2_PREFIX, STATES, latest_record, build_handoff_record, derive_candidate, label_projection, marker_body, render_status

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
    checks on the actual merged candidate are ``required-checks``.
    """

    def __init__(self, message: str, *, gate: str = "integration"):
        super().__init__(message)
        self.gate = gate


class NotFinalized(QueueError):
    """A completed OpenSpec change is still active: the candidate must be finalized first."""


class LifecycleOwnershipChanged(QueueError):
    """Another lifecycle job took the candidate between observation and transition."""


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
        raise QueueError(result.stderr.strip() or result.stdout.strip() or f"gh exit {result.returncode}")
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QueueError("GitHub returned non-JSON queue state") from exc


COORDINATOR_APP_ENV = "DEV_PLATFORM_COORDINATOR_APP"


def trusted_apps(root: Path) -> frozenset[str]:
    """The coordinator App whose comments count as lifecycle records.

    The workflow exports the slug of the App token it minted. A local reader
    takes it from ``[publication] coordinator_app`` in the external operator
    config (operator identity stays out of committed project config) or the
    project config. No other App is trusted.
    """
    from _platform_common import read_operator_config

    names = {os.environ.get(COORDINATOR_APP_ENV, "").strip()}
    for reader in (read_platform_config, read_operator_config):
        try:
            configured = reader(root).get("publication", {})
        except Exception:
            continue
        if isinstance(configured, dict):
            names.add(str(configured.get("coordinator_app", "")).strip())
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
    return latest_record(number, comments, trusted_apps=trusted_apps(root), head=head,
                         trusted_writers=trusted_writers(root, comments))


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
    rows = _gh(root, "api", f"repos/{repo}/issues/{number}/comments?per_page=100")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise QueueError("PR queue comments are unavailable or exceed the bounded page")
    return [row for row in rows if isinstance(row, dict)]


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
    """Concurrent retries share a slot; a blocked candidate may start a new one."""
    blocks = [event["comment_id"] for event in events if event.get("kind") == "block" and isinstance(event.get("comment_id"), int)]
    cutoff = max(blocks, default=0)
    admissions = [event for event in events if event.get("kind") == "admit" and isinstance(event.get("comment_id"), int) and event["comment_id"] > cutoff]
    if not admissions:
        return None
    first = min(admissions, key=lambda event: event["comment_id"])
    if not all(
        all(event.get(key) == first.get(key) for key in ("head", "branch"))
        for event in admissions
    ):
        raise QueueError(f"PR #{number} has conflicting admission evidence")
    return first


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


def set_friction_sink(sink) -> None:
    global _friction_sink
    _friction_sink = sink


def use_default_friction_sink(root: Path) -> None:
    from integration_contour import default_friction_sink

    set_friction_sink(default_friction_sink(root))


def emit_friction(number: int, branch: str | None, kind: str, head: str, detail: str, *,
                  attempts: dict[str, int] | None = None) -> None:
    """Record required friction before publishing a transition; failures leave it retryable."""
    if _friction_sink is None:
        return
    if not isinstance(branch, str) or not branch:
        raise QueueError("friction recording requires a candidate branch; retry transition")
    import hashlib

    spec = _FRICTION_STATES.get(kind)
    category, severity, triggers, observation = spec if spec else (
        "coordinator-" + kind, "medium", ["nondefault-override"], detail)
    key = hashlib.sha256(json.dumps([number, kind, head, sorted((attempts or {}).items())]).encode()).hexdigest()[:24]
    try:
        _friction_sink({"task": branch, "number": number, "category": category, "severity": severity,
                        "triggers": triggers, "observation": observation,
                        "evidence": f"PR #{number} {kind} at head {head[:12]}: {detail}"[:1000],
                        "hypothesis": "Recorded automatically by the publication coordinator; see the PR lifecycle records.",
                        "proposal": "Review whether the gate, the evidence or the repair path should change.",
                        "dedupe_key": f"coordinator:{key}"})
    except (Exception, SystemExit) as exc:
        raise QueueError(f"friction recording failed for PR #{number} ({kind}); retry transition: {exc}") from exc


def _transition(
    root: Path, repo: str, number: int, state: str, head: str, *,
    task_identity: str | dict[str, Any], red_gate: dict[str, Any] | None = None,
    gates: dict[str, Any] | None = None, attempt: str | None = None,
    set_attempts: dict[str, int] | None = None,
    refuse_from: set[str] | frozenset[str] = frozenset(), inherit_identity: bool = True,
    cross_head_claims: bool = False, next_job: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Publish the v2 handoff record for one transition and project its lifecycle label.

    v1 admission/update markers stay authoritative for the existing queue; the
    v2 record is what a later executor or ``status`` reads to continue. The PR
    head and latest record are re-observed first: a moved head publishes
    nothing; a current-head record in ``refuse_from`` (another job's ownership)
    raises ``LifecycleOwnershipChanged``; a transition carrying nothing new is
    not re-published (scheduled retries must not grow the bounded comment
    page) but still repairs the label projection. Gates, items not re-verified
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
    previous = _latest(root, number, comments, head) or {}
    lineage = _latest(root, number, comments) or {}
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
    new_attempts = any(previous.get("attempts", {}).get(k) != v for k, v in (set_attempts or {}).items())
    branch = observed.get("head", {}).get("ref")
    if not identity_changed and not new_attempts and previous.get("state") == state and red_gate in (None, previous.get("red_gate")) and not new_gates and not new_job:
        if state in _FRICTION_STATES:
            emit_friction(number, branch, state, head, str((previous.get("red_gate") or {}).get("evidence", ""))[:300],
                          attempts=previous.get("attempts"))
        _project_lifecycle_label(root, repo, number, observed, state)
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
        task_identity=(previous.get("task_identity") or lineage.get("task_identity") or task_identity)
        if inherit_identity else task_identity,
        gates=merged_gates, red_gate=red_gate,
        not_reverified=list(previous.get("not_reverified") or lineage.get("not_reverified") or []),
        attempts=attempts,
        next_job=next_job if next_job is not None else (previous.get("next_job") if state == previous.get("state") or state in {"reviewing", "repairing"} else None),
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if state in _FRICTION_STATES:
        emit_friction(number, branch, state, head, str((red_gate or {}).get("evidence", ""))[:300], attempts=attempts)
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", data={"body": marker_body(record)})
    _project_lifecycle_label(root, repo, number, observed, state)
    return record


def publish_job(root: Path, repo: str, number: int, kind: str, head: str, *,
                task_identity: str | dict[str, Any], attempt: int | None = None,
                providers=None, target_head=None, phase=None) -> dict[str, Any] | None:
    """Publish a head-bound job record for the candidate's current state (no new state)."""
    from lifecycle_workers import job_record

    observed = _pr(root, repo, number)
    current = _derive(root, observed, _comments(root, repo, number))
    if attempt is None:
        attempt = current.get("attempts", {}).get(kind, 0)
    if providers is None and kind in {"review", "repair"}:
        from independent_review_runner import settings, resolve_provider

        config = settings(root)
        providers = config.get("providers")
        if providers is None:
            provider, _ = resolve_provider(root, config)
            providers = [provider or "unresolved-originating-task-route"]
    if providers and "unresolved-originating-task-route" in providers:
        emit_friction(number, observed.get("head", {}).get("ref"), "fallback", head,
                      f"{kind} job could not resolve the originating task route and falls back to the default provider")
    return _transition(root, repo, number, current["state"], head,
                       task_identity=current.get("task_identity") or task_identity,
                       red_gate=current.get("red_gate") if kind in {"repair", "integration-repair"} else None,
                       next_job=job_record(kind, head, current.get("task_identity") or task_identity, attempt,
                                           providers=providers, target_head=target_head, phase=phase))


def _raise_if_owned_elsewhere(root: Path, repo: str, number: int, head: str) -> None:
    comments = _comments(root, repo, number)
    claimed = _derive(root, _pr(root, repo, number), comments)
    newest = _latest(root, number, comments) or {}
    exact_owner = claimed.get("head") == head and claimed.get("task_identity") is not None and claimed["state"] in NOT_INTEGRABLE
    if _malformed(claimed) or exact_owner or newest.get("state") in CLAIM_STATES:
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


def review_owned(candidate: dict) -> bool:
    return (candidate.get("state") == "blocked-retryable"
            and ((candidate.get("next_job") or {}).get("kind") == "review"
                 or (candidate.get("red_gate") or {}).get("name") == "review"))


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


def _admission_handoff(root: Path, branch: str, head: str) -> dict[str, Any]:
    """Task-content identity for the admitted head.

    A managed task checked out at the admitted head binds its task-content
    digest; otherwise (quick task, or a checkout elsewhere) exact-head identity.
    """
    proof = None
    # Only a checkout at the admitted head can vouch for its validation.
    try:
        local_head = run_git(["rev-parse", "HEAD"], cwd=root, check=False).stdout.strip()
    except OSError:
        local_head = ""
    if local_head == head:
        try:
            from agent_friction import current_task_content

            proof = current_task_content(root)
        except Exception:
            proof = None
    digest = proof.get("digest") if isinstance(proof, dict) else None
    if not (isinstance(digest, str) and digest):
        return {"task_identity": {"branch": branch, "head": head}, "gates": {}}
    return {"task_identity": {"task_content": digest}, "gates": _archived_verification_gate(root)}


def _archived_verification_gate(root: Path) -> dict[str, Any]:
    """The archived automated-checks evidence of this managed task, as a satisfied gate.

    Admission itself proves no validation; it binds the gate the archive helper
    already recorded (successful outcome, the task content and head it ran on,
    and the evidence file digest). Without that evidence no gate is claimed.
    """
    import hashlib

    try:
        from managed_task import read_task_state

        state = read_task_state(root) or {}
    except Exception:
        return {}
    change = state.get("change")
    if not isinstance(change, str) or not change:
        return {}
    matches = sorted((root / "openspec" / "changes" / "archive").glob(f"*-{change}/automated-checks.json"))
    if len(matches) != 1:
        return {}
    raw = matches[0].read_bytes()
    try:
        evidence = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    checkout = evidence.get("managed_checkout") if isinstance(evidence, dict) else None
    content = checkout.get("task_content") if isinstance(checkout, dict) else None
    if evidence.get("outcome") != "success" or not isinstance(content, dict) or not content.get("digest"):
        return {}
    return {"archived-verification": {
        "result": "passed",
        "identity": {"task_content": content["digest"], "head": checkout.get("head")},
        "evidence": {"path": matches[0].relative_to(root).as_posix(), "sha256": hashlib.sha256(raw).hexdigest()},
    }}


def admit(root: Path, number: int, expected_head: str, *, handoff: dict | None = None) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    identity = (handoff or {}).get("task_identity", {})
    target = identity.get("target_branch", "main") if isinstance(identity, dict) else "main"
    if pr.get("state") != "open" or pr.get("base", {}).get("ref") != target or pr.get("head", {}).get("sha") != expected_head:
        raise QueueError("queue admission requires one open PR at the exact validated head against main")
    branch = pr.get("head", {}).get("ref")
    if isinstance(branch, str) and branch.startswith("requirement/BR-") and not handoff:
        identity = (_latest(root, number, _comments(root, repo, number), expected_head) or {}).get("task_identity", {})
    if not isinstance(branch, str) or not (branch.startswith("agent/")
        or (identity.get("kind") == "requirement-composition" and branch.startswith("requirement/BR-"))):
        raise QueueError("queue admission requires an owned task branch")
    if target == "main" and branch.startswith("requirement/BR-"):
        require_composition_finalized(root, repo, number, expected_head)
    events = _events(root, repo, number)
    admitted = _admission(events, number)
    if admitted and handoff:
        prior = _latest(root, number, _comments(root, repo, number))
        old_identity = prior.get("task_identity") if prior else None
        keys = ("kind", "change", "requirement", "source_issue", "work_identity", "target_branch", "contribution_base")
        updates = [event for event in events if event.get("kind") == "update"
                   and event.get("comment_id", 0) > admitted.get("comment_id", 0)]
        proven = updates[-1].get("head") if updates else admitted.get("head")
        if (prior and prior.get("head") == proven and prior.get("head") != expected_head
                and prior.get("state") == "blocked-retryable"
                and prior.get("red_gate", {}).get("name") == "semantic-verification"
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
        updates = [event for event in events if event.get("kind") == "update"
                   and event.get("comment_id", 0) > admitted.get("comment_id", 0)]
        proven = updates[-1].get("head") if updates else admitted.get("head")
        if proven != expected_head:
            raise QueueError("PR has an earlier or ambiguous admission; resolve it before re-admission")
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
    current = _derive(root, _pr(root, repo, number), _comments(root, repo, number))
    if current.get("task_identity") is None or current.get("head") != expected_head:
        try:
            _transition(root, repo, number, "review-pending" if handoff else "ready", expected_head, inherit_identity=False,
                        refuse_from=STATES, **(handoff or _admission_handoff(root, branch, expected_head)))
        except LifecycleOwnershipChanged:
            pass  # lifecycle work recorded this head in the meantime; never rewind it
    if handoff:
        confirmed = _latest(root, number, _comments(root, repo, number), expected_head)
        if confirmed is None or _pr(root, repo, number).get("head", {}).get("sha") != expected_head:
            raise QueueError("developer handoff admission is not confirmed at the exact PR head")
        if confirmed["state"] == "review-pending":
            publish_job(root, repo, number, "review", expected_head, task_identity=handoff["task_identity"])
    _label(root, repo, number, QUEUE, present=True)
    return {"number": number, "position_key": admitted["comment_id"], "head": expected_head, "state": "queued"}


def _queued(root: Path, repo: str) -> list[tuple[int, int, dict[str, Any]]]:
    # Filter remotely before bounding. Merged queued contributions still need
    # recovery if the worker stopped between GitHub merge and manifest publication.
    rows = _gh(root, "pr", "list", "--state", "all", "--label", QUEUE, "--limit", "100", "--json", "number,labels")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise QueueError("queued PR inventory is unavailable or exceeds the bounded limit")
    queue = []
    for row in rows:
        if not isinstance(row, dict) or QUEUE not in {label.get("name") for label in row.get("labels", []) if isinstance(label, dict)}:
            continue
        number = row.get("number")
        if not isinstance(number, int):
            raise QueueError("queued PR has no number")
        admission = _admission(_events(root, repo, number), number)
        if admission is None:
            raise QueueError(f"queued PR #{number} lacks a valid admission")
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
    queue = _queued(root, repo)
    for index, (_, candidate, _) in enumerate(queue, 1):
        if candidate == number:
            labels = {label.get("name") for label in pr.get("labels", []) if isinstance(label, dict)}
            active = index == 1 and ACTIVE in labels
            return {"state": "active" if active else "waiting", "number": number, "position": index, "owner": "publication-queue workflow" if active else None}
    return {"state": "blocked", "number": number, "reason": "admitted PR lacks queue label"}



def candidate_status(root: Path, number: int, *, repo: str | None = None) -> dict[str, Any]:
    """Observe a lifecycle handoff without changing v1 queue consumers."""
    repo = repo or _repo(root)
    pr = _pr(root, repo, number)
    comments = _comments(root, repo, number)
    head = pr.get("head", {}).get("sha", "")
    # gh uses 1 for failed checks and 8 for pending checks. Those are readable
    # snapshots, not transport failures. Leave the legacy worker observer alone.
    response = subprocess.run(
        ["gh", "pr", "checks", str(number), "--required", "--json", "name,state,workflow,link"],
        cwd=root, text=True, capture_output=True, check=False,
        stdin=subprocess.DEVNULL,
    )
    checks = {"head": head, "kind": "unknown", "detail": "required checks unavailable"}
    if response.returncode in {0, 1, 8}:
        try:
            rows = json.loads(response.stdout)
        except json.JSONDecodeError:
            rows = None
        if isinstance(rows, list):
            observed = _classify_required_checks(rows)
            checks.update(kind=observed.kind, detail=observed.detail, checks=list(observed.checks))
    # A concurrent push invalidates this observation, including every gate.
    if _pr(root, repo, number).get("head", {}).get("sha") != head:
        checks["head"] = None
    return _derive(root, pr, comments, checks)


def lifecycle_summary(root: Path, number: int) -> dict[str, Any]:
    """Compact derived lifecycle state for task status, including exact-head checks."""
    candidate = candidate_status(root, number)
    return {key: candidate.get(key) for key in ("state", "head", "red_gate", "attempts", "next_action", "reason")}


def requirement_status(root: Path, requirement: str) -> dict[str, Any]:
    """List shared candidate generations by canonical branch identity, read-only."""
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
    repo = _repo(root)
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
    if admission.get("head") != run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip():
        # After local fast-forward recovery the current head is a coordinator
        # descendant, so a matching update marker is also accepted.
        updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
        if not updates or updates[-1].get("head") != run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip():
            raise QueueError("local task head is not the admitted or proven coordinator head")
    return status(root, data["number"])


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
    if run_git(["merge-base", "--is-ancestor", local, remote_head], cwd=root, check=False).returncode:
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
        require_composition_finalized(root, repo, number, head)
    if head != proven:
        # A runner can die after GitHub updates the branch but before it writes
        # the update comment. Recover only a clean merge of proven head + main.
        run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
        parents = run_git(["rev-list", "--parents", "-n", "1", head], cwd=root).stdout.split()
        if len(parents) != 3 or parents[1] != proven:
            raise QueueError("PR head changed outside coordinator control")
        prior_main = parents[2]
        run_git(["fetch", "origin", "main"], cwd=root)
        if run_git(["merge-base", "--is-ancestor", prior_main, "origin/main"], cwd=root, check=False).returncode:
            raise QueueError("unrecorded branch update is not based on main")
        expected_tree = run_git(["merge-tree", "--write-tree", proven, prior_main], cwd=root, check=False)
        actual_tree = run_git(["rev-parse", f"{head}^{{tree}}"], cwd=root).stdout.strip()
        if expected_tree.returncode or expected_tree.stdout.splitlines()[0].strip() != actual_tree:
            # A re-derivation push whose update marker was lost: accept only that exact shape.
            from post_review_finalization import derived_merge_only

            if not derived_merge_only(root, head, proven, prior_main, _task_paths(root, repo, admission)):
                raise QueueError("unrecorded branch update is not a clean main merge")
        _comment(root, repo, number, {"kind": "update", "previous": proven, "head": head, "base": prior_main})
    base = admission.get("base")
    if not isinstance(base, str) or len(base) != 40:
        raise QueueError("admission base is invalid")
    current_main = _main(root)
    if current_main == base and head == admission.get("head"):
        return head, current_main
    run_git(["fetch", "origin", "main"], cwd=root)
    if run_git(["merge-base", "--is-ancestor", base, current_main], cwd=root, check=False).returncode:
        raise QueueError("main no longer descends from admitted base")
    changed = set(run_git(["diff", "--name-only", f"{base}..{current_main}"], cwd=root).stdout.splitlines())
    task_paths = _task_paths(root, repo, admission)
    overlap = changed & task_paths
    from post_review_finalization import derived_spec_paths

    derived = derived_spec_paths(task_paths, overlap)
    if overlap != derived:
        # Path overlap alone never blocks: a clean merge is judged by the merge result and the
        # checks on the actual merged candidate; a real conflict becomes integration repair.
        derived = set()
    run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
    if derived and run_git(["merge-base", "--is-ancestor", current_main, head], cwd=root, check=False).returncode == 0:
        return head, current_main  # already re-derived on this main: nothing to redo
    if derived:
        # Only the candidate's own archive-derived spec paths overlap main: re-derive them on the
        # actual base. A failure is integration repair; checks still run on the result.
        from post_review_finalization import RederivationFailed, prepare_derived_specs

        _raise_if_owned_elsewhere(root, repo, number, head)
        try:
            return prepare_derived_specs(root, repo, number, pr, head, task_paths)
        except RederivationFailed as exc:
            raise IntegrationRepairNeeded(f"archive-derived spec re-derivation failed: {exc}") from exc
    # If the previously prepared head already contains current main, do not
    # perform a redundant update or trigger another CI run.
    run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
    if run_git(["merge-base", "--is-ancestor", current_main, head], cwd=root, check=False).returncode == 0:
        return head, current_main
    conflicts = merge_conflicts(root, head, current_main)
    if conflicts:
        raise IntegrationRepairNeeded("merge of current main conflicts in: " + ", ".join(conflicts[:8]))
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
    raise QueueError("GitHub branch update is still pending; retry coordinator")


def merge_conflicts(root: Path, head: str, main: str) -> list[str]:
    """Paths a deterministic merge of ``main`` into ``head`` cannot resolve (empty means a clean merge)."""
    done = run_git(["merge-tree", "--write-tree", "--name-only", "--no-messages", head, main], cwd=root, check=False)
    if done.returncode == 0:
        return []
    if done.returncode == 1:
        names = [line.strip() for line in done.stdout.splitlines()[1:] if line.strip()]
        return names or ["(conflict paths unavailable)"]
    raise QueueError("cannot evaluate the merge of main: " + (done.stderr or done.stdout).strip()[:200])


def worker(root: Path) -> dict[str, Any]:
    """Integrate ready candidates one at a time; a candidate that cannot proceed never stalls the rest.

    A candidate owned by other lifecycle work, blocked, awaiting finalization or integration
    repair is skipped and the next ready candidate is evaluated in the same run. A candidate
    that holds final integration ownership (checks pending, main moved, merge accepted) ends
    the run so at most one candidate integrates at a time.
    """
    repo = _repo(root)
    queue = _queued(root, repo)
    if not queue:
        return {"state": "empty"}
    skipped: list[str] = []
    blocked: dict[str, Any] | None = None
    # At most one candidate holds final integration ownership: resume the one
    # already active before granting ownership to any other.
    observed_prs = {number: _pr(root, repo, number) for _, number, _ in queue}

    def active(number: int) -> bool:
        return ACTIVE in {label.get("name") for label in observed_prs[number].get("labels", []) if isinstance(label, dict)}

    queue = sorted(queue, key=lambda item: not active(item[1]))
    for _, number, admission in queue:
        pr = observed_prs[number]
        comments = _comments(root, repo, number)
        identity = (_latest(root, number, comments) or {}).get("task_identity", {})
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
                publish_job(root, repo, number, "repair", current["head"], task_identity=current["task_identity"],
                            attempt=max(1, current.get("attempts", {}).get("repair", 0) + 1))
                return {"state": "repair-pending", "number": number}
            if current["state"] in {"contribution-integration-pending", "contribution-integrated"}:
                try:
                    outcome = merge_reviewed_contribution(root, repo, current)
                except (ContributionError, QueueError) as exc:
                    skipped.append(f"#{number} contribution: {exc}")
                    continue
                _label(root, repo, number, QUEUE, present=False)
                return outcome
            skipped.append(f"#{number} contribution: {current['state']}")
            continue
        if pr.get("merged"):
            _label(root, repo, number, QUEUE, present=False)
            return {"state": "merged", "number": number}
        # Without any v2 record the v1 admission alone governs (it reads as ready).
        has_v2 = any(str(row.get("body", "")).startswith(V2_PREFIX) for row in comments)
        current = _derive(root, pr, comments) if has_v2 else {"state": "ready"}
        if has_v2 and str(current.get("reason", "")).startswith("recover validated integration-repair push"):
            # A repair job pushed its validated result but was interrupted before advancing: record it.
            from integration_contour import recover_integration_repair

            if recover_integration_repair(root, repo, number, pr, comments):
                comments = _comments(root, repo, number)
                current = _derive(root, pr, comments)
        if current["state"] == "blocked-escalation" and current.get("reason", "").startswith("malformed marker"):
            blocked = _block(root, repo, number, current["reason"])
            skipped.append(f"#{number} blocked: {current['reason']}"[:300])
            continue
        # Only a record for the exact current head can hand the candidate to other
        # work; otherwise _prepare must still recover an interrupted branch update.
        exact_head_record = current.get("task_identity") is not None and current.get("head") == pr.get("head", {}).get("sha")
        newest = (_latest(root, number, comments) or {}) if has_v2 else {}
        if newest.get("state") in CLAIM_STATES:
            # A review/repair claim on an earlier head still owns the candidate:
            # never prepare (update or block) it under that work.
            skipped.append(f"#{number} {newest['state']} claim on {str(newest.get('head'))[:12]}")
            if active(number):
                _label(root, repo, number, ACTIVE, present=False)  # relinquish to the claiming work
            continue
        if exact_head_record and (current["state"] in NOT_INTEGRABLE or review_owned(current)):
            # A candidate owned by other work does not hold up the rest of the queue.
            skipped.append(f"#{number} {current['state']}: {current['next_action']}")
            if current["state"] == "integration-repair-pending" and not current.get("next_job"):
                # Interrupted between the state record and its job: publish the missing job (idempotent).
                try:
                    publish_job(root, repo, number, "integration-repair", current["head"],
                                task_identity=current["task_identity"],
                                attempt=max(1, current.get("attempts", {}).get("integration-repair", 1)))
                except QueueError:
                    pass
            if active(number):
                _label(root, repo, number, ACTIVE, present=False)
            continue
        outcome = _integrate(root, repo, number, admission, pr)
        if outcome.pop("released", False):
            skipped.append(f"#{number} {outcome.get('state')}: {outcome.get('reason', '')}"[:300])
            if outcome.get("state") == "blocked":
                blocked = outcome
            continue
        if skipped:
            outcome["skipped"] = skipped
        return outcome
    if blocked is not None:
        return {**blocked, "skipped": skipped}  # the run still reports a block (non-zero exit), after trying the rest
    return {"state": "waiting", "reason": "no integrable candidate; " + "; ".join(skipped)}


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
                raise QueueError("required check state is unknown: " + state.detail)
            if time.monotonic() >= deadline:
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
        result = subprocess.run(["gh", "pr", "merge", str(number), "--squash", "--match-head-commit", head], cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
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
            return {"state": "waiting", "number": number, "reason": "protected merge refused; will re-evaluate: " + (result.stderr.strip() or "unknown")[:300]}
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
    except (QueueError, subprocess.CalledProcessError) as exc:
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
    lineage = _latest(root, number, comments) or {}
    spent = max(current.get("attempts", {}).get("integration-repair", 0),
                lineage.get("attempts", {}).get("integration-repair", 0))
    _label(root, repo, number, ACTIVE, present=False)
    if spent >= MAX_INTEGRATION_REPAIRS:
        return _block(root, repo, number,
                      f"integration repair exhausted after {spent} attempts: {exc}"[:500], head=head_now)
    fallback = current.get("task_identity") or lineage.get("task_identity") or {
        "branch": admission.get("branch"), "head": head_now}
    try:
        _transition(root, repo, number, "integration-repair-pending", head_now, task_identity=fallback,
                    red_gate={"name": exc.gate, "identity": head_now, "evidence": str(exc)[:500]},
                    set_attempts={"integration-repair": spent + 1},
                    refuse_from=CLAIM_STATES, cross_head_claims=True)
        publish_job(root, repo, number, "integration-repair", head_now,
                    task_identity=fallback, attempt=spent + 1)
    except LifecycleOwnershipChanged:
        pass
    return {"state": "waiting", "number": number, "reason": str(exc)}


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
    sub.add_parser("worker")
    args = parser.parse_args()
    root = current_worktree_root()
    if args.command == "worker":
        use_default_friction_sink(root)  # real coordinator runs record friction automatically
    try:
        if args.command == "admit":
            result = admit(root, args.pr, args.head)
        elif args.command == "status":
            result = requirement_status(root, args.requirement) if args.requirement else candidate_status(root, args.pr)
        else:
            result = worker(root)
    except QueueError as exc:
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
    return 0 if result.get("state") in {"merged", "empty", "queued", "active", "waiting", "not-admitted"} else 2





def branch_head(root: Path, branch: str) -> str:
    result = run_git(["ls-remote", "origin", f"refs/heads/{branch}"], cwd=root).stdout.split()
    if not result:
        raise QueueError("integration target branch is unavailable")
    return result[0]


def require_composition_finalized(root: Path, repo: str, number: int, head: str) -> None:
    import tempfile
    from lifecycle_workers import prepare_checkout
    from requirement_composition import candidate_manifest, require_final_gates
    from requirement_contributions import ContributionError

    current = _derive(root, _pr(root, repo, number), _comments(root, repo, number))
    identity = current.get("task_identity")
    if not isinstance(identity, dict) or identity.get("kind") != "requirement-composition":
        raise QueueError("Requirement publication lacks composition identity")
    try:
        with tempfile.TemporaryDirectory(prefix="requirement-merge-gates-") as temporary:
            checkout = prepare_checkout(f"https://github.com/{repo}.git", temporary, "harness", head)
            manifest = candidate_manifest(checkout, identity["requirement"])
            require_final_gates(checkout, manifest, current, head)
    except ContributionError as exc:
        raise QueueError(str(exc)) from exc


def refresh_composition_checks(root: Path, repo: str, number: int, head: str) -> None:
    import tempfile
    from lifecycle_workers import prepare_checkout
    from requirement_composition import candidate_manifest, advance_final_publication

    candidate = _derive(root, _pr(root, repo, number), _comments(root, repo, number))
    identity = candidate.get("task_identity", {})
    with tempfile.TemporaryDirectory(prefix="composition-main-refresh-") as temporary:
        checkout = prepare_checkout(f"https://github.com/{repo}.git", temporary, "harness", head)
        manifest = candidate_manifest(checkout, identity["requirement"])
    result = advance_final_publication(root, repo, manifest, head, number, adapter=sys.modules[__name__], enqueue=False)
    if result["status"] != "ready":
        raise QueueError("Requirement final-head checks await fresh composition gates")


if __name__ == "__main__":
    raise SystemExit(main())
