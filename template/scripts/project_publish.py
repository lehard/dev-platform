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
MERGE_CONFIRM_ATTEMPTS = 10
MERGE_CONFIRM_INTERVAL_SECONDS = 0.5


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
        + " Install gh if needed, then run `gh auth login`, provide GH_TOKEN/GITHUB_TOKEN, or configure a reusable GitHub HTTPS credential for git."
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


def wait_for_pr_checks(root: Path, env: dict[str, str], current: str) -> None:
    print("Waiting for GitHub PR checks...")
    result = subprocess.run(
        ["gh", "pr", "checks", current, "--watch", "--fail-fast", "--interval", "5"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SystemExit("Required PR checks did not pass; PR remains open and local main was not changed. " + detail)


def wait_for_pr_merged(root: Path, env: dict[str, str], current: str) -> bool:
    for attempt in range(MERGE_CONFIRM_ATTEMPTS):
        result = subprocess.run(
            ["gh", "pr", "view", current, "--json", "state,mergedAt", "--jq", ".state"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip().upper() == "MERGED":
            return True
        if attempt + 1 < MERGE_CONFIRM_ATTEMPTS:
            time.sleep(MERGE_CONFIRM_INTERVAL_SECONDS)
    return False


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
    result = subprocess.run(
        ["gh", "pr", "merge", current, "--squash"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())

    # The GitHub-side PR state is authoritative. gh can return non-zero after a
    # successful server-side merge because of unrelated local convenience work.
    if not wait_for_pr_merged(root, env, current):
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise SystemExit(
            "GitHub PR merge could not be confirmed as MERGED after bounded retries; "
            "local main was not reconciled. " + detail
        )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        print(f"WARNING: gh pr merge exited non-zero, but GitHub confirms the PR is MERGED; continuing reconciliation: {detail}")

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
