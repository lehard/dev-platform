from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from _platform_common import (
    current_worktree_root,
    fetch_main,
    github_cli_env,
    harness_mode,
    main_root,
    pr_merge_mode,
    profile,
    protected_main,
    publish_mode,
    read_platform_config,
    relation,
    run_git,
)


ALLOW_NO_CHECKS_ENV = "DEV_PLATFORM_ALLOW_NO_CHECKS"
DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def integration_clean(root: Path, config: dict) -> bool:
    """Ignore the platform's own untracked lock file, but no other mutation."""
    lock = str(config.get("paths", {}).get("main_merge_lock", ".claude/main-merge.lock")).replace("\\", "/")
    status = run_git(["status", "--porcelain", "--untracked-files=all"], cwd=root).stdout.splitlines()
    return all(not line or line[3:].replace("\\", "/") == lock for line in status)


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def find_board_id(main: Path, worktree: Path, config: dict) -> str | None:
    rel = config.get("paths", {}).get("agent_board", ".claude/agents-board.json")
    path = main / rel
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for item in data.get("items", []):
        try:
            if Path(item.get("worktree", "")).resolve() == worktree.resolve():
                return item.get("id")
        except OSError:
            continue
    return None


def finish_board(main: Path, worktree: Path, config: dict) -> None:
    board_id = find_board_id(main, worktree, config)
    if board_id:
        subprocess.run(["python3", str(main / "scripts" / "agent_board.py"), "finish", "--id", board_id, "--quiet"], cwd=main, check=False)


