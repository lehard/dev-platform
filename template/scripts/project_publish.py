from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Callable, ContextManager

from _platform_common import (
    current_worktree_root,
    fetch_main,
    github_cli_env,
    main_root,
    pr_merge_mode,
    protected_main,
    publish_mode,
    read_platform_config,
    relation,
    require_origin,
    run_git,
    preflight,
)
from integration_state import guard_before_protected_merge
from publication_state import (
    ExactHeadPrLookup,
    PrRef,  # re-exported: the canonical definition lives in the always-platform-owned publication_state
    RequiredCheckState,
    find_exact_head_pr,
    required_check_state,
    required_check_state_for_ref,
    stable_pr_ref,
)
from managed_project_status import ManagedProjectStatusError, reconcile as reconcile_managed_project
try:
    from managed_task import ManagedTaskError, require_delivery_provenance
except ModuleNotFoundError:  # Compatibility while a pre-managed-intake render is being upgraded.
    class ManagedTaskError(RuntimeError):
        pass

    def require_delivery_provenance(root: Path):
        return None


DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"
CHECK_REGISTRATION_TIMEOUT_SECONDS = 90.0
CHECK_REGISTRATION_INTERVAL_SECONDS = 3.0
CHECK_COMPLETION_TIMEOUT_SECONDS = 600.0
CHECK_COMPLETION_INTERVAL_SECONDS = 5.0
MERGE_CONFIRM_TIMEOUT_SECONDS = 600.0
MERGE_CONFIRM_INTERVAL_SECONDS = 2.0
MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS = 3.0
PRE_MERGE_GUARD_TIMEOUT_SECONDS = 60.0


def _pr_ref(pr: dict, *, already_merged: bool = False) -> PrRef:
    # Validate the candidate before retaining it as a publication cursor.
    stable_pr_ref(pr)
    number = pr.get("number")
    return PrRef(number if isinstance(number, int) else None, str(pr.get("url", "")), already_merged)


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def require_gh_environment(root: Path, *, branch_pushed: bool = False) -> dict[str, str]:
    env = github_cli_env(root)
    if env is not None:
        return env
    suffix = " The validated feature branch is already pushed." if branch_pushed else ""
    raise SystemExit(
        "GitHub PR API authentication is unavailable."
        + suffix
        + " Install gh if needed, provide a valid GH_TOKEN/GITHUB_TOKEN, or configure a persistent gh/Git HTTPS credential."
    )


def publish_direct(root: Path, remote: str, main_branch: str) -> int:
    if os.environ.get(DIRECT_PUBLISH_GUARD) != "1":
        raise SystemExit(
            "Direct publication must be invoked by the validated finish_task lifecycle. "
            f"For an explicit emergency/operator override, set {DIRECT_PUBLISH_GUARD}=1 yourself."
        )
    integration = main_root()
    preflight(integration)
    if root != integration:
        raise SystemExit("Direct publication must run from the integration copy after local integration.")
    if branch(integration) != main_branch:
        raise SystemExit(f"Direct publication requires {main_branch!r} checked out.")
    if not clean(integration):
        raise SystemExit("Integration copy is dirty. Commit or remove changes before publishing.")
    require_origin(integration, remote)
    fetch_main(integration, remote, main_branch)
    remote_branch = f"{remote}/{main_branch}"
    state = relation(integration, main_branch, remote_branch)
    if state == "equal":
        print(f"Nothing to publish: {main_branch} already equals {remote_branch}.")
        return 0
    if state != "ahead":
        raise SystemExit(f"Refusing direct push: local {main_branch} vs {remote_branch} is {state}. Fetch/reconcile explicitly.")
    run_git(["push", remote, f"{main_branch}:{main_branch}"], cwd=integration)
    print(f"Published {main_branch} -> {remote}/{main_branch}.")
    return 0


