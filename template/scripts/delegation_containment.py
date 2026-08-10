#!/usr/bin/env python3
"""Detect whether a delegated write-capable subagent stayed within its assigned worktree.

See openspec/specs/platform-delegation/spec.md for the contract. This module only
detects and reports; it never stashes, resets, or deletes anything in the
integration copy, since changed paths there may be another agent's legitimate
concurrent work.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class ContainmentError(RuntimeError):
    """A user-facing containment safety error."""


@dataclass(frozen=True)
class GitSnapshot:
    head: str
    status: frozenset[tuple[str, str]]  # (porcelain status code, path)


@dataclass(frozen=True)
class ContainmentResult:
    violated: bool
    new_changes: tuple[str, ...]
    pre_existing_changes: tuple[str, ...]
    head_moved: bool


def run_git(cwd: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(["git", *arguments], cwd=cwd, text=True, capture_output=True, check=False)
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ContainmentError(f"git {' '.join(arguments)} failed: {detail}")
    return completed


def resolve_assigned_worktree(integration_root: Path, assigned_worktree: str | Path) -> Path:
    """Validate assigned_worktree is an absolute, registered worktree distinct from integration_root."""
    raw = Path(assigned_worktree)
    if not raw.is_absolute():
        raise ContainmentError(f"assigned_worktree must be an absolute path, got {raw}")
    resolved = raw.expanduser().resolve()
    integration_resolved = integration_root.resolve()
    if resolved == integration_resolved:
        raise ContainmentError("assigned_worktree must not be the integration copy itself")
    listing = run_git(integration_root, "worktree", "list", "--porcelain")
    registered = {
        Path(line[len("worktree ") :]).resolve()
        for line in listing.stdout.splitlines()
        if line.startswith("worktree ")
    }
    if resolved not in registered:
        raise ContainmentError(f"assigned_worktree {resolved} is not a registered git worktree of {integration_root}")
    return resolved


def snapshot(integration_root: Path) -> GitSnapshot:
    """Capture integration_root's committed HEAD and full working-tree status.

    Raises ContainmentError if the snapshot itself cannot be taken; callers must
    treat that as a containment-check failure, not as "no violation."
    """
    head = run_git(integration_root, "rev-parse", "HEAD").stdout.strip()
    status_output = run_git(integration_root, "status", "--porcelain", "--untracked-files=all").stdout
    entries: set[tuple[str, str]] = set()
    for line in status_output.splitlines():
        if not line:
            continue
        entries.add((line[:2], line[3:]))
    return GitSnapshot(head=head, status=frozenset(entries))


def check_containment(before: GitSnapshot, after: GitSnapshot) -> ContainmentResult:
    """Compare two snapshots of the same integration_root and classify the diff.

    A path present in both snapshots with the same status is pre-existing and is
    never a violation, regardless of how it looks. Only paths newly appearing (or
    a HEAD that moved, meaning something was committed) count as new changes.
    """
    new_entries = after.status - before.status
    pre_existing_still_present = before.status & after.status
    new_paths = tuple(sorted(path for _code, path in new_entries))
    pre_existing_paths = tuple(sorted(path for _code, path in pre_existing_still_present))
    head_moved = after.head != before.head
    violated = bool(new_entries) or head_moved
    return ContainmentResult(
        violated=violated,
        new_changes=new_paths,
        pre_existing_changes=pre_existing_paths,
        head_moved=head_moved,
    )


def format_violation_message(assigned_worktree: Path, result: ContainmentResult) -> str:
    parts = [f"Delegated write containment violation: changes appeared outside assigned worktree {assigned_worktree}."]
    if result.new_changes:
        parts.append("New paths: " + ", ".join(result.new_changes))
    if result.head_moved:
        parts.append("Integration HEAD moved during delegation (something was committed there).")
    return " ".join(parts)


def record_containment_friction(
    integration_root: Path,
    assigned_worktree: Path,
    result: ContainmentResult,
    *,
    task: str | None = None,
) -> None:
    """Record a local friction event for a containment violation.

    Must only be called after check_containment has already produced a definitive
    result (never before). Local JSONL append; does not require GitHub auth.
    """
    observation = format_violation_message(assigned_worktree, result)
    evidence = f"new_changes={list(result.new_changes)!r} head_moved={result.head_moved}"
    arguments = [
        sys.executable,
        str(integration_root / "scripts" / "agent_friction.py"),
        "record",
        "--category",
        "delegated-write-containment-violation",
        "--trigger",
        "unsafe-near-miss",
        "--severity",
        "high",
        "--scope",
        "platform",
        "--observation",
        observation,
        "--evidence",
        evidence,
        "--hypothesis",
        "A write-capable delegated subagent or subprocess wrote outside its assigned worktree.",
        "--proposal",
        "Review the delegation harness's containment wiring (cwd, PreToolUse hook, or sandbox writable root) for this delegation path.",
    ]
    if task:
        arguments.extend(["--task", task])
    completed = subprocess.run(arguments, cwd=integration_root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        print(f"WARNING: could not record containment friction event: {detail}", file=sys.stderr)