def run_checks(root: Path, base: str, no_checks: bool) -> None:
    if no_checks:
        return
    result = subprocess.run(["python3", str(root / "scripts" / "select_checks.py"), "--base", base, "--execute"], cwd=root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_openspec_hygiene(root: Path) -> None:
    script = root / "scripts" / "openspec_lifecycle.py"
    result = subprocess.run(["python3", str(script), "check"], cwd=root)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def validate_publication_config(root: Path, config: dict, prof: str, mode: str) -> None:
    merge_mode = pr_merge_mode(config)
    if merge_mode not in {"auto", "manual"}:
        raise SystemExit(f"Invalid pr_merge_mode={merge_mode!r}; expected 'auto' or 'manual'.")
    if protected_main(config) and mode == "direct":
        raise SystemExit("protected_main=true is incompatible with publish_mode=direct. Use publish_mode=pr so GitHub required checks can gate the merge.")
    if mode == "pr" and prof == "light":
        raise SystemExit("publish_mode=pr requires a feature-capable profile. Use standard/multi-agent or a reviewed project-owned harness.")
    if mode == "pr" and github_cli_env(root) is None:
        raise SystemExit(
            "publish_mode=pr requires authenticated GitHub CLI/API access. Provide a valid GH_TOKEN/GITHUB_TOKEN, a persistent gh login, or reusable GitHub HTTPS credentials before finishing the task."
        )


def task_pr_is_already_merged(root: Path, branch: str) -> bool:
    """Return true only when GitHub merged the PR for this exact local branch head."""
    env = github_cli_env(root)
    if env is None:
        return False
    result = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "state,headRefOid"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    remote_head = str(payload.get("headRefOid", "")).strip()
    state = str(payload.get("state", "")).strip().upper()
    local_head = run_git(["rev-parse", branch], cwd=root, check=False)
    if local_head.returncode != 0:
        return False
    return state == "MERGED" and remote_head == local_head.stdout.strip()


@contextmanager
def serialized_integration(root: Path, config: dict, timeout_seconds: float) -> Iterator[None]:
    relative = config.get("paths", {}).get("main_merge_lock", ".claude/main-merge.lock")
    path = (root / relative).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is None:
            yield
            return
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SystemExit("Another agent is still integrating into the main branch. Retry after it finishes.") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def integrate_and_publish_direct(work: Path, integration: Path, config: dict, branch: str, main_branch: str) -> None:
    fetch_main(integration, "origin", main_branch)
    remote_main = f"origin/{main_branch}"
    if branch != main_branch:
        if not clean(integration):
            raise SystemExit("Integration copy is dirty. Resolve it before direct integration.")
        if work == integration:
            run_git(["switch", main_branch], cwd=integration)
        elif current_branch(integration) != main_branch:
            raise SystemExit(f"Integration copy must have {main_branch!r} checked out.")
        if run_git(["merge-base", "--is-ancestor", remote_main, main_branch], cwd=integration, check=False).returncode != 0:
            raise SystemExit(f"Local {main_branch} is not safely based on current {remote_main}.")
        if run_git(["merge-base", "--is-ancestor", main_branch, branch], cwd=integration, check=False).returncode != 0:
            raise SystemExit(f"{branch} is stale relative to current local {main_branch}. Rebase/update explicitly and rerun checks.")
        run_git(["merge", "--ff-only", branch], cwd=integration)
        print(f"Integrated {branch} -> {main_branch} locally.")
    env = os.environ.copy()
    env[DIRECT_PUBLISH_GUARD] = "1"
    subprocess.run(["python3", str(integration / "scripts" / "project_publish.py"), "--mode", "direct"], cwd=integration, check=True, env=env)


def sync_after_remote_pr_merge(work: Path, integration: Path, config: dict, main_branch: str) -> None:
    # This function is called only while serialized_integration is held. Fetch
    # after lock acquisition: a previous reconciler may have advanced main while
    # this task was waiting for the shared checkout.
    fetch_main(integration, "origin", main_branch)
    if not integration_clean(integration, config):
        raise SystemExit("Remote PR merged, but the integration copy is dirty. Leave it untouched and synchronize main manually after resolving local state.")
    remote_main = f"origin/{main_branch}"
    if work == integration:
        run_git(["switch", main_branch], cwd=integration)
    elif current_branch(integration) != main_branch:
        raise SystemExit(f"Remote PR merged, but integration copy must have {main_branch!r} checked out before synchronization.")
    state = relation(integration, main_branch, remote_main)
    if state == "behind":
        run_git(["merge", "--ff-only", remote_main], cwd=integration)
        print(f"Fast-forwarded local {main_branch} to merged {remote_main}.")
    elif state == "equal":
        print(f"Local {main_branch} already equals merged {remote_main}.")
    else:
        raise SystemExit(f"Remote PR merged, but local {main_branch} vs {remote_main} is {state}. Refusing automatic reconciliation.")


def cleanup_completed_task(work: Path, integration: Path, branch: str, *, squash_merged: bool) -> None:
    if work == integration:
        return

    # The running process must leave the task worktree before asking Git to
    # remove it. All post-merge housekeeping is driven from the integration
    # checkout where main is already synchronized.
    os.chdir(integration)
    removed = run_git(["worktree", "remove", str(work)], cwd=integration, check=False)
    if removed.returncode != 0:
        detail = removed.stderr.strip() or removed.stdout.strip() or f"exit {removed.returncode}"
        print(f"WARNING: task is integrated, but local worktree cleanup failed for {work}: {detail}")
        return

    # A squash-merged branch is not an ancestor of main even though its PR is
    # merged. At this point remote merge has been confirmed and main synced, so
    # explicit local branch deletion is safe for the exact completed task.
    delete_flag = "-D" if squash_merged else "-d"
    deleted = run_git(["branch", delete_flag, branch], cwd=integration, check=False)
    if deleted.returncode != 0:
        detail = deleted.stderr.strip() or deleted.stdout.strip() or f"exit {deleted.returncode}"
        print(f"WARNING: task is integrated, but local branch cleanup failed for {branch}: {detail}")
        return
    print(f"Removed completed worktree and local branch {branch}.")


def reconcile_confirmed_remote_pr_merge(
    work: Path,
    integration: Path,
    config: dict,
    branch: str,
    main_branch: str,
    prof: str,
    *,
    cleanup: bool,
    timeout_seconds: float,
) -> None:
    """Serialize only local post-MERGED reconciliation, never remote waits."""
    with serialized_integration(integration, config, timeout_seconds):
        sync_after_remote_pr_merge(work, integration, config, main_branch)
        if prof == "multi-agent":
            finish_board(integration, work, config)
        if cleanup:
            cleanup_completed_task(work, integration, branch, squash_merged=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate, integrate when needed, and publish a completed task without a human git hand-off.")
    parser.add_argument("--no-checks", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--title")
    parser.add_argument("--body")
    parser.add_argument("--merge-timeout", type=float, default=60.0)
    args = parser.parse_args()
    if args.merge_timeout < 0:
        parser.error("--merge-timeout must be non-negative")
    if args.no_checks and os.environ.get(ALLOW_NO_CHECKS_ENV) != "1":
        raise SystemExit(
            "--no-checks is an emergency/operator override and is blocked by default. "
            f"Set {ALLOW_NO_CHECKS_ENV}=1 only after an explicit decision to bypass validation."
        )
    work = current_worktree_root()
    integration = main_root()
    config = read_platform_config(work)
    if harness_mode(config) != "platform":
        raise SystemExit("harness_mode=project: use the repository-owned Git/worktree publication workflow instead of scripts/finish_task.py.")
    prof = profile(config)
    mode = publish_mode(config)
    main_branch = str(config.get("main_branch", "main"))
    branch = current_branch(work)
    if not branch:
        raise SystemExit("Detached HEAD is not publishable through the platform lifecycle.")
    validate_publication_config(work, config, prof, mode)
    run_openspec_hygiene(work)
    if not clean(work):
        raise SystemExit("Current worktree is dirty. Commit or remove changes first.")
    fetch_main(integration, "origin", main_branch)
    remote_main = f"origin/{main_branch}"

    # Recovery is intentionally checked before local validation against the new
    # remote base. A squash-merged task branch is no longer an ancestor of main,
    # but if GitHub already merged this exact head there is nothing to rebase or
    # republish; only local reconciliation remains.
    if mode == "pr" and branch != main_branch and pr_merge_mode(config) == "auto" and task_pr_is_already_merged(work, branch):
        reconcile_confirmed_remote_pr_merge(
            work, integration, config, branch, main_branch, prof, cleanup=args.cleanup, timeout_seconds=args.merge_timeout
        )
        print("Task PR was already merged through GitHub; local main and task state were reconciled without republishing.")
        return 0

    run_checks(work, remote_main, args.no_checks)
    if mode == "pr":
        if branch == main_branch:
            raise SystemExit("publish_mode=pr requires a feature branch. Use standard/multi-agent profile or switch publish_mode deliberately.")
        if run_git(["merge-base", "--is-ancestor", remote_main, branch], cwd=work, check=False).returncode != 0:
            raise SystemExit(f"{branch} is stale relative to {remote_main}. Rebase/update explicitly, rerun checks, then finish.")
        command = ["python3", str(work / "scripts" / "project_publish.py"), "--mode", "pr"]
        if args.title:
            command += ["--title", args.title]
        if args.body:
            command += ["--body", args.body]
        subprocess.run(command, cwd=work, check=True)
        if pr_merge_mode(config) == "auto":
            reconcile_confirmed_remote_pr_merge(
                work, integration, config, branch, main_branch, prof, cleanup=args.cleanup, timeout_seconds=args.merge_timeout
            )
            print("Task PR passed required checks, merged through GitHub, and local main was synchronized.")
        else:
            if prof == "standard" and work == integration:
                run_git(["switch", main_branch], cwd=integration)
                print(f"Returned integration copy to {main_branch} after manual-review PR publication.")
            if prof == "multi-agent":
                finish_board(integration, work, config)
            print("Task published as PR for manual review. OpenSpec lifecycle hygiene passed.")
        return 0
    if mode != "direct":
        raise SystemExit(f"Unknown publish_mode: {mode}")
    with serialized_integration(integration, config, args.merge_timeout):
        integrate_and_publish_direct(work, integration, config, branch, main_branch)
        if prof == "multi-agent" and work != integration:
            finish_board(integration, work, config)
    if args.cleanup:
        cleanup_completed_task(work, integration, branch, squash_merged=False)
    print("Task published directly. OpenSpec lifecycle hygiene passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
