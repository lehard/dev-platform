from __future__ import annotations

import argparse
from pathlib import Path

from _platform_common import current_worktree_root, fetch_main, main_root, preflight, read_platform_config, relation, require_origin, run_git


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely synchronize the local integration branch with origin before starting work.")
    parser.add_argument("--remote", default="origin")
    args = parser.parse_args()
    caller = current_worktree_root()
    integration = main_root()
    preflight(integration)
    config = read_platform_config(caller)
    branch = str(config.get("main_branch", "main"))
    remote_branch = f"{args.remote}/{branch}"
    require_origin(integration, args.remote)
    if not clean(integration):
        raise SystemExit("Integration copy is dirty. Refusing to synchronize it.")
    checked_out = current_branch(integration)
    if checked_out != branch:
        raise SystemExit(f"Integration copy must have {branch!r} checked out; found {checked_out!r}.")
    fetch_main(integration, args.remote, branch)
    state = relation(integration, branch, remote_branch)
    if state == "equal":
        print(f"{branch} is already synchronized with {remote_branch}.")
        return 0
    if state == "behind":
        run_git(["merge", "--ff-only", remote_branch], cwd=integration)
        print(f"Fast-forwarded {branch} to {remote_branch}.")
        return 0
    if state == "ahead":
        raise SystemExit(f"Local {branch} is ahead of {remote_branch}. Publish or reconcile it before starting new work.")
    raise SystemExit(f"Local {branch} and {remote_branch} have diverged. Resolve explicitly; automatic reconciliation is forbidden.")


if __name__ == "__main__":
    raise SystemExit(main())
