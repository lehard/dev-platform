from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    locked_json,
    machine_path,
    main_root,
    run_git,
    utc_now,
)


def board_path() -> Path:
    return machine_path("agent_board", main_root())


def _branch_exists(branch: str, root: Path) -> bool:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
    return result.returncode == 0


def _status(item: dict, root: Path) -> list[str]:
    problems: list[str] = []
    worktree = Path(item.get("worktree", ""))
    if not worktree.exists():
        problems.append("worktree-missing")
    branch = item.get("branch", "")
    if branch and not _branch_exists(branch, root):
        problems.append("branch-missing")
    return problems


def cmd_list(_: argparse.Namespace) -> int:
    path = board_path()
    if not path.exists():
        print("No active agent board.")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not items:
        print("No active agent work.")
        return 0
    for item in items:
        print(f"{item['id']}  {item['branch']}  {item['task']}")
        print(f"  worktree: {item['worktree']}")
        print(f"  scope: {item.get('scope') or '-'}")
        print(f"  heartbeat: {item.get('heartbeat')}")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    root = main_root()
    worktree = Path(args.worktree).resolve()
    branch = args.branch
    path = board_path()

    with locked_json(path) as data:
        items = data.setdefault("items", [])
        for item in items:
            if Path(item.get("worktree", "")).resolve() == worktree:
                raise SystemExit(f"Worktree already registered: {worktree}")
            if item.get("branch") == branch:
                raise SystemExit(f"Branch already registered: {branch}")
        item_id = args.id or uuid.uuid4().hex[:10]
        items.append(
            {
                "id": item_id,
                "task": args.task,
                "scope": args.scope or "",
                "branch": branch,
                "worktree": str(worktree),
                "pid": os.getpid(),
                "started_at": utc_now(),
                "heartbeat": utc_now(),
            }
        )
    print(item_id)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    path = board_path()
    with locked_json(path) as data:
        item = next((x for x in data.setdefault("items", []) if x.get("id") == args.id), None)
        if item is None:
            raise SystemExit(f"Unknown board id: {args.id}")
        if args.task is not None:
            item["task"] = args.task
        if args.scope is not None:
            item["scope"] = args.scope
        item["heartbeat"] = utc_now()
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    path = board_path()
    if not path.exists():
        return 0
    with locked_json(path) as data:
        items = data.setdefault("items", [])
        before = len(items)
        items[:] = [item for item in items if item.get("id") != args.id]
        if len(items) == before and not args.quiet:
            print(f"Board id not found: {args.id}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = main_root()
    path = board_path()
    if not path.exists():
        print("agent-board: ok (empty)")
        return 0

    with locked_json(path) as data:
        items = data.setdefault("items", [])
        bad: list[tuple[dict, list[str]]] = []
        for item in items:
            problems = _status(item, root)
            if problems:
                bad.append((item, problems))

        if args.fix and bad:
            removable = {item["id"] for item, problems in bad if "worktree-missing" in problems}
            items[:] = [item for item in items if item.get("id") not in removable]
            if removable:
                print("Removed stale entries:", ", ".join(sorted(removable)))

    if not bad:
        print("agent-board: ok")
        return 0
    for item, problems in bad:
        print(f"{item.get('id')}: {', '.join(problems)}")
    return 1 if not args.fix else 0


def find_id_for_current_worktree() -> str | None:
    path = board_path()
    if not path.exists():
        return None
    worktree = current_worktree_root()
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        if Path(item.get("worktree", "")).resolve() == worktree:
            return item.get("id")
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Machine-local registry of active agent worktrees.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("doctor")
    p.add_argument("--fix", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("start")
    p.add_argument("--task", required=True)
    p.add_argument("--scope", default="")
    p.add_argument("--branch", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("update")
    p.add_argument("--id", required=True)
    p.add_argument("--task")
    p.add_argument("--scope")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("finish")
    p.add_argument("--id", required=True)
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_finish)

    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))
