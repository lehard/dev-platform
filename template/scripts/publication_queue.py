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
from candidate_lifecycle import CLAIM_STATES, PREFIX as V2_PREFIX, STATES, latest_record, build_handoff_record, derive_candidate, label_projection, marker_body, render_status

PREFIX = "dev-platform-publication-queue:v1 "
QUEUE = "publication:queued"
ACTIVE = "publication:active"
BLOCKED = "publication:blocked"
WORKFLOW = ".github/workflows/publication-queue.yml"
CHECK_WAIT_SECONDS = 240


class QueueError(RuntimeError):
    pass


class LifecycleOwnershipChanged(QueueError):
    """Another lifecycle job took the candidate between observation and transition."""


def _gh(root: Path, *args: str, data: dict[str, str] | None = None) -> Any:
    cmd = ["gh", *args]
    if data:
        for key, value in data.items():
            cmd += ["-f", f"{key}={value}"]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
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


def trusted_writers(root: Path, comments: list[dict[str, Any]]) -> frozenset[str]:
    """MEMBER/COLLABORATOR marker authors whose repository write permission is proven."""
    repo: str | None = None
    writers: set[str] = set()
    for row in comments:
        user = row.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        body = str(row.get("body", ""))
        if (not isinstance(login, str) or row.get("author_association") not in {"MEMBER", "COLLABORATOR"}
                or not body.startswith(("dev-platform-publication-queue:v1 ", V2_PREFIX))):
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
        result = subprocess.run(["gh", "api", "-X", "DELETE", f"repos/{repo}/issues/{number}/labels/{label.replace(':', '%3A')}"], cwd=root, capture_output=True, text=True)
        if result.returncode and "404" not in result.stderr:
            raise QueueError(result.stderr.strip() or "cannot remove publication label")


def _transition(
    root: Path, repo: str, number: int, state: str, head: str, *,
    task_identity: str | dict[str, Any], red_gate: dict[str, Any] | None = None,
    gates: dict[str, Any] | None = None, attempt: str | None = None,
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
    if previous.get("state") == state and red_gate in (None, previous.get("red_gate")) and not new_gates and not new_job:
        _project_lifecycle_label(root, repo, number, observed, state)
        return previous
    merged_gates = {**previous.get("gates", {}), **(gates or {})}
    attempts = dict(previous.get("attempts") or lineage.get("attempts") or {})
    if attempt is not None and previous.get("state") != state:
        attempts[attempt] = attempts.get(attempt, 0) + 1
    record = build_handoff_record(
        number=number, state=state, head=head,
        task_identity=(previous.get("task_identity") or lineage.get("task_identity") or task_identity)
        if inherit_identity else task_identity,
        gates=merged_gates, red_gate=red_gate,
        not_reverified=list(previous.get("not_reverified") or lineage.get("not_reverified") or []),
        attempts=attempts,
        next_job=next_job if next_job is not None else (previous.get("next_job") if state == previous.get("state") else None),
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _gh(root, "api", "-X", "POST", f"repos/{repo}/issues/{number}/comments", data={"body": marker_body(record)})
    _project_lifecycle_label(root, repo, number, observed, state)
    return record


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
        subprocess.run(["gh", "label", "create", wanted, "--color", "c5def5", "--force"], cwd=root, capture_output=True, text=True)
        _label(root, repo, number, wanted, present=True)


# v2 states owned by other lifecycle work; the integration worker must not take them over.
# Escalation and integration repair must be resolved first; integration never clears a red gate.
NOT_INTEGRABLE = {
    "review-pending", "reviewing", "repair-pending", "repairing", "finalize-pending",
    "blocked-escalation", "integration-repair-pending",
}


def _ensure_labels(root: Path) -> None:
    for name, color in ((QUEUE, "a2eeef"), (ACTIVE, "fbca04"), (BLOCKED, "b60205")):
        result = subprocess.run(["gh", "label", "create", name, "--color", color, "--force"], cwd=root, capture_output=True, text=True)
        if result.returncode:
            raise QueueError(result.stderr.strip() or f"cannot ensure label {name}")


def _pr(root: Path, repo: str, number: int) -> dict[str, Any]:
    data = _gh(root, "api", f"repos/{repo}/pulls/{number}")
    if not isinstance(data, dict) or data.get("number") != number:
        raise QueueError(f"PR #{number} is unavailable")
    return data


def _main(root: Path) -> str:
    result = run_git(["ls-remote", "origin", "refs/heads/main"], cwd=root)
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


def admit(root: Path, number: int, expected_head: str) -> dict[str, Any]:
    repo = _repo(root)
    pr = _pr(root, repo, number)
    if pr.get("state") != "open" or pr.get("base", {}).get("ref") != "main" or pr.get("head", {}).get("sha") != expected_head:
        raise QueueError("queue admission requires one open PR at the exact validated head against main")
    branch = pr.get("head", {}).get("ref")
    if not isinstance(branch, str) or not branch.startswith("agent/"):
        raise QueueError("queue admission requires an owned task branch")
    events = _events(root, repo, number)
    admitted = _admission(events, number)
    if admitted:
        if admitted.get("head") != expected_head:
            raise QueueError("PR has an earlier or ambiguous admission; resolve it before re-admission")
    else:
        base = _main(root)
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
            _transition(root, repo, number, "ready", expected_head, inherit_identity=False,
                        refuse_from=STATES, **_admission_handoff(root, branch, expected_head))
        except LifecycleOwnershipChanged:
            pass  # lifecycle work recorded this head in the meantime; never rewind it
    _label(root, repo, number, QUEUE, present=True)
    return {"number": number, "position_key": admitted["comment_id"], "head": expected_head, "state": "queued"}


def _queued(root: Path, repo: str) -> list[tuple[int, int, dict[str, Any]]]:
    rows = _gh(root, "pr", "list", "--state", "open", "--limit", "100", "--json", "number,labels")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise QueueError("open PR inventory is unavailable or exceeds the bounded limit")
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
    )
    if listed.returncode:
        raise QueueError(listed.stderr.strip() or "Requirement candidate inventory is unavailable")
    # Shared candidates plus the Requirement's own child branches, which carry a
    # single-child (or not yet composed) publication directly.
    from managed_work_identity import parent_identity

    child_prefix = "agent/" + parent_identity(requirement).lower() + "-t"
    children = re.escape(child_prefix) + r"[1-9][0-9]*-[A-Za-z0-9][A-Za-z0-9._-]*"
    pattern = re.compile(re.escape(branch) + r"(?:-[0-9a-f]{12})?|" + children if branch else children)
    numbers = sorted({int(number) for number, _, ref in (line.partition("\t") for line in listed.stdout.splitlines())
                      if number.isdigit() and pattern.fullmatch(ref)})
    result: dict[str, Any] = {"requirement": requirement, "candidates": [candidate_status(root, number, repo=repo) for number in numbers]}
    if lineage_note:
        result["shared_lineage"] = lineage_note
    return result


def local_status(root: Path, branch: str) -> dict[str, Any] | None:
    """Observe this task's admitted PR even after the coordinator updates its head."""
    result = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "number,baseRefName,headRefName"],
        cwd=root, text=True, capture_output=True, check=False,
    )
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