def _validate_feature_branch(root: Path, remote: str, main_branch: str) -> str:
    current = branch(root)
    if not current or current == main_branch:
        raise SystemExit("PR publication requires a feature branch, not the integration branch.")
    if not clean(root):
        raise SystemExit("Task worktree is dirty. Commit or remove changes before publishing.")
    require_origin(root, remote)
    return current


def push_feature_branch(root: Path, remote: str, main_branch: str, *, require_fresh_base: bool) -> str:
    """Push the validated feature branch; the push itself is always safe/idempotent.

    `require_fresh_base` gates only the first-publication precondition that the
    branch already contains current `{remote}/{main_branch}`. Recovery of an
    already-existing exact-head PR passes `require_fresh_base=False`: that PR's
    `headRefOid` already proves this exact commit reached GitHub, so an
    already-published branch must not be blocked from resuming merely because
    the base advanced after that PR was opened -- pushing again is a harmless
    no-op fast-forward to the same commit.
    """
    preflight(root)
    current = _validate_feature_branch(root, remote, main_branch)
    fetch_main(root, remote, main_branch)
    if require_fresh_base and run_git(["merge-base", "--is-ancestor", f"{remote}/{main_branch}", current], cwd=root, check=False).returncode != 0:
        raise SystemExit(f"{current} does not contain current {remote}/{main_branch}. Rebase/update explicitly, rerun checks, then publish.")
    run_git(["push", "-u", remote, current], cwd=root)
    print(f"Published feature branch {current} -> {remote}/{current}.")
    return current


