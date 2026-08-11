from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from _platform_common import main_root, machine_path, profile, read_platform_config, run_git


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise argparse.ArgumentTypeError("slug must contain letters or numbers")
    return cleaned


@dataclass(frozen=True)
class StartedWorktree:
    worktree: Path
    branch: str
    board_id: str


def create_worktree(root: Path, slug_value: str, task: str, scope: str = "", *, base: str | None = None, sync: bool = True) -> StartedWorktree:
    root = root.resolve()
    config = read_platform_config(root)
    if profile(config) != "multi-agent":
        raise RuntimeError("start_worktree.py is only valid for workflow_profile=multi-agent. Use start_task.py.")
    main_branch = base or str(config.get("main_branch", "main"))
    branch = f"agent/{slug_value}"
    worktrees_root = machine_path("worktrees", root)
    worktree = worktrees_root / slug_value
    worktrees_root.mkdir(parents=True, exist_ok=True)
    if sync:
        subprocess.run(["python3", str(root / "scripts" / "project_sync.py")], cwd=root, check=True)
    if worktree.exists():
        raise RuntimeError(f"Worktree path already exists: {worktree}")
    if run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False).returncode == 0:
        raise RuntimeError(f"Branch already exists: {branch}")
    subprocess.run(["python3", str(root / "scripts" / "agent_board.py"), "doctor"], cwd=root, check=False)
    run_git(["worktree", "add", "-b", branch, str(worktree), main_branch], cwd=root)
    try:
        result = subprocess.run(
            ["python3", str(root / "scripts" / "agent_board.py"), "start", "--task", task, "--scope", scope, "--branch", branch, "--worktree", str(worktree)],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        run_git(["worktree", "remove", "--force", str(worktree)], cwd=root, check=False)
        run_git(["branch", "-D", branch], cwd=root, check=False)
        raise
    return StartedWorktree(worktree=worktree, branch=branch, board_id=result.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and register an isolated multi-agent worktree.")
    parser.add_argument("slug", type=slug)
    parser.add_argument("--task", required=True)
    parser.add_argument("--scope", default="")
    parser.add_argument("--base")
    parser.add_argument("--skip-sync", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        started = create_worktree(main_root(), args.slug, args.task, args.scope, base=args.base, sync=not args.skip_sync)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Created: {started.worktree}")
    print(f"Branch:  {started.branch}")
    print(f"Board:   {started.board_id}")
    print(f"Next:    cd {started.worktree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
