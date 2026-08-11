#!/usr/bin/env python3
"""Safely start and materialize a managed OpenSpec task outside integration main."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from _platform_common import current_worktree_root
from managed_task import ManagedTaskError, check_schema, discover_task, import_task
from start_task import StartedTask, cleanup_started_task, start_task


def start_managed_task(root: Path, reference: str, scope: str = "") -> tuple[StartedTask, str, bool]:
    """Discover before task creation, then materialize in the task checkout only."""
    package = discover_task(root, reference)
    check_schema(root, package)
    started = start_task(
        root,
        package.change,
        task=f"Managed task {package.source_issue}",
        scope=scope or f"openspec/changes/{package.change}",
    )
    try:
        imported, current_main, reused = import_task(
            started.task_root,
            reference,
            expected_revision=package.revision,
        )
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
    except (ManagedTaskError, RuntimeError, subprocess.CalledProcessError) as exc:
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
