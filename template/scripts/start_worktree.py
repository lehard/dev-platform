from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from _platform_common import main_root, machine_path, read_platform_config, run_git


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise argparse.ArgumentTypeError("slug must contain letters or numbers")
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and register an isolated agent worktree.")
    parser.add_argument("slug", type=slug)
    parser.add_argument("--task", required=True)
    parser.add_argument("--scope", default="")
    parser.add_argument("--base")
    args = parser.parse_args()

    root = main_root()
    config = read_platform_config()
    main_branch = args.base or config.get("main_branch", "main")
    branch = f"agent/{args.slug}"
    worktrees_root = machine_path("worktrees", root)
    worktree = worktrees_root / args.slug
    worktrees_root.mkdir(parents=True, exist_ok=True)

    if worktree.exists():
        raise SystemExit(f"Worktree path already exists: {worktree}")
    if run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False).returncode == 0:
        raise SystemExit(f"Branch already exists: {branch}")

    subprocess.run(
        ["python3", str(root / "scripts" / "agent_board.py"), "doctor"],
        cwd=root,
        check=False,
    )

    run_git(["worktree", "add", "-b", branch, str(worktree), main_branch], cwd=root)
    try:
        result = subprocess.run(
            [
                "python3",
                str(root / "scripts" / "agent_board.py"),
                "start",
                "--task",
                args.task,
                "--scope",
                args.scope,
                "--branch",
                branch,
                "--worktree",
                str(worktree),
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
    except Exception:
        run_git(["worktree", "remove", "--force", str(worktree)], cwd=root, check=False)
        run_git(["branch", "-D", branch], cwd=root, check=False)
        raise

    board_id = result.stdout.strip()
    print(f"Created: {worktree}")
    print(f"Branch:  {branch}")
    print(f"Board:   {board_id}")
    print(f"Next:    cd {worktree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