def ensure_pr(
    root: Path,
    env: dict[str, str],
    current: str,
    main_branch: str,
    title: str | None,
    body: str | None,
    expected_head: str,
    lookup: ExactHeadPrLookup | None = None,
) -> PrRef:
    """Reuse an exact-head PR if one exists; otherwise create one.

    Ownership is decided by repository/base branch + task head branch + exact
    `headRefOid`, never by title/body text or a remembered PR number. A create
    race against a concurrent publisher is resolved by re-observing GitHub and
    reusing whatever exact PR won, instead of producing a duplicate.
    """
    if lookup is None:
        lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if not lookup.available:
        raise SystemExit("GitHub PR state is unavailable; publication remains resumable without local-main mutation.")
    if lookup.exact_open is not None:
        url = str(lookup.exact_open.get("url", ""))
        print(f"PR already exists for exact task head: {url}")
        return _pr_ref(lookup.exact_open)
    if lookup.exact_merged is not None:
        url = str(lookup.exact_merged.get("url", ""))
        print(f"PR already merged on GitHub for exact task head: {url}")
        return _pr_ref(lookup.exact_merged, already_merged=True)

    if not title:
        title = run_git(["log", "-1", "--pretty=%s"], cwd=root).stdout.strip() or current
    if body is None:
        body = "Published by dev-platform after local validation and a fresh origin/main check."
    created = subprocess.run(
        ["gh", "pr", "create", "--base", main_branch, "--head", current, "--title", title, "--body", body],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if created.returncode == 0:
        # The create command's URL is not yet proof that it names the current
        # head. Re-enumerate the full tuple and retain only the stable exact PR.
        created_lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
        if created_lookup.available and created_lookup.exact_open is not None:
            pr = _pr_ref(created_lookup.exact_open)
            print(pr.url)
            return pr
        raise SystemExit("PR creation returned success, but GitHub did not expose one stable exact-head PR; refusing to continue.")

    # A concurrent publisher may have created the exact PR between our lookup
    # and this create attempt. Re-observe and reuse it instead of treating the
    # race as a reason to create competing delivery work.
    retry = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if retry.available and retry.exact_open is not None:
        url = str(retry.exact_open.get("url", ""))
        print(f"PR creation lost a race with a concurrent publisher; reusing exact PR: {url}")
        return _pr_ref(retry.exact_open)
    detail = created.stderr.strip() or created.stdout.strip() or f"exit {created.returncode}"
    raise SystemExit(f"gh pr create failed: {detail}")


def wait_for_pr_checks(root: Path, env: dict[str, str], pr: PrRef, expected_head: str) -> None:
    print("Waiting for GitHub required PR checks from structured PR state...")
    registration_deadline = time.monotonic() + CHECK_REGISTRATION_TIMEOUT_SECONDS
    completion_deadline: float | None = None
    while True:
        state = required_check_state_for_ref(root, env, pr.ref, expected_head)
        if state.kind == "passed":
            return
        if state.kind == "not_registered":
            if time.monotonic() >= registration_deadline:
                raise SystemExit(
                    "Required PR checks did not register within the bounded wait; remote state remains pending and resumable. "
                    "The PR and feature branch remain intact; local main was not changed."
                )
            print("Required PR checks are not registered yet; waiting for GitHub to attach them to the current PR head...")
            time.sleep(CHECK_REGISTRATION_INTERVAL_SECONDS)
            continue
        if state.kind == "pending":
            if completion_deadline is None:
                completion_deadline = time.monotonic() + CHECK_COMPLETION_TIMEOUT_SECONDS
            if time.monotonic() >= completion_deadline:
                raise SystemExit(
                    "Required PR checks did not complete within the bounded wait; remote state remains pending and resumable. "
                    "The PR and feature branch remain intact; local main was not changed."
                )
            print("Required PR checks are pending for the current PR head; waiting for terminal state...")
            time.sleep(CHECK_COMPLETION_INTERVAL_SECONDS)
            continue
        if state.kind == "failed":
            raise SystemExit(
                "Required PR checks failed for the current PR head; PR remains open and local main was not changed. "
                + state.detail
            )
        raise SystemExit(
            "GitHub required-check state is unknown; failing closed with a resumable remote-pending result. "
            "The PR and feature branch remain intact; local main was not changed. "
            + state.detail
        )


def exact_merged_state(root: Path, env: dict[str, str], pr: PrRef, expected_head: str) -> bool:
    """Return true only for the previously selected PR at the validated head."""
    result = subprocess.run(
        ["gh", "pr", "view", pr.ref, "--json", "state,headRefOid"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(payload, dict)
        and str(payload.get("state", "")).upper() == "MERGED"
        and str(payload.get("headRefOid", "")).strip() == expected_head
    )


def wait_for_pr_merged(root: Path, env: dict[str, str], pr: PrRef, expected_head: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        if exact_merged_state(root, env, pr, expected_head):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(MERGE_CONFIRM_INTERVAL_SECONDS)


def delete_remote_branch(root: Path, remote: str, current: str) -> None:
    exists = run_git(["ls-remote", "--exit-code", "--heads", remote, current], cwd=root, check=False)
    if exists.returncode != 0:
        print(f"Remote feature branch {remote}/{current} is already absent.")
        return
    deleted = run_git(["push", remote, "--delete", current], cwd=root, check=False)
    if deleted.returncode != 0:
        detail = deleted.stderr.strip() or deleted.stdout.strip() or f"exit {deleted.returncode}"
        print(f"WARNING: PR is merged, but remote branch cleanup failed for {remote}/{current}: {detail}")
        return
    print(f"Deleted remote feature branch {remote}/{current} after confirmed merge.")


def request_protected_merge(
    root: Path,
    env: dict[str, str],
    current: str,
    pr: PrRef,
    remote: str,
    expected_head: str,
    *,
    merge_guard: Callable[[], ContextManager[None]] | None = None,
) -> str:
    """Try ordinary/auto/queue merge for the exact validated head.

    Every attempt is guarded with `--match-head-commit` so GitHub itself
    refuses to merge a head other than `expected_head`. If an attempt is
    rejected, the PR's current head is re-observed directly (not inferred from
    error text): a changed head fails closed immediately; an unchanged head
    means the rejection was for another reason (checks pending, auto-merge
    disabled, ...), so the next protected mode is tried.

    Returns "merged" once GitHub confirms MERGED, or "unavailable" once every
    protected mode was rejected without the head ever changing -- meaning
    native durable arming could not be persisted at all and the caller should
    fall back to the bounded foreground check wait. A resumable pending state
    (accepted but not yet MERGED within the bounded wait) and a fail-closed
    changed-head both exit the process directly, matching this codebase's
    existing terminal/resumable SystemExit convention.
    """
    attempts = [
        ("ordinary squash merge", ["gh", "pr", "merge", pr.ref, "--squash", "--match-head-commit", expected_head]),
        ("GitHub auto-merge with squash", ["gh", "pr", "merge", pr.ref, "--auto", "--squash", "--match-head-commit", expected_head]),
        ("GitHub auto/queue enrollment", ["gh", "pr", "merge", pr.ref, "--auto", "--match-head-commit", expected_head]),
    ]
    last_detail = "merge command was not attempted"

    for label, command in attempts:
        with merge_guard() if merge_guard is not None else nullcontext():
            result = subprocess.run(
                command,
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        if result.stdout.strip():
            print(result.stdout.strip())
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"

        if result.returncode == 0:
            print(f"GitHub accepted {label} for exact validated head {expected_head}.")
            if wait_for_pr_merged(root, env, pr, expected_head, timeout_seconds=MERGE_CONFIRM_TIMEOUT_SECONDS):
                delete_remote_branch(root, remote, current)
                print(f"Merged PR for {current} through GitHub ({label}).")
                return "merged"
            raise SystemExit(
                f"{label} was accepted by GitHub for exact head {expected_head}, but the PR did not reach MERGED "
                "within this bounded local wait. GitHub retains that accepted merge request independently of this "
                "process; rerun finish or finish --status later to reconcile once it completes. Local main was not changed."
            )

        # A stable PR reference avoids branch ambiguity. Any readable state
        # other than the validated head is a hard stop.  This direct first
        # read avoids spending the bounded recovery wait on a PR we already
        # know cannot authorize the validated task head.
        observed = subprocess.run(
            ["gh", "pr", "view", pr.ref, "--json", "headRefOid"],
            cwd=root, env=env, text=True, capture_output=True, check=False,
        )
        try:
            actual_head = str(json.loads(observed.stdout).get("headRefOid", "")).strip() if observed.returncode == 0 else None
        except json.JSONDecodeError:
            actual_head = None
        if actual_head is not None and actual_head != expected_head:
            raise SystemExit(
                f"PR head changed from validated {expected_head} to {actual_head} before a merge request was "
                "accepted; refusing to merge a different head under this validation. Revalidate the new head and "
                "finish again. Local main was not changed."
            )

        # gh can report a convenience/cleanup error after GitHub already
        # accepted the merge. Only exact MERGED confirmation permits cleanup.
        if wait_for_pr_merged(root, env, pr, expected_head, timeout_seconds=MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS):
            print(f"WARNING: {label} exited non-zero, but GitHub confirms the PR is MERGED; continuing reconciliation: {detail}")
            delete_remote_branch(root, remote, current)
            print(f"Merged PR for {current} through GitHub ({label}).")
            return "merged"

        last_detail = detail
        print(f"{label} was not accepted for the unchanged validated head ({detail}); trying the next protected GitHub merge mode...")

    print(f"Native GitHub auto-merge/merge-queue could not be armed for the exact validated head ({last_detail}); it remains resumable.")
    return "unavailable"


def publish_pr(
    root: Path,
    remote: str,
    main_branch: str,
    title: str | None,
    body: str | None,
    merge_mode: str,
    *,
    config: dict | None = None,
) -> int:
    try:
        require_delivery_provenance(root)
    except ManagedTaskError as exc:
        raise SystemExit("Managed task publication blocked: " + str(exc)) from exc
    current = _validate_feature_branch(root, remote, main_branch)
    env = require_gh_environment(root)
    expected_head = run_git(["rev-parse", current], cwd=root).stdout.strip()

    # An already-open (or already-merged) exact-head PR is a resumable remote
    # object: recovery does not require re-applying the first-publication
    # freshness precondition, even if the base has advanced since that PR was
    # opened -- GitHub protection/queue/auto-merge remains authoritative for
    # whether it can still integrate. The push itself still happens whenever
    # the PR isn't already merged: it is a harmless idempotent no-op when the
    # exact head is already on GitHub, and it is the actual first-publication
    # push otherwise.
    lookup = find_exact_head_pr(root, env, current, main_branch, expected_head)
    if not lookup.available:
        raise SystemExit("GitHub PR state is unavailable; publication remains resumable without local-main mutation.")
    if lookup.exact_merged is None:
        push_feature_branch(root, remote, main_branch, require_fresh_base=lookup.exact_open is None)

    pr = ensure_pr(root, env, current, main_branch, title, body, expected_head, lookup=lookup)
    if pr.already_merged:
        if not exact_merged_state(root, env, pr, expected_head):
            raise SystemExit("Previously discovered merged PR no longer proves MERGED at the exact validated head; refusing cleanup.")
        delete_remote_branch(root, remote, current)
        print(f"PR for {current} was already merged on GitHub for the exact validated head; nothing further to merge.")
        return 0
    try:
        project = reconcile_managed_project(root, "In review")
    except ManagedProjectStatusError as exc:
        raise SystemExit(
            "Reviewable PR exists, but managed Project reconciliation is pending: " + str(exc)
        ) from exc
    if project is not None:
        print(
            f"Managed Project status {'updated' if project.changed else 'already current'}: "
            f"{project.source_issue} -> In review"
        )
    if merge_mode == "manual":
        print("PR published for manual review; pr_merge_mode=manual, so no merge was attempted.")
        return 0
    if merge_mode != "auto":
        raise SystemExit(f"Unknown pr_merge_mode: {merge_mode!r}; expected 'auto' or 'manual'.")

    config = config or read_platform_config(root)
    integration = main_root()

    def merge_guard() -> ContextManager[None]:
        return guard_before_protected_merge(
            integration, config, remote, main_branch, PRE_MERGE_GUARD_TIMEOUT_SECONDS
        )

    # Prefer to persist merge intent in native GitHub auto-merge/merge-queue
    # state before any long local wait, so an accepted remote request survives
    # loss of this process.
    outcome = request_protected_merge(root, env, current, pr, remote, expected_head, merge_guard=merge_guard)
    if outcome == "merged":
        return 0

    print(
        "WARNING: falling back to the bounded foreground required-check wait; remote durability is degraded "
        "until this process (or a resumed one) completes it."
    )
    wait_for_pr_checks(root, env, pr, expected_head)
    fallback_outcome = request_protected_merge(root, env, current, pr, remote, expected_head, merge_guard=merge_guard)
    if fallback_outcome == "merged":
        return 0
    raise SystemExit(
        "GitHub did not accept a protected merge for the exact validated head after required checks passed; "
        "PR remains open and local main was not reconciled."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish completed work to GitHub using the project's configured safety mode.")
    parser.add_argument("--mode", choices=["direct", "pr"])
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--title")
    parser.add_argument("--body")
    args = parser.parse_args()
    root = current_worktree_root()
    config = read_platform_config(root)
    mode = args.mode or publish_mode(config)
    main_branch = str(config.get("main_branch", "main"))
    if mode == "direct":
        if protected_main(config):
            raise SystemExit("protected_main=true is incompatible with direct publication. Use PR publication so required checks can gate the merge.")
        return publish_direct(root, args.remote, main_branch)
    return publish_pr(root, args.remote, main_branch, args.title, args.body, pr_merge_mode(config), config=config)


if __name__ == "__main__":
    raise SystemExit(main())
