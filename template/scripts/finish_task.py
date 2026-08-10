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

from _platform_common import current_worktree_root, fetch_main, harness_mode, main_root, profile, publish_mode, read_platform_config, run_git


ALLOW_NO_CHECKS_ENV = "DEV_PLATFORM_ALLOW_NO_CHECKS"
DIRECT_PUBLISH_GUARD = "DEV_PLATFORM_VALIDATED_DIRECT_PUBLISH"


def clean(root: Path) -> bool:
    return not run_git(["status", "--porcelain"], cwd=root).stdout.strip()


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
    run_openspec_hygiene(work)
    if not clean(work):
        raise SystemExit("Current worktree is dirty. Commit or remove changes first.")
    fetch_main(integration, "origin", main_branch)
    remote_main = f"origin/{main_branch}"
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
        if prof == "standard" and work == integration:
            run_git(["switch", main_branch], cwd=integration)
            print(f"Returned integration copy to {main_branch} after PR publication.")
        if prof == "multi-agent":
            finish_board(integration, work, config)
        print("Task published as PR. OpenSpec lifecycle hygiene passed.")
        return 0
    if mode != "direct":
        raise SystemExit(f"Unknown publish_mode: {mode}")
    with serialized_integration(integration, config, args.merge_timeout):
        integrate_and_publish_direct(work, integration, config, branch, main_branch)
        if prof == "multi-agent" and work != integration:
            finish_board(integration, work, config)
    if args.cleanup and work != integration:
        run_git(["worktree", "remove", str(work)], cwd=integration)
        run_git(["branch", "-d", branch], cwd=integration)
        print(f"Removed worktree and branch {branch}.")
    print("Task published directly. OpenSpec lifecycle hygiene passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