def _prepare(root: Path, repo: str, number: int, admission: dict[str, Any], pr: dict[str, Any]) -> tuple[str, str]:
    head = pr.get("head", {}).get("sha")
    if not isinstance(head, str) or len(head) != 40:
        raise QueueError("PR head is unavailable")
    events = _events(root, repo, number)
    updates = [e for e in events if e.get("kind") == "update" and e.get("comment_id", 0) > admission["comment_id"]]
    proven = admission.get("head") if not updates else updates[-1].get("head")
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
    overlap = changed & _task_paths(root, repo, admission)
    if overlap:
        raise QueueError("main changed task paths: " + ", ".join(sorted(overlap)[:8]))
    # If the previously prepared head already contains current main, do not
    # perform a redundant update or trigger another CI run.
    run_git(["fetch", "origin", pr["head"]["ref"]], cwd=root)
    if run_git(["merge-base", "--is-ancestor", current_main, head], cwd=root, check=False).returncode == 0:
        return head, current_main
    # Last observation before mutating the branch: never update a head that review
    # or repair claimed meanwhile (atomic job claims arrive with the worker contract).
    _raise_if_owned_elsewhere(root, repo, number, head)
    _gh(root, "api", "-X", "PUT", f"repos/{repo}/pulls/{number}/update-branch", data={"expected_head_sha": head})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        observed = _pr(root, repo, number).get("head", {}).get("sha")
        if isinstance(observed, str) and observed != head:
            _comment(root, repo, number, {"kind": "update", "previous": head, "head": observed, "base": current_main})
            return observed, current_main
        time.sleep(3)
    raise QueueError("GitHub branch update is still pending; retry coordinator")


