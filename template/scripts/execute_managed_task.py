#!/usr/bin/env python3
"""Compose managed authoring and start for a fresh execution request.

This is intentionally a thin entrypoint: ``managed_task.create_task`` remains
the sole authoring implementation and ``start_managed_task.start_managed_task``
remains the sole materialization implementation.  Retrying the command reuses
the authoring receipt or exact existing Issue before asking managed start to
resume its exact task identity.
"""
from __future__ import annotations

import argparse
import re
import subprocess

from _platform_common import current_worktree_root
from managed_task import (
    ASSURANCE_VALUES,
    EFFORT_HINT_VALUES,
    ROUTING_CONFIDENCE_VALUES,
    STRONG_TRIGGERS,
    ManagedTaskError,
    create_task,
)
from managed_project_status import ManagedProjectStatusError
from start_managed_task import ManagedAdmissionWait, start_managed_task


EXACT_DUPLICATE = re.compile(r"clear duplicate already exists: ([^;]+); no issue was created")


def existing_exact_issue(error: ManagedTaskError) -> str | None:
    """Return the sole reusable exact identity from authoring's bounded check."""
    match = EXACT_DUPLICATE.fullmatch(str(error))
    return match.group(1) if match else None


def execute_managed_task(root, args: argparse.Namespace):
    """Author/reuse once, then start exactly that Issue without new state."""
    try:
        package, resumed, already_published = create_task(
            root,
            args.bundle,
            args.priority,
            args.confirm_distinct,
            strong_trigger=args.strong_trigger,
            task_family=args.task_family,
            routing_confidence=args.routing_confidence,
            assurance=args.assurance,
            effort_hint=args.effort_hint,
            process_evidence_values=args.process_evidence,
        )
        source_issue = package.source_issue
    except ManagedTaskError as exc:
        source_issue = existing_exact_issue(exc)
        if source_issue is None:
            raise
        resumed = True
        already_published = True

    started, current_main, start_reused = start_managed_task(
        root,
        source_issue,
        args.scope,
        acknowledge_source_issue_revision=args.acknowledge_source_issue_revision,
    )
    return source_issue, resumed, already_published, started, current_main, start_reused


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Author/reuse and start one fresh non-trivial managed task before implementation."
    )
    parser.add_argument("--bundle", required=True, help="directory containing manifest.json, issue.md and declared OpenSpec artifacts")
    parser.add_argument("--scope", default="", help="optional concrete scope for multi-agent admission")
    parser.add_argument("--priority", help="override configured priority (P0, P1, P2 or P3)")
    parser.add_argument("--confirm-distinct", action="store_true", help="confirm bounded candidate tasks are separate work")
    parser.add_argument("--strong-trigger", choices=STRONG_TRIGGERS)
    parser.add_argument("--task-family", default="general")
    parser.add_argument("--routing-confidence", choices=ROUTING_CONFIDENCE_VALUES, default="medium")
    parser.add_argument("--assurance", choices=ASSURANCE_VALUES, default="standard")
    parser.add_argument("--effort-hint", choices=EFFORT_HINT_VALUES)
    parser.add_argument("--process-evidence", action="append", metavar="OWNER/REPO#N")
    parser.add_argument(
        "--acknowledge-source-issue-revision", metavar="BODY_SHA256",
        help="explicitly keep the already-authored package after the source Issue body changed",
    )
    args = parser.parse_args()
    try:
        source, author_reused, package_reused, started, current_main, start_reused = execute_managed_task(
            current_worktree_root(), args
        )
    except ManagedAdmissionWait as exc:
        print(f"Managed task waiting: {exc}")
        return 3
    except (ManagedTaskError, ManagedProjectStatusError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Managed execution intake blocked: {exc}")
        return 2
    author_state = "reused" if author_reused else "created"
    package_state = "already published" if package_reused else "published"
    start_state = "reused" if start_reused else "materialized"
    print(f"Managed task {author_state}: {source} ({package_state})")
    print(f"Managed task {start_state} in {started.task_root}")
    print(f"Branch: {started.branch}")
    print(f"Current origin/main: {current_main}")
    print("Next: perform semantic preflight in the task checkout before implementation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
