from __future__ import annotations

"""Reconcile an authoritative pending Dev Platform rollout PR before new work starts.

A pending rollout PR is operational platform-delivery state, not product
backlog work. Before a platform-owned task branch/worktree is created, this
module checks whether the current repository has one, and -- only when it is
unambiguously green -- merges it through ordinary non-bypass GitHub policy and
synchronizes the local integration branch. An ambiguous or unsafe rollout
blocks new work with an explicit, resumable state instead of being silently
ignored or force-adopted.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finish_task import serialized_integration, sync_after_remote_pr_merge
from project_publish import request_protected_merge
from publication_state import current_pr_head, github_repo_name, required_check_state_for_ref
from rollout_identity import RolloutPR, authoritative_pending_rollout, candidate_rollout_prs, list_open_prs

# Structured pre-task rollout states (see openspec/changes/reconcile-pending-rollout-before-task).
NONE = "none"
PENDING_CHECKS = "pending_checks"
BLOCKED = "blocked"
SAFE_TO_ADOPT = "safe_to_adopt"
MERGED_NEEDS_LOCAL_SYNC = "merged_needs_local_sync"
RECONCILED = "reconciled"

MAIN_LOCK_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class RolloutPreflightResult:
    state: str
    detail: str = ""
    pr: RolloutPR | None = None


def rollout_bot_login(config: dict[str, Any]) -> str:
    tools = config.get("tools") if isinstance(config.get("tools"), dict) else {}
    rollout = tools.get("rollout") if isinstance(tools.get("rollout"), dict) else {}
    return str(rollout.get("bot_login") or "")


def observe_pending_rollout(root: Path, config: dict[str, Any], env: dict[str, str] | None) -> RolloutPreflightResult:
    """Read-only: determine rollout state without merging or syncing anything.

    Runs for every harness mode -- `agent_doctor.py` uses it to surface
    pending-rollout state even for `harness_mode=project`, which keeps its own
    task/worktree entrypoint and never calls `reconcile_pending_rollout`
    (the mutating merge-and-sync step, gated platform-owned-only by its sole
    caller, `start_task.py`).
    """
    main_branch = str(config.get("main_branch", "main"))
    # Unlike an observed candidate PR with ambiguous ownership, being unable to
    # reach GitHub at all is not evidence of a pending rollout -- fail open with
    # a note rather than blocking every task start whenever `gh` is briefly
    # unavailable. `agent_doctor.py`'s existing `require_origin`/gh-auth checks
    # are the actual gate for a genuinely misconfigured platform-owned repo.
    if env is None:
        return RolloutPreflightResult(NONE, detail="GitHub CLI/API authentication is unavailable; skipped the pending-rollout check")
    repository = github_repo_name(root, env)
    if repository is None:
        return RolloutPreflightResult(NONE, detail="could not resolve the current GitHub repository from `gh repo view`; skipped the pending-rollout check")

    open_prs = list_open_prs(repository, main_branch, env=env)
    candidates = candidate_rollout_prs(open_prs, base_branch=main_branch)
    if not candidates:
        return RolloutPreflightResult(NONE)

    bot_login = rollout_bot_login(config)
    if not bot_login:
        return RolloutPreflightResult(
            BLOCKED,
            detail=(
                f"{len(candidates)} open PR(s) match the reserved rollout branch/base contract, but "
                "tools.rollout.bot_login is not configured in .dev-platform.toml, so the expected automation "
                "identity cannot be confirmed; resolve manually or update the platform config"
            ),
        )

    authoritative = authoritative_pending_rollout(open_prs, repository=repository, base_branch=main_branch, expected_bot=bot_login)
    if authoritative is None:
        return RolloutPreflightResult(
            BLOCKED,
            detail=(
                f"{len(candidates)} open PR(s) match the reserved rollout branch/base contract for {repository}, but "
                f"none match the expected automation identity {bot_login!r}; refusing to guess ownership"
            ),
        )

    check_state = required_check_state_for_ref(root, env, authoritative.branch, authoritative.head_sha)
    if check_state.kind == "failed":
        return RolloutPreflightResult(
            BLOCKED, detail=f"rollout PR #{authoritative.number} required checks failed: {check_state.detail}", pr=authoritative,
        )
    if check_state.kind == "passed":
        return RolloutPreflightResult(
            SAFE_TO_ADOPT, detail=f"rollout PR #{authoritative.number} ({authoritative.version}) is green and safe to adopt", pr=authoritative,
        )
    if check_state.kind in ("pending", "not_registered"):
        return RolloutPreflightResult(
            PENDING_CHECKS,
            detail=f"rollout PR #{authoritative.number} ({authoritative.version}) required checks are not yet complete ({check_state.kind})",
            pr=authoritative,
        )
    return RolloutPreflightResult(
        BLOCKED, detail=f"rollout PR #{authoritative.number} required-check state is unknown: {check_state.detail}", pr=authoritative,
    )


def _merge_rollout_pr(root: Path, env: dict[str, str], pr: RolloutPR, remote: str = "origin") -> tuple[str, str]:
    expected_head = current_pr_head(root, env, pr.branch)
    if expected_head is None:
        return "unavailable", f"could not read rollout PR #{pr.number}'s current head from GitHub"
    try:
        result = request_protected_merge(root, env, pr.branch, remote, expected_head)
    except SystemExit as exc:
        return "unavailable", str(exc)
    return result, ""


def _synchronize_local_main(root: Path, config: dict[str, Any]) -> tuple[bool, str]:
    main_branch = str(config.get("main_branch", "main"))
    try:
        with serialized_integration(root, config, timeout_seconds=MAIN_LOCK_TIMEOUT_SECONDS):
            sync_after_remote_pr_merge(root, root, config, main_branch)
    except SystemExit as exc:
        return False, str(exc)
    return True, ""


def reconcile_pending_rollout(root: Path, config: dict[str, Any], env: dict[str, str] | None) -> RolloutPreflightResult:
    """Observe, and when unambiguously safe, merge and synchronize a pending rollout.

    Never force-pushes, bypasses required checks/review, or merges a rollout
    whose head changed since observation -- `request_protected_merge` re-reads
    the PR's exact current head immediately before requesting the merge.
    """
    observed = observe_pending_rollout(root, config, env)
    if observed.state != SAFE_TO_ADOPT:
        return observed
    assert observed.pr is not None and env is not None

    merge_result, merge_detail = _merge_rollout_pr(root, env, observed.pr)
    if merge_result != "merged":
        return RolloutPreflightResult(
            BLOCKED,
            detail=merge_detail or f"rollout PR #{observed.pr.number} could not be merged through ordinary GitHub reconciliation",
            pr=observed.pr,
        )

    synced, sync_detail = _synchronize_local_main(root, config)
    if not synced:
        return RolloutPreflightResult(
            MERGED_NEEDS_LOCAL_SYNC,
            detail=(
                f"rollout PR #{observed.pr.number} ({observed.pr.version}) is merged on GitHub, but the local "
                f"integration branch could not be synchronized yet: {sync_detail}; rerun to retry"
            ),
            pr=observed.pr,
        )
    return RolloutPreflightResult(
        RECONCILED,
        detail=f"merged and synchronized rollout PR #{observed.pr.number} ({observed.pr.version}) before starting new work",
        pr=observed.pr,
    )