def worker(root: Path) -> dict[str, Any]:
    repo = _repo(root)
    queue = _queued(root, repo)
    if not queue:
        return {"state": "empty"}
    skipped: list[str] = []
    # At most one candidate holds final integration ownership: resume the one
    # already active before granting ownership to any other.
    observed_prs = {number: _pr(root, repo, number) for _, number, _ in queue}

    def active(number: int) -> bool:
        return ACTIVE in {label.get("name") for label in observed_prs[number].get("labels", []) if isinstance(label, dict)}

    queue = sorted(queue, key=lambda item: not active(item[1]))
    for _, number, admission in queue:
        pr = observed_prs[number]
        if pr.get("merged"):
            _label(root, repo, number, QUEUE, present=False)
            return {"state": "merged", "number": number}
        comments = _comments(root, repo, number)
        # Without any v2 record the v1 admission alone governs (it reads as ready).
        has_v2 = any(str(row.get("body", "")).startswith(V2_PREFIX) for row in comments)
        current = _derive(root, pr, comments) if has_v2 else {"state": "ready"}
        if current["state"] == "blocked-escalation" and current.get("reason", "").startswith("malformed marker"):
            return _block(root, repo, number, current["reason"])
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
        if exact_head_record and current["state"] in NOT_INTEGRABLE:
            # A candidate owned by other work does not hold up the rest of the queue.
            skipped.append(f"#{number} {current['state']}: {current['next_action']}")
            if active(number):
                _label(root, repo, number, ACTIVE, present=False)
            continue
        break
    else:
        return {"state": "waiting", "reason": "no integrable candidate; " + "; ".join(skipped)}
    _label(root, repo, number, ACTIVE, present=True)
    try:
        head, base = _prepare(root, repo, number, admission, pr)
        identity = {"branch": admission.get("branch"), "head": head}
        _transition(root, repo, number, "integrating", head, task_identity=identity, attempt="integration",
                    refuse_from=NOT_INTEGRABLE, cross_head_claims=True,
                    next_job={"kind": "integration", "claim": "publication-queue workflow", "head": head})
        deadline = time.monotonic() + CHECK_WAIT_SECONDS
        while True:
            state = required_check_state_for_ref(root, os.environ.copy(), str(number), head)
            if state.kind == "passed":
                checks_evidence = state.detail or "required checks passed"
                break
            if state.kind in {"failed", "not_registered"}:
                # Review or repair may have claimed the head while checks ran.
                _raise_if_owned_elsewhere(root, repo, number, head)
            if state.kind == "failed":
                return _block(root, repo, number, "required check failed: " + state.detail, head=head)
            if state.kind == "not_registered":
                return _block(root, repo, number, "required check is not registered for the PR head", head=head)
            if state.kind == "unknown":
                raise QueueError("required check state is unknown: " + state.detail)
            if time.monotonic() >= deadline:
                return {"state": "waiting", "number": number, "reason": "required CI pending"}
            time.sleep(10)
        if _main(root) != base or _pr(root, repo, number).get("head", {}).get("sha") != head:
            return {"state": "waiting", "number": number, "reason": "main or PR head moved; coordinator will re-evaluate"}
        # Review or repair may have claimed this head during the check wait.
        _raise_if_owned_elsewhere(root, repo, number, head)
        result = subprocess.run(["gh", "pr", "merge", str(number), "--squash", "--match-head-commit", head], cwd=root, text=True, capture_output=True)
        if _pr(root, repo, number).get("merged"):
            _label(root, repo, number, ACTIVE, present=False)
            _label(root, repo, number, QUEUE, present=False)
            try:
                _transition(root, repo, number, "merged", head, task_identity=identity,
                            gates={"required-checks": {"result": "passed", "identity": head, "evidence": checks_evidence}})
            except QueueError:
                # The merge is the authoritative fact; a lost record must not turn it into a block.
                pass
            return {"state": "merged", "number": number, "head": head}
        if result.returncode:
            return {"state": "waiting", "number": number, "reason": "protected merge refused; will re-evaluate: " + (result.stderr.strip() or "unknown")[:300]}
        return {"state": "waiting", "number": number, "reason": "merge accepted; awaiting GitHub confirmation"}
    except LifecycleOwnershipChanged as exc:
        _label(root, repo, number, ACTIVE, present=False)
        return {"state": "waiting", "number": number, "reason": str(exc)}
    except (QueueError, subprocess.CalledProcessError) as exc:
        head_now = pr.get("head", {}).get("sha")
        try:
            # Never block a candidate that review or repair claimed meanwhile.
            if isinstance(head_now, str):
                _raise_if_owned_elsewhere(root, repo, number, head_now)
        except LifecycleOwnershipChanged as owned:
            _label(root, repo, number, ACTIVE, present=False)
            return {"state": "waiting", "number": number, "reason": str(owned)}
        except QueueError as unobservable:
            # Ownership cannot be observed: never overwrite a possible claim with a
            # block; the next coordinator run re-evaluates.
            _label(root, repo, number, ACTIVE, present=False)
            return {"state": "waiting", "number": number,
                    "reason": f"{exc}; lifecycle ownership unobservable: {unobservable}"}
        return _block(root, repo, number, str(exc))


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


if __name__ == "__main__":
    raise SystemExit(main())
