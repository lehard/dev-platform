from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, main_root, read_platform_config, run_git


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


def current_branch(root: Path) -> str:
    return run_git(["branch", "--show-current"], cwd=root).stdout.strip()


def find_board_id(main: Path, worktree: Path) -> str | None:
    config = read_platform_config(worktree)
    rel = config.get("paths", {}).get("agent_board", ".claude/agents-board.json")
    path = main / rel
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for item in data.get("items", []):
        if Path(item.get("worktree", "")).resolve() == worktree.resolve():
            return item.get("id")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely fast-forward a completed task worktree into main.")
    parser.add_argument("--no-checks", action="store_true")
    parser.add_argument("--cleanup", action="store_true", help="Remove the worktree and local task branch after merge.")
    args = parser.parse_args()
    worktree = current_worktree_root()
    main = main_root()
    if worktree == main:
        raise SystemExit("Run merge_to_main.py from the task worktree, not the main integration copy.")
    config = read_platform_config(worktree)
    main_branch = config.get("main_branch", "main")
    branch = current_branch(worktree)
    if not branch:
        raise SystemExit("Detached HEAD is not mergeable through this helper.")
    if not clean(worktree):
        raise SystemExit("Task worktree is dirty. Commit or remove changes first.")
    if not clean(main):
        raise SystemExit("Main integration copy is dirty. Resolve it before merging.")
    checked_out = current_branch(main)
    if checked_out != main_branch:
        raise SystemExit(f"Main copy must have {main_branch!r} checked out; found {checked_out!r}.")
    if not args.no_checks:
        result = subprocess.run(["python3", str(worktree / "scripts" / "select_checks.py"), "--base", main_branch, "--execute"], cwd=worktree)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    ff = run_git(["merge-base", "--is-ancestor", main_branch, branch], cwd=worktree, check=False)
    if ff.returncode != 0:
        raise SystemExit(f"{branch} is not based on current {main_branch}. Rebase/update explicitly, resolve conflicts, rerun checks, then merge.")
    run_git(["merge", "--ff-only", branch], cwd=main)
    print(f"Merged {branch} -> {main_branch}")
    board_id = find_board_id(main, worktree)
    if board_id:
        subprocess.run(["python3", str(main / "scripts" / "agent_board.py"), "finish", "--id", board_id, "--quiet"], cwd=main, check=False)
    if args.cleanup:
        run_git(["worktree", "remove", str(worktree)], cwd=main)
        run_git(["branch", "-d", branch], cwd=main)
        print(f"Removed worktree and branch {branch}")
    else:
        print("Worktree retained. Use --cleanup next time or remove it manually when safe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
