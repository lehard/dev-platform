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
from rollout_preflight import LAG_BEHIND, observe_platform_lag
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


ACKNOWLEDGE_ON_BOARD = (
    "record `agent_board.py acknowledge --with-id <id> --path <path> --reason <bounded reason>` "
    "for the conflicting id/path(s) above, then retry"
)
# A refused start removes its worktree, which `agent_board.py acknowledge` needs: the rerun acknowledges instead.
ACKNOWLEDGE_ON_RESTART = "rerun this start with --acknowledge-overlap <bounded reason>"


def acknowledge_conflicts(root: Path, started: StartedTask, decision: dict[str, object], reason: str) -> None:
    """Record the operator's verified-safe decision for exactly the conflicts this admission reported."""
    paths_by_id: dict[str, list[str]] = {}
    for other_id, _task, path in decision["conflicts"]:
        paths_by_id.setdefault(other_id, []).append(path)
    for other_id, paths in paths_by_id.items():
        command = ["python3", str(root / "scripts" / "agent_board.py"), "acknowledge", "--branch", started.branch,
                   "--worktree", str(started.task_root), "--with-id", other_id, "--reason", reason]
        for path in paths:
            command += ["--path", path]
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise RuntimeError(f"overlap acknowledgment failed: {detail}")


def admission_reason(decision: dict[str, object], safe_exit: str = ACKNOWLEDGE_ON_BOARD) -> str:
    conflicts = decision.get("conflicts", [])
    if not isinstance(conflicts, list) or not conflicts:
        return "hard overlap with another active task"
    rendered: list[str] = []
    for conflict in conflicts[:5]:
        if isinstance(conflict, list) and len(conflict) == 3:
            rendered.append(f"{conflict[0]} ({conflict[1]}): {conflict[2]}")
    if not rendered:
        return "hard overlap with another active task"
    return (
        "hard overlap with "
        + "; ".join(rendered)
        + f". If the overlap is verified safe, {safe_exit}; otherwise wait for the sibling task to finish."
    )


def start_task(root: Path, slug_value: str, task: str, scope: str = "", *, admission: bool = True, branch_name: str | None = None, base_ref: str | None = None, acknowledge_overlap: str | None = None) -> StartedTask:
    root = root.resolve()
    preflight(root)
    config = read_platform_config(root)
    if harness_mode(config) != "platform":
        raise RuntimeError("harness_mode=project: use the repository-owned task/worktree entrypoint described by its AGENTS.md.")
    prof = profile(config)
    if prof == "multi-agent":
        from agent_board import require_scope_paths  # the board ships only with this profile

        require_scope_paths(scope, root)
    main_branch = config["main_branch"]
    doctor = subprocess.run(["python3", str(root / "scripts" / "agent_doctor.py")], cwd=root, stdin=subprocess.DEVNULL)
    if doctor.returncode != 0:
        raise RuntimeError("agent doctor failed; task start was not attempted")
    subprocess.run(["python3", str(root / "scripts" / "project_sync.py")], cwd=root, check=True, stdin=subprocess.DEVNULL)
    # project_sync may have moved platform_version: measure the lag on the re-read config.
    lag = observe_platform_lag(root, read_platform_config(root), github_cli_env(root))
    if lag.state == LAG_BEHIND:
        print(f"Dev Platform release lag: {lag.detail}", flush=True)
    observed = require_fresh_task_base(root, "origin", main_branch, task_ref=main_branch)
    print(f"Task-start freshness observation: {main_branch} contains freshly observed origin/{main_branch} ({observed}).")
    if base_ref is not None:
        run_git(["rev-parse", "--verify", base_ref + "^{commit}"], cwd=root)
    if prof == "light":
        checked_out = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
        if checked_out != main_branch:
            raise RuntimeError(f"light profile expects {main_branch!r} checked out; found {checked_out!r}.")
        return StartedTask(profile=prof, branch=main_branch, task_root=root)
    if prof == "standard":
        branch = branch_name or f"agent/{slug_value}"
        exists = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=root, check=False)
        if exists.returncode == 0:
            raise RuntimeError(f"Branch already exists: {branch}")
        run_git(["switch", "-c", branch, base_ref or main_branch], cwd=root)
        return StartedTask(profile=prof, branch=branch, task_root=root)
    if prof == "multi-agent":
        started: StartedWorktree = create_worktree(root, slug_value, task, scope, sync=False, **({"base": base_ref} if base_ref else {}), **({"branch_name": branch_name} if branch_name else {}))
        task_started = StartedTask(profile=prof, branch=started.branch, task_root=started.worktree, board_id=started.board_id)
        if admission:
            admit_or_remove(root, task_started, scope, acknowledge_overlap)
        return task_started
    raise RuntimeError(f"Unknown workflow_profile: {prof}")


def admit_or_remove(root: Path, started: StartedTask, scope: str, acknowledge_overlap: str | None) -> None:
    """Admit a just-created task, acknowledging its overlap when asked; a task that stays unadmitted is removed."""
    try:
        decision = admit_task(root, started, scope)
        if decision["decision"] == "WAIT" and acknowledge_overlap:
            acknowledge_conflicts(root, started, decision, acknowledge_overlap)
            decision = admit_task(root, started, scope)
        if decision["decision"] == "WAIT":
            raise TaskAdmissionWait(admission_reason(decision, ACKNOWLEDGE_ON_RESTART))
    except RuntimeError:
        cleanup_started_task(root, started)
        raise


def cleanup_started_task(root: Path, started: StartedTask) -> None:
    """Remove only the branch/worktree created by this invocation after intake fails."""
    root = root.resolve()
    main_branch = read_platform_config(root)["main_branch"]
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
    parser.add_argument("--scope", default="", help="repository paths separated by commas or newlines")
    parser.add_argument("--acknowledge-overlap", metavar="REASON", help="Record this reason for a hard overlap verified safe and admit the task.")
    args = parser.parse_args()
    try:
        started = start_task(current_worktree_root(), args.slug, args.task, args.scope, acknowledge_overlap=args.acknowledge_overlap)
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
