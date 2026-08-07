from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, fetch_main, main_root, publish_mode, read_platform_config, relation, require_origin, run_git


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def publish_direct(root: Path, remote: str, main_branch: str) -> int:
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


def publish_pr(root: Path, remote: str, main_branch: str, title: str | None, body: str | None) -> int:
    current = branch(root)
    if not current or current == main_branch:
        raise SystemExit("PR publication requires a feature branch, not the integration branch.")
    if not clean(root):
        raise SystemExit("Task worktree is dirty. Commit or remove changes before publishing.")
    require_origin(root, remote)
    fetch_main(root, remote, main_branch)
    if run_git(["merge-base", "--is-ancestor", f"{remote}/{main_branch}", current], cwd=root, check=False).returncode != 0:
        raise SystemExit(f"{current} does not contain current {remote}/{main_branch}. Rebase/update explicitly, rerun checks, then publish.")
    if not shutil.which("gh"):
        raise SystemExit("publish_mode=pr requires GitHub CLI (gh). Install/authenticate it, then rerun.")
    auth = subprocess.run(["gh", "auth", "status"], cwd=root, text=True, capture_output=True)
    if auth.returncode != 0:
        raise SystemExit("GitHub CLI is not authenticated. Run `gh auth login`, then rerun.")
    run_git(["push", "-u", remote, current], cwd=root)
    existing = subprocess.run(["gh", "pr", "view", current, "--json", "url", "--jq", ".url"], cwd=root, text=True, capture_output=True)
    if existing.returncode == 0 and existing.stdout.strip():
        print(f"PR already exists: {existing.stdout.strip()}")
        return 0
    if not title:
        title = run_git(["log", "-1", "--pretty=%s"], cwd=root).stdout.strip() or current
    if body is None:
        body = "Published by dev-platform after local validation and a fresh origin/main check."
    created = subprocess.run(["gh", "pr", "create", "--base", main_branch, "--head", current, "--title", title, "--body", body], cwd=root, text=True, capture_output=True, check=True)
    print(created.stdout.strip())
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
        return publish_direct(root, args.remote, main_branch)
    return publish_pr(root, args.remote, main_branch, args.title, args.body)


if __name__ == "__main__":
    raise SystemExit(main())
