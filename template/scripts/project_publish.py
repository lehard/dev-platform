from __future__ import annotations

import argparse
import os
import subprocess
import time
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
MERGE_CONFIRM_TIMEOUT_SECONDS = 600.0
MERGE_CONFIRM_INTERVAL_SECONDS = 2.0
MERGE_FAILURE_CONFIRM_TIMEOUT_SECONDS = 3.0
NO_CHECK_MARKERS = (
    "no checks reported",
    "no checks were reported",
    "no required checks",
    "no checks found",
)


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


def _checks_not_registered(detail: str) -> bool:
    lowered = detail.lower()
    return any(marker in lowered for marker in NO_CHECK_MARKERS)


def wait_for_pr_checks(root: Path, env: dict[str, str], current: str) -> None:
    print("Waiting for GitHub required PR checks...")
    deadline = time.monotonic() + CHECK_REGISTRATION_TIMEOUT_SECONDS
    while True:
        result = subprocess.run(
            ["gh", "pr", "checks", current, "--required", "--watch", "--fail-fast", "--interval", "5"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.returncode == 0:
            return
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        if _checks_not_registered(detail) and time.monotonic() < deadline:
            print("Required PR checks are not registered yet; waiting for GitHub to attach them to the PR...")
            time.sleep(CHECK_REGISTRATION_INTERVAL_SECONDS)
            continue
        if _checks_not_registered(detail):
            raise SystemExit(
                "Required PR checks did not register within the bounded wait; PR remains open and local main was not changed. "
                + detail
            )
        raise SystemExit("Required PR checks did not pass; PR remains open and local main was not changed. " + detail)


def pr_state(root: Path, env: dict[str, str], current: str) -> str | None:
    result = subprocess.run(
        ["gh", "pr", "view", current, "--json", "state", "--jq", ".state"],
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
                "local main was not reconciled."
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
