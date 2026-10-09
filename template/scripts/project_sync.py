from __future__ import annotations

import argparse
from pathlib import Path

from delegation_containment import ContainmentError, record_integration_advance, require_own_fast_forward
from integration_state import serialized_integration
from _platform_common import current_worktree_root, fetch_main, main_root, preflight, read_platform_config, relation, require_origin, run_git


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely synchronize the local integration branch with origin before starting work.")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--lock-timeout", type=float, default=60.0, help="seconds to wait for the shared integration lock")
    args = parser.parse_args()
    caller = current_worktree_root()
    integration = main_root()
    preflight(integration)
    config = read_platform_config(caller)
    branch = str(config.get("main_branch", "main"))
    remote_branch = f"{args.remote}/{branch}"
    require_origin(integration, args.remote)
    if args.lock_timeout < 0:
        parser.error("--lock-timeout must be non-negative")
    # Hold the integration lock so the head read, the merge and its receipt describe one advance
    # by this caller and cannot absorb another process's concurrent advance.
    with serialized_integration(integration, config, args.lock_timeout):
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
            before_head = run_git(["rev-parse", "HEAD"], cwd=integration).stdout.strip()
            run_git(["merge", "--ff-only", remote_branch], cwd=integration)
            after_head = run_git(["rev-parse", "HEAD"], cwd=integration).stdout.strip()
            try:
                require_own_fast_forward(integration, branch, before_head, after_head, remote_branch)
            except ContainmentError as exc:
                raise SystemExit(str(exc)) from exc
            record_integration_advance(
                integration,
                before_head,
                after_head,
                tool="project_sync",
                actor_worktree=caller,
                remote=args.remote,
            )
            print(f"Fast-forwarded {branch} to {remote_branch}.")
            return 0
        if state == "ahead":
            raise SystemExit(f"Local {branch} is ahead of {remote_branch}. Publish or reconcile it before starting new work.")
        raise SystemExit(f"Local {branch} and {remote_branch} have diverged. Resolve explicitly; automatic reconciliation is forbidden.")


if __name__ == "__main__":
    raise SystemExit(main())
