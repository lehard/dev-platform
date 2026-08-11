from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

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
)


DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"
CHECK_REGISTRATION_TIMEOUT_SECONDS = 90.0
CHECK_REGISTRATION_INTERVAL_SECONDS = 3.0
CHECK_COMPLETION_TIMEOUT_SECONDS = 600.0
CHECK_COMPLETION_INTERVAL_SECONDS = 5.0
MERGE_CONFIRM_TIMEOUT_SECONDS = 600.0
MERGE_CONFIRM_INTERVAL_SECONDS = 2.0
MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS = 3.0
PASSED_CHECK_STATES = {"SUCCESS", "NEUTRAL", "SKIPPING", "SKIPPED"}
FAILED_CHECK_STATES = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STALE", "ERROR"}
PENDING_CHECK_STATES = {"EXPECTED", "PENDING", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}


@dataclass(frozen=True)
class RequiredCheckState:
    """Normalized, structured GitHub state for required checks on one PR head."""

    kind: str
    detail: str = ""
    checks: tuple[dict[str, object], ...] = ()


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


def push_feature_branch(root: Path, remote: str, main_branch: str) -> str:
    current = branch(root)
    if not current or current == main_branch:
        raise SystemExit("PR publication requires a feature branch, not the integration branch.")
    if not clean(root):
        raise SystemExit("Task worktree is dirty. Commit or remove changes before publishing.")
    require_origin(root, remote)
    fetch_main(root, remote, main_branch)
    if run_git(["merge-base", "--is-ancestor", f"{remote}/{main_branch}", current], cwd=root, check=False).returncode != 0:
        raise SystemExit(f"{current} does not contain current {remote}/{main_branch}. Rebase/update explicitly, rerun checks, then publish.")
    run_git(["push", "-u", remote, current], cwd=root)
    print(f"Published feature branch {current} -> {remote}/{current}.")
    return current


def ensure_pr(root: Path, env: dict[str, str], current: str, main_branch: str, title: str | None, body: str | None) -> str:
    existing = subprocess.run(
        ["gh", "pr", "view", current, "--json", "url", "--jq", ".url"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        url = existing.stdout.strip()
        print(f"PR already exists: {url}")
        return url
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
        check=True,
    )
    url = created.stdout.strip()
    print(url)
    return url


def required_check_state(root: Path, env: dict[str, str], current: str) -> RequiredCheckState:
    """Read required-check state from gh JSON, never from rendered CLI wording.

    `gh pr checks --required --json` delegates required-context selection to
    GitHub, and the preceding PR query proves those contexts belong to this
    local task head.  An unreadable API response is intentionally `unknown`.
    """
    pr = subprocess.run(
        ["gh", "pr", "view", current, "--json", "state,headRefOid"],
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
    local_head = run_git(["rev-parse", current], cwd=root, check=False)
    if local_head.returncode != 0:
        return RequiredCheckState("unknown", f"local task branch {current!r} is unavailable")
    remote_head = str(pr_payload.get("headRefOid", "")).strip()
    if remote_head != local_head.stdout.strip():
        return RequiredCheckState("unknown", "GitHub PR head does not match the local task head")

    checks = subprocess.run(
        ["gh", "pr", "checks", current, "--required", "--json", "name,state,workflow,link"],
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


def wait_for_pr_checks(root: Path, env: dict[str, str], current: str) -> None:
    print("Waiting for GitHub required PR checks from structured PR state...")
    registration_deadline = time.monotonic() + CHECK_REGISTRATION_TIMEOUT_SECONDS
    completion_deadline: float | None = None
    while True:
        state = required_check_state(root, env, current)
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


def pr_state(root: Path, env: dict[str, str], current: str) -> str | None:
    result = subprocess.run(
        ["gh", "pr", "view", current, "--json", "state,mergedAt", "--jq", ".state"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip().upper()
    return value or None


def wait_for_pr_merged(root: Path, env: dict[str, str], current: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while True:
        if pr_state(root, env, current) == "MERGED":
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


def merge_pr(root: Path, env: dict[str, str], current: str, remote: str) -> None:
    attempts = [
        ("ordinary squash merge", ["gh", "pr", "merge", current, "--squash"]),
        ("GitHub auto-merge with squash", ["gh", "pr", "merge", current, "--auto", "--squash"]),
        ("GitHub auto/queue enrollment", ["gh", "pr", "merge", current, "--auto"]),
    ]
    last_detail = "merge command was not attempted"
    confirmed_after_nonzero = False

    for index, (label, command) in enumerate(attempts):
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
        last_detail = detail

        if result.returncode == 0:
            if wait_for_pr_merged(root, env, current, timeout_seconds=MERGE_CONFIRM_TIMEOUT_SECONDS):
                break
            raise SystemExit(
                f"{label} was accepted by GitHub, but the PR did not reach MERGED within the bounded wait; "
                "remote state remains pending and resumable; local main was not reconciled."
            )

        # gh can report a convenience/cleanup error after GitHub already accepted
        # the merge. Confirm remote state before interpreting a non-zero exit as a
        # failed merge request.
        if wait_for_pr_merged(root, env, current, timeout_seconds=MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS):
            confirmed_after_nonzero = True
            break

        if index + 1 < len(attempts):
            print(f"{label} was not accepted ({detail}); trying the next protected GitHub merge mode...")
    else:
        raise SystemExit(
            "GitHub rejected every supported protected PR merge mode; PR remains open and local main was not reconciled. "
            + last_detail
        )

    if confirmed_after_nonzero:
        print(f"WARNING: gh pr merge exited non-zero, but GitHub confirms the PR is MERGED; continuing reconciliation: {last_detail}")

    delete_remote_branch(root, remote, current)
    print(f"Merged PR for {current} through GitHub after successful checks.")


def publish_pr(root: Path, remote: str, main_branch: str, title: str | None, body: str | None, merge_mode: str) -> int:
    current = push_feature_branch(root, remote, main_branch)
    # Keep git publication independent from GitHub API credentials. Normal
    # finish_task preflight catches missing auth before this point, while direct
    # project_publish invocation still leaves validated work safely pushed.
    env = require_gh_environment(root, branch_pushed=True)
    ensure_pr(root, env, current, main_branch, title, body)
    if merge_mode == "manual":
        print("PR published for manual review; pr_merge_mode=manual, so no merge was attempted.")
        return 0
    if merge_mode != "auto":
        raise SystemExit(f"Unknown pr_merge_mode: {merge_mode!r}; expected 'auto' or 'manual'.")
    wait_for_pr_checks(root, env, current)
    merge_pr(root, env, current, remote)
    return 0


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
    return publish_pr(root, args.remote, main_branch, args.title, args.body, pr_merge_mode(config))


if __name__ == "__main__":
    raise SystemExit(main())
