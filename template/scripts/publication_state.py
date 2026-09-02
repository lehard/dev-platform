from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from _platform_common import pr_merge_mode, run_git


PR_VIEW_FIELDS = "number,url,state,headRefOid,baseRefName,headRefName,headRepositoryOwner,autoMergeRequest,mergeStateStatus"

PASSED_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPING", "SKIPPED"}
FAILED_CHECK_STATES = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", "ERROR"}
PENDING_CHECK_STATES = {"EXPECTED", "PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}


@dataclass(frozen=True)
class RequiredCheckState:
    """Normalized, structured GitHub state for required checks on one PR head."""

    kind: str
    detail: str = ""
    checks: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class PrRef:
    """Stable pull-request cursor shared by platform publication and rollout code.

    Defined here -- in the always-platform-owned publication-state module that
    every harness renders -- rather than in ``project_publish.py`` so platform
    lifecycle code (for example ``rollout_preflight.py``) can name the type
    without importing a publication module that a ``harness_mode=project``
    repository is allowed to keep project-owned. ``project_publish.py``
    re-exports it for backwards compatibility.
    """

    number: int | None
    url: str
    already_merged: bool = False

    @property
    def ref(self) -> str:
        if self.number is not None:
            return str(self.number)
        if self.url.startswith(("https://", "http://")):
            return self.url
        raise SystemExit("Exact PR discovery did not return a stable PR number or URL; refusing branch-name fallback.")


def required_check_state(root: Path, env: dict[str, str], current: str) -> RequiredCheckState:
    """Read required-check state from gh JSON, never from rendered CLI wording.

    `gh pr checks --required --json` delegates required-context selection to
    GitHub, and the preceding PR query proves those contexts belong to this
    local task head.  An unreadable API response is intentionally `unknown`.
    """
    local_head = run_git(["rev-parse", current], cwd=root, check=False)
    if local_head.returncode != 0:
        return RequiredCheckState("unknown", f"local task branch {current!r} is unavailable")
    lookup = find_exact_head_pr(root, env, current, "main", local_head.stdout.strip())
    # This compatibility helper has no base parameter. Publication paths use
    # required_check_state_for_ref directly; callers that need another base
    # must do the same rather than letting a branch name become proof.
    pr = lookup.exact_open
    if not lookup.available or pr is None:
        return RequiredCheckState("unknown", "GitHub exact PR state is unavailable")
    return required_check_state_for_ref(root, env, stable_pr_ref(pr), local_head.stdout.strip())


def _classify_required_checks(payload: list[Any]) -> RequiredCheckState:
    normalized = tuple(item for item in payload if isinstance(item, dict))
    if len(normalized) != len(payload):
        return RequiredCheckState("unknown", "GitHub required-check response contained an invalid check")
    if not normalized:
        return RequiredCheckState("not_registered")

    states = {str(item.get("state", "")).strip().upper() for item in normalized}
    if any(state in FAILED_CHECK_STATES for state in states):
        failed = ", ".join(str(item.get("name", "unnamed")) for item in normalized if str(item.get("state", "")).strip().upper() in FAILED_CHECK_STATES)
        return RequiredCheckState("failed", failed, normalized)
    if all(state in PASSED_CHECK_STATES for state in states):
        return RequiredCheckState("passed", checks=normalized)
    if all(state in PASSED_CHECK_STATES | PENDING_CHECK_STATES for state in states):
        return RequiredCheckState("pending", checks=normalized)
    return RequiredCheckState("unknown", "GitHub returned an unsupported required-check state", normalized)


def required_check_state_for_ref(root: Path, env: dict[str, str], ref: str, expected_head: str) -> RequiredCheckState:
    """Like `required_check_state`, but for a PR with no local checkout.

    `ref` may be a PR number, URL, or branch name that `gh pr view` accepts
    directly. The caller supplies `expected_head` (read fresh from GitHub, not
    from a local branch) to guard against the PR head changing between
    observation and this check -- used for rollout PR reconciliation, where
    the platform never checks out the PR's branch locally.
    """
    pr = subprocess.run(
        ["gh", "pr", "view", ref, "--json", "state,headRefOid"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if pr.returncode != 0:
        return RequiredCheckState("unknown", "GitHub PR state is unavailable")
    try:
        pr_payload = json.loads(pr.stdout)
    except json.JSONDecodeError:
        return RequiredCheckState("unknown", "GitHub PR state was not structured JSON")
    remote_head = str(pr_payload.get("headRefOid", "")).strip()
    if remote_head != expected_head:
        return RequiredCheckState("unknown", "GitHub PR head does not match the expected observed head")

    checks = subprocess.run(
        ["gh", "pr", "checks", ref, "--required", "--json", "name,state,workflow,link"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if checks.returncode != 0:
        return RequiredCheckState("unknown", "GitHub required-check state is unavailable")
    try:
        payload = json.loads(checks.stdout)
    except json.JSONDecodeError:
        return RequiredCheckState("unknown", "GitHub required-check state was not structured JSON")
    if not isinstance(payload, list):
        return RequiredCheckState("unknown", "GitHub required-check response was not a list")
    return _classify_required_checks(payload)


@dataclass(frozen=True)
class ExactHeadPrLookup:
    """Exact-head PR classification for one task branch/base pair.

    A matching PR is identified by repository/base branch plus task head
    branch and exact `headRefOid` -- never by title, body, or a remembered PR
    number alone. `available=False` means GitHub state could not be read;
    callers MUST fail closed rather than guessing publication state.
    """

    available: bool
    exact_open: dict[str, Any] | None = None
    exact_merged: dict[str, Any] | None = None
    stale_open: dict[str, Any] | None = None  # open PR for this branch/base, different head
    detail: str = ""


def stable_pr_ref(pr: dict[str, Any]) -> str:
    """Return the immutable PR handle required after exact-head discovery."""
    number = pr.get("number")
    if isinstance(number, int) and number > 0:
        return str(number)
    url = str(pr.get("url", "")).strip()
    if url.startswith(("https://", "http://")):
        return url
    raise ValueError("exact PR candidate has no stable number or URL")


def _pr_candidates(root: Path, env: dict[str, str], branch: str, base_branch: str) -> tuple[bool, list[dict[str, Any]], str]:
    """Enumerate structured PRs; branch filtering only narrows discovery.

    `gh pr view <branch>` is deliberately not used here: when a branch name is
    reused GitHub can select a historical merged PR.  The list response gives
    every candidate that must be compared against the full identity tuple.
    """
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "all", "--head", branch, "--base", base_branch,
         "--limit", "100", "--json", PR_VIEW_FIELDS],
        cwd=root, env=env, text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        return False, [], "GitHub PR candidate list is unavailable"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, [], "GitHub PR candidate list was not structured JSON"
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        return False, [], "GitHub PR candidate list was not a structured list"
    return True, payload, ""


def find_exact_head_pr(root: Path, env: dict[str, str], branch: str, base_branch: str, local_head: str) -> ExactHeadPrLookup:
    available, candidates, detail = _pr_candidates(root, env, branch, base_branch)
    if not available:
        return ExactHeadPrLookup(available=False, detail=detail)
    exact_open: dict[str, Any] | None = None
    exact_merged: dict[str, Any] | None = None
    stale_open: dict[str, Any] | None = None
    for candidate in candidates:
        # Validate filter fields in the payload as well; command-line filters
        # are an optimisation, never identity proof.
        if str(candidate.get("baseRefName", "")).strip() != base_branch:
            continue
        if str(candidate.get("headRefName", "")).strip() != branch:
            continue
        state = str(candidate.get("state", "")).strip().upper()
        head = str(candidate.get("headRefOid", "")).strip()
        pr = dict(candidate)
        pr["state"] = state
        pr["headRefOid"] = head
        try:
            stable_pr_ref(pr)
        except ValueError:
            return ExactHeadPrLookup(available=False, detail="GitHub exact PR candidate lacks a stable number or URL")
        if head == local_head and state == "OPEN":
            if exact_open is not None:
                return ExactHeadPrLookup(available=False, detail="multiple exact open PR candidates were returned")
            exact_open = pr
        elif head == local_head and state == "MERGED":
            if exact_merged is not None:
                return ExactHeadPrLookup(available=False, detail="multiple exact merged PR candidates were returned")
            exact_merged = pr
        elif state == "OPEN" and stale_open is None:
            stale_open = pr
    if exact_open is not None and exact_merged is not None:
        return ExactHeadPrLookup(
            available=False,
            detail="both open and merged PRs match the same branch/base/head identity",
        )
    return ExactHeadPrLookup(available=True, exact_open=exact_open, exact_merged=exact_merged, stale_open=stale_open)


def find_exact_local_branch_pr(root: Path, env: dict[str, str], branch: str, base_branch: str) -> ExactHeadPrLookup:
    """Find the exact PR for the branch currently registered by a local task.

    This binds the existing branch/base/exact-head publication identity in one
    place for callers that coordinate a task without checking out or changing
    its worktree.  A missing local branch is unavailable rather than an
    inferred terminal state, so consumers can retain their fail-closed claim.
    """
    local_head = run_git(["rev-parse", f"refs/heads/{branch}"], cwd=root, check=False)
    if local_head.returncode != 0:
        return ExactHeadPrLookup(available=False, detail=f"local task branch {branch!r} is unavailable")
    head = local_head.stdout.strip()
    if not head:
        return ExactHeadPrLookup(available=False, detail=f"local task branch {branch!r} has no readable head")
    return find_exact_head_pr(root, env, branch, base_branch, head)


def current_pr_head(root: Path, env: dict[str, str], ref: str) -> str | None:
    """Best-effort read of the PR's current headRefOid, for exact-head guards.

    Returns None on any unreadable response so callers do not fail closed on a
    transient read error alone; the merge command's own result is still the
    authoritative signal for whether the request was accepted.
    """
    result = subprocess.run(
        ["gh", "pr", "view", ref, "--json", "headRefOid", "--jq", ".headRefOid"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def pr_head_repository_owner(root: Path, env: dict[str, str], ref: str) -> str | None:
    """Read the exact PR head repository owner for reconciliation ownership checks."""
    result = subprocess.run(
        ["gh", "pr", "view", ref, "--json", "headRepositoryOwner"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    owner = payload.get("headRepositoryOwner") if isinstance(payload, dict) else None
    login = owner.get("login") if isinstance(owner, dict) else None
    return str(login).strip() if isinstance(login, str) and login.strip() else None


def github_repo_name(root: Path, env: dict[str, str]) -> str | None:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    name = result.stdout.strip()
    return name if result.returncode == 0 and name else None


def repo_auto_merge_capability(root: Path, env: dict[str, str]) -> bool | None:
    """Read-only capability probe: can this repository persist native auto-merge?

    Never mutates repository settings. Returns None when the capability cannot
    be determined (e.g. insufficient permissions or unreadable API response).
    """
    name = github_repo_name(root, env)
    if name is None:
        return None
    result = subprocess.run(
        ["gh", "api", f"repos/{name}", "--jq", ".allow_auto_merge"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def merge_durability_capability(config: dict[str, Any], env: dict[str, str] | None, root: Path) -> str:
    """One of: manual, remote_armed_capable, foreground_fallback, unknown."""
    if pr_merge_mode(config) != "auto":
        return "manual"
    if env is None:
        return "unknown"
    allowed = repo_auto_merge_capability(root, env)
    if allowed is True:
        return "remote_armed_capable"
    if allowed is False:
        return "foreground_fallback"
    return "unknown"


NOT_PUBLISHED = "not_published"
OPEN_CHECKS_PENDING = "open_checks_pending"
REMOTE_ARMED = "remote_armed"
BLOCKED = "blocked"
REMOTE_MERGED_LOCAL_PENDING = "remote_merged_local_pending"
COMPLETE = "complete"
GITHUB_UNAVAILABLE = "github_unavailable"


@dataclass(frozen=True)
class PublicationObservation:
    branch: str
    base_branch: str
    local_head: str | None = None
    remote_branch_head: str | None = None
    github_available: bool = True
    pr: dict[str, Any] | None = None
    pr_relationship: str = "none"  # none | exact_open | exact_merged | stale_open | unavailable
    required_check_kind: str | None = None
    required_check_detail: str = ""
    auto_merge_armed: bool = False
    remote_merged: bool = False
    local_main_head: str | None = None
    remote_main_head: str | None = None
    local_reconciliation_pending: bool = False
    bucket: str = NOT_PUBLISHED
    detail: str = ""


def _remote_ref_head(root: Path, remote: str, branch: str) -> str | None:
    """Observe a remote ref's head SHA via ls-remote, without mutating local refs."""
    configured = run_git(["remote", "get-url", remote], cwd=root, check=False)
    if configured.returncode != 0 or not configured.stdout.strip():
        return None
    result = run_git(["ls-remote", remote, branch], cwd=root, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0].strip()


def observe_publication(
    work_root: Path,
    integration_root: Path,
    env: dict[str, str] | None,
    branch: str,
    base_branch: str,
    remote: str = "origin",
) -> PublicationObservation:
    """Derive publication status purely from current local Git + GitHub state.

    Never pushes, creates/merges PRs, mutates the board, or writes local refs.
    """
    local_head_result = run_git(["rev-parse", "--verify", branch], cwd=work_root, check=False)
    local_head = local_head_result.stdout.strip() if local_head_result.returncode == 0 else None

    if env is None:
        return PublicationObservation(
            branch=branch,
            base_branch=base_branch,
            local_head=local_head,
            github_available=False,
            pr_relationship="unavailable",
            bucket=GITHUB_UNAVAILABLE,
            detail="GitHub CLI/API authentication is unavailable",
        )

    remote_branch_head = _remote_ref_head(work_root, remote, branch)

    if local_head is None:
        return PublicationObservation(
            branch=branch,
            base_branch=base_branch,
            remote_branch_head=remote_branch_head,
            bucket=NOT_PUBLISHED,
            detail=f"local branch {branch!r} does not exist",
        )

    lookup = find_exact_head_pr(work_root, env, branch, base_branch, local_head)
    local_main_head_result = run_git(["rev-parse", "--verify", base_branch], cwd=integration_root, check=False)
    local_main_head = local_main_head_result.stdout.strip() if local_main_head_result.returncode == 0 else None
    remote_main_head = _remote_ref_head(integration_root, remote, base_branch)

    if not lookup.available:
        return PublicationObservation(
            branch=branch,
            base_branch=base_branch,
            local_head=local_head,
            remote_branch_head=remote_branch_head,
            pr_relationship="unavailable",
            local_main_head=local_main_head,
            remote_main_head=remote_main_head,
            bucket=GITHUB_UNAVAILABLE,
            detail=lookup.detail,
        )

    if lookup.exact_merged is not None:
        pending = local_main_head is not None and remote_main_head is not None and local_main_head != remote_main_head
        return PublicationObservation(
            branch=branch,
            base_branch=base_branch,
            local_head=local_head,
            remote_branch_head=remote_branch_head,
            pr=lookup.exact_merged,
            pr_relationship="exact_merged",
            remote_merged=True,
            local_main_head=local_main_head,
            remote_main_head=remote_main_head,
            local_reconciliation_pending=pending,
            bucket=REMOTE_MERGED_LOCAL_PENDING if pending else COMPLETE,
        )

    if lookup.exact_open is not None:
        armed = lookup.exact_open.get("autoMergeRequest") is not None
        check_state = required_check_state_for_ref(
            work_root, env, stable_pr_ref(lookup.exact_open), local_head
        )
        if check_state.kind == "failed":
            bucket = BLOCKED
        elif armed:
            bucket = REMOTE_ARMED
        else:
            bucket = OPEN_CHECKS_PENDING
        return PublicationObservation(
            branch=branch,
            base_branch=base_branch,
            local_head=local_head,
            remote_branch_head=remote_branch_head,
            pr=lookup.exact_open,
            pr_relationship="exact_open",
            required_check_kind=check_state.kind,
            required_check_detail=check_state.detail,
            auto_merge_armed=armed,
            local_main_head=local_main_head,
            remote_main_head=remote_main_head,
            bucket=bucket,
        )

    detail = ""
    if lookup.stale_open is not None:
        detail = (
            f"an open PR exists for {branch} but its head {lookup.stale_open.get('headRefOid')} differs from the "
            f"current local head {local_head}: {lookup.stale_open.get('url')}"
        )
    return PublicationObservation(
        branch=branch,
        base_branch=base_branch,
        local_head=local_head,
        remote_branch_head=remote_branch_head,
        pr=lookup.stale_open,
        pr_relationship="stale_open" if lookup.stale_open is not None else "none",
        local_main_head=local_main_head,
        remote_main_head=remote_main_head,
        bucket=NOT_PUBLISHED,
        detail=detail,
    )


def status_payload(obs: PublicationObservation, durability: str) -> dict[str, Any]:
    """Sanitized structured status: no credentials, no raw arbitrary logs."""
    return {
        "branch": obs.branch,
        "base_branch": obs.base_branch,
        "local_head": obs.local_head,
        "remote_branch_head": obs.remote_branch_head,
        "github_available": obs.github_available,
        "pr_number": (obs.pr or {}).get("number") if obs.pr else None,
        "pr_url": (obs.pr or {}).get("url") if obs.pr else None,
        "pr_relationship": obs.pr_relationship,
        "required_check_kind": obs.required_check_kind,
        "required_check_detail": obs.required_check_detail,
        "auto_merge_armed": obs.auto_merge_armed,
        "remote_merged": obs.remote_merged,
        "local_main_head": obs.local_main_head,
        "remote_main_head": obs.remote_main_head,
        "local_reconciliation_pending": obs.local_reconciliation_pending,
        "status": obs.bucket,
        "merge_durability": durability,
        "detail": obs.detail,
    }


def status_text(obs: PublicationObservation, durability: str) -> str:
    lines = [
        f"branch: {obs.branch}",
        f"base_branch: {obs.base_branch}",
        f"local_head: {obs.local_head or 'none'}",
    ]
    if obs.pr is not None:
        lines.append(f"pr: #{obs.pr.get('number')} {obs.pr.get('url')} ({obs.pr_relationship})")
    else:
        lines.append("pr: none")
    lines.append(f"status: {obs.bucket}")
    if obs.required_check_kind:
        detail = f" ({obs.required_check_detail})" if obs.required_check_detail else ""
        lines.append(f"required_checks: {obs.required_check_kind}{detail}")
    lines.append(f"auto_merge_armed: {str(obs.auto_merge_armed).lower()}")
    lines.append(f"remote_merged: {str(obs.remote_merged).lower()}")
    lines.append(f"local_reconciliation_pending: {str(obs.local_reconciliation_pending).lower()}")
    lines.append(f"merge_durability: {durability}")
    if obs.detail:
        lines.append(f"detail: {obs.detail}")
    return "\n".join(lines)
