#!/usr/bin/env python3
"""Safely start and materialize a managed OpenSpec task outside integration main."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root, machine_path, profile, read_platform_config, run_git
from managed_task import (
    ManagedTaskError,
    discover_task,
    import_task,
    resolve_canonical_provenance,
    write_task_state,
)
from managed_project_status import ManagedProjectStatusError, reconcile
from start_task import StartedTask, cleanup_started_task, start_task
from start_task import admission_reason, admit_task


class ManagedAdmissionWait(RuntimeError):
    """Managed package/worktree are preserved while a hard claim is active."""


def start_managed_task(root: Path, reference: str, scope: str = "") -> tuple[StartedTask, str, bool]:
    """Discover before task creation, then materialize in the task checkout only."""
    package = discover_task(root, reference)
    config = read_platform_config(root)
    if profile(config) == "multi-agent":
        existing_root = machine_path("worktrees", root) / package.change
        if existing_root.is_dir():
            provenance = resolve_canonical_provenance(
                existing_root, source_issue=package.source_issue, change=package.change
            )
            if provenance is None:
                raise ManagedTaskError(
                    f"existing managed task worktree {existing_root} has no canonical OpenSpec provenance"
                )
            # Bounded migration for tasks created before task-level state was
            # introduced. It records identity only and never reimports the
            # transport package over the repository-local change.
            write_task_state(existing_root, package)
            branch = run_git(["branch", "--show-current"], cwd=existing_root).stdout.strip()
            if not branch:
                raise ManagedTaskError(f"existing managed task worktree is detached: {existing_root}")
            started = StartedTask(profile="multi-agent", branch=branch, task_root=existing_root)
            decision = admit_task(root, started, scope if scope else None)
            desired_status = "Blocked" if decision["decision"] == "WAIT" else "In progress"
            reconciliation = reconcile(existing_root, desired_status, source_issue=package.source_issue)
            if reconciliation is None:
                raise ManagedProjectStatusError("managed resume lost its source Issue identity")
            print(
                f"Managed Project status {'updated' if reconciliation.changed else 'already current'}: "
                f"{package.source_issue} -> {desired_status}"
            )
            if decision["decision"] == "WAIT":
                raise ManagedAdmissionWait(admission_reason(decision))
            return started, package.prepared_against, True
    started = start_task(
        root,
        package.change,
        task=f"Managed task {package.source_issue}",
        scope=scope or f"openspec/changes/{package.change}",
        admission=False,
    )
    try:
        imported, current_main, reused = import_task(
            started.task_root,
            reference,
            expected_revision=package.revision,
        )
        decision = admit_task(root, started, scope if scope else None)
        desired_status = "Blocked" if decision["decision"] == "WAIT" else "In progress"
        reconciliation = reconcile(
            started.task_root,
            desired_status,
            source_issue=package.source_issue,
        )
        if reconciliation is None:
            raise ManagedProjectStatusError("managed start lost its source Issue identity")
        print(
            f"Managed Project status {'updated' if reconciliation.changed else 'already current'}: "
            f"{package.source_issue} -> {desired_status}"
        )
        if decision["decision"] == "WAIT":
            raise ManagedAdmissionWait(admission_reason(decision))
    except ManagedAdmissionWait:
        # WAIT is a resumable state.  Keep the registered worktree and the
        # canonical package so the next explicit invocation can re-check it.
        raise
    except Exception:
        cleanup_started_task(root, started)
        raise
    return started, current_main, reused


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a managed backlog task without writing to integration main.")
    parser.add_argument("issue", help="owner/repo#N or GitHub issue URL")
    parser.add_argument("--scope", default="", help="optional task scope for multi-agent board registration")
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        started, current_main, reused = start_managed_task(root, args.issue, args.scope)
    except ManagedAdmissionWait as exc:
        print(f"Managed task waiting: {exc}")
        return 3
    except (ManagedTaskError, ManagedProjectStatusError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Managed task start blocked: {exc}")
        return 2
    print(f"Managed task {'reused' if reused else 'materialized'} in {started.task_root}")
    print(f"Branch: {started.branch}")
    if started.board_id:
        print(f"Board: {started.board_id}")
    print(f"Current origin/main: {current_main}")
    print("Next: perform semantic preflight in the task checkout, then use the OpenSpec lifecycle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
