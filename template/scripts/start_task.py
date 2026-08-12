from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    github_cli_env,
    harness_mode,
    preflight,
    profile,
    read_platform_config,
    require_fresh_task_base,
    run_git,
)
from rollout_preflight import NONE, RECONCILED, reconcile_pending_rollout
from start_worktree import StartedWorktree, create_worktree


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    if not cleaned:
        raise argparse.ArgumentTypeError("slug must contain letters or numbers")
    return cleaned


@dataclass(frozen=True)
class StartedTask:
    profile: str
    branch: str
    task_root: Path
    board_id: str | None = None


class TaskAdmissionWait(RuntimeError):
    """A resumable multi-agent scope conflict prevented implementation."""


def admit_task(root: Path, started: StartedTask, scope: str | None = None) -> dict[str, object]:
    """Ask the board to atomically claim this task's concrete file scope."""
    if started.profile != "multi-agent":
        return {"decision": "RUN", "claims": []}
    command = [
        "python3",
        str(root / "scripts" / "agent_board.py"),
        "admit",
        "--branch",
        started.branch,
        "--worktree",
        str(started.task_root),
    ]
    if scope is not None:
        command += ["--scope", scope]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"multi-agent admission failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("multi-agent admission returned unreadable JSON") from exc
    if payload.get("decision") not in {"RUN", "WAIT"}:
        raise RuntimeError("multi-agent admission returned an invalid decision")
    return payload


def admission_reason(decision: dict[str, object]) -> str:
    conflicts = decision.get("conflicts", [])
    if not isinstance(conflicts, list) or not conflicts:
        return "hard overlap with another active task"
    rendered: list[str] = []
    for conflict in conflicts[:5]:
        if isinstance(conflict, list) and len(conflict) == 3:
            rendered.append(f"{conflict[0]} ({conflict[1]}): {conflict[2]}")
    return "hard overlap with " + "; ".join(rendered) if rendered else "hard overlap with another active task"


def start_task(root: Path, slug_value: str, task: str, scope: str = "", *, admission: bool = True) -> StartedTask:
    root = root.resolve()
    preflight(root)
    config = read_platform_config(root)
    if harness_mode(config) != "platform":
        raise RuntimeError("harness_mode=project: use the repository-owned task/worktree entrypoint described by its AGENTS.md.")
    prof = profile(config)
    main_branch = str(config.get("main_branch", "main"))
    doctor = subprocess.run(["python3", str(root / "scripts" / "agent_doctor.py")], cwd=root)
    if doctor.returncode != 0:
        raise RuntimeError("agent doctor failed; task start was not attempted")
    subprocess.run(["python3", str(root / "scripts" / "project_sync.py")], cwd=root, check=True)
    rollout_outcome = reconcile_pending_rollout(root, config, github_cli_env(root))
    if rollout_outcome.state == RECONCILED:
        print(rollout_outcome.detail)
    elif rollout_outcome.state == NONE:
        if rollout_outcome.detail:
            print(f"Dev Platform rollout reconciliation skipped: {rollout_outcome.detail}")
    else:
        raise RuntimeError(f"Dev Platform rollout reconciliation blocked task start: {rollout_outcome.detail}")
    observed = require_fresh_task_base(root, "origin", main_branch, task_ref=main_branch)
    print(f"Task-start freshness observation: {main_branch} contains freshly observed origin/{main_branch} ({observed}).")
    if prof == "light":
        checked_out = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
        if checked_out != main_branch:
            raise RuntimeError(f"light profile expects {main_branch!r} checked out; found {checked_out!r}.")
        return StartedTask(profile=prof, branch=main_branch, task_root=root)
    if prof == "standard":
        branch = f"agent/{slug_value}"
        exists = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
        if exists.returncode == 0:
            raise RuntimeError(f"Branch already exists: {branch}")
        run_git(["switch", "-c", branch, main_branch], cwd=root)
        return StartedTask(profile=prof, branch=branch, task_root=root)
    if prof == "multi-agent":
        started: StartedWorktree = create_worktree(root, slug_value, task, scope, sync=False)
        task_started = StartedTask(profile=prof, branch=started.branch, task_root=started.worktree, board_id=started.board_id)
        if admission:
            decision = admit_task(root, task_started, scope)
            if decision["decision"] == "WAIT":
                cleanup_started_task(root, task_started)
                raise TaskAdmissionWait(admission_reason(decision))
        return task_started
    raise RuntimeError(f"Unknown workflow_profile: {prof}")


def cleanup_started_task(root: Path, started: StartedTask) -> None:
    """Remove only the branch/worktree created by this invocation after intake fails."""
    root = root.resolve()
    main_branch = str(read_platform_config(root).get("main_branch", "main"))
    if started.profile == "standard":
        run_git(["switch", main_branch], cwd=root)
        run_git(["branch", "-D", started.branch], cwd=root)
        return
    if started.profile == "multi-agent":
        if started.board_id:
            subprocess.run(["python3", str(root / "scripts" / "agent_board.py"), "finish", "--id", started.board_id, "--quiet"], cwd=root, check=False)
        run_git(["worktree", "remove", "--force", str(started.task_root)], cwd=root, check=False)
        run_git(["branch", "-D", started.branch], cwd=root, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start work using the configured dev-platform workflow profile.")
    parser.add_argument("slug", type=slug)
    parser.add_argument("--task", required=True)
    parser.add_argument("--scope", default="")
    args = parser.parse_args()
    try:
        started = start_task(current_worktree_root(), args.slug, args.task, args.scope)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
    if started.profile == "light":
        print(f"Ready on synchronized {started.branch}. Single-agent light workflow has no task branch.")
        return 0
    if started.profile == "standard":
        print(f"Created feature branch: {started.branch}")
        return 0
    print(f"Created: {started.task_root}")
    print(f"Branch:  {started.branch}")
    print(f"Board:   {started.board_id}")
    print(f"Next:    cd {started.task_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
