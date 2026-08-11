#!/usr/bin/env python3
"""Detect whether a delegated write-capable subagent stayed within its assigned worktree.

See openspec/specs/platform-delegation/spec.md for the contract. This module only
detects and reports; it never stashes, resets, or deletes anything in the
integration copy, since changed paths there may be another agent's legitimate
concurrent work.

The snapshot is content-aware: a dirty/untracked path is fingerprinted by its
actual index blob (when staged) and worktree bytes/symlink target/executable
bit, not merely by its two-character porcelain status code. This lets the
post-check tell "still the same pre-existing dirty state" apart from "someone
changed the contents of that already-dirty path while delegation was running",
even when the status code did not change. Only paths already reported dirty or
untracked by `git status` are fingerprinted, so this never hashes the whole
repository.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class ContainmentError(RuntimeError):
    """A user-facing containment safety error."""


@dataclass(frozen=True)
class PathState:
    status: str  # two-character porcelain status code (XY)
    fingerprint: str  # opaque content-aware fingerprint; equal iff relevant state is equal
    orig_path: str | None = None  # rename/copy source, when applicable


@dataclass(frozen=True)
class GitSnapshot:
    head: str
    paths: dict[str, PathState]


@dataclass(frozen=True)
class ContainmentResult:
    violated: bool
    new_changes: tuple[str, ...]
    pre_existing_changes: tuple[str, ...]
    disappeared_changes: tuple[str, ...]
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


def _parse_porcelain_z(output: str) -> list[tuple[str, str, str | None]]:
    """Parse `git status --porcelain=v1 -z` output into (status, path, orig_path) triples.

    The -z form is NUL-delimited and leaves paths unquoted/unescaped, which avoids the
    whitespace/quoting ambiguity of the newline-delimited default format. Rename/copy
    entries carry an extra NUL-terminated original-path field immediately after the path.
    """
    tokens = output.split("\0")
    entries: list[tuple[str, str, str | None]] = []
    index = 0
    total = len(tokens)
    while index < total:
        token = tokens[index]
        if token == "":
            index += 1
            continue
        status = token[:2]
        path = token[3:]
        index += 1
        orig_path: str | None = None
        if status[0] in ("R", "C") and index < total:
            orig_path = tokens[index]
            index += 1
        entries.append((status, path, orig_path))
    return entries


def _worktree_fingerprint(full_path: Path) -> str:
    """Content-aware fingerprint of a path's current worktree state.

    Read-only. Distinguishes absent/regular-file-content/executable-bit/symlink-target.
    Raises ContainmentError if the path exists but cannot be inspected consistently.
    """
    try:
        stat_result = full_path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        raise ContainmentError(f"cannot inspect worktree path {full_path}: {exc}") from exc

    mode = stat_result.st_mode
    if stat.S_ISLNK(mode):
        try:
            target = os.readlink(full_path)
        except OSError as exc:
            raise ContainmentError(f"cannot read symlink {full_path}: {exc}") from exc
        return f"symlink:{target}"
    if stat.S_ISREG(mode):
        executable = "x" if mode & stat.S_IXUSR else "-"
        try:
            digest = hashlib.sha256(full_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise ContainmentError(f"cannot read worktree path {full_path}: {exc}") from exc
        return f"file:{executable}:{digest}"
    raise ContainmentError(f"unsupported filesystem entry type for containment snapshot: {full_path}")


def _index_fingerprints(integration_root: Path, paths: list[str]) -> dict[str, str]:
    """Batched `git ls-files -s` blob/mode fingerprint for paths with a staged change."""
    if not paths:
        return {}
    result = run_git(integration_root, "ls-files", "-s", "-z", "--", *paths)
    fingerprints: dict[str, str] = {}
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        meta, _, path = entry.partition("\t")
        pieces = meta.split(" ")
        if len(pieces) < 2:
            raise ContainmentError(f"unexpected `git ls-files -s` output for {path!r}: {meta!r}")
        mode, blob = pieces[0], pieces[1]
        fingerprints[path] = f"index:{mode}:{blob}"
    return fingerprints


def snapshot(integration_root: Path) -> GitSnapshot:
    """Capture integration_root's committed HEAD and a content-aware dirty/untracked state map.

    Raises ContainmentError if the snapshot itself cannot be taken; callers must
    treat that as a containment-check failure, not as "no violation."
    """
    head = run_git(integration_root, "rev-parse", "HEAD").stdout.strip()
    status_output = run_git(
        integration_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).stdout
    raw_entries = _parse_porcelain_z(status_output)

    needs_index_fingerprint = [path for status, path, _orig in raw_entries if status[0] not in (" ", "?")]
    index_fingerprints = _index_fingerprints(integration_root, needs_index_fingerprint)

    paths: dict[str, PathState] = {}
    for status, path, orig_path in raw_entries:
        worktree_fp = _worktree_fingerprint(integration_root / path)
        index_fp = index_fingerprints.get(path, "index:none")
        paths[path] = PathState(status=status, fingerprint=f"{index_fp}|{worktree_fp}", orig_path=orig_path)
    return GitSnapshot(head=head, paths=paths)


def check_containment(before: GitSnapshot, after: GitSnapshot) -> ContainmentResult:
    """Compare two content-aware snapshots of the same integration_root and classify the diff.

    A path present in both snapshots is pre-existing-unchanged only when both its status
    code and its content-aware fingerprint are identical -- not merely when the status code
    matches, since the same status code can persist across a real content mutation (for
    example a tracked file staying " M" while its bytes change). A path that disappears
    between snapshots (its dirty/untracked state resolved somehow during delegation) is
    reported rather than silently dropped, since attribution cannot be proven from
    snapshots alone.
    """
    new_changes: list[str] = []
    pre_existing: list[str] = []
    for path, after_state in after.paths.items():
        before_state = before.paths.get(path)
        if (
            before_state is None
            or before_state.status != after_state.status
            or before_state.fingerprint != after_state.fingerprint
        ):
            new_changes.append(path)
        else:
            pre_existing.append(path)
    disappeared = [path for path in before.paths if path not in after.paths]
    head_moved = before.head != after.head
    violated = bool(new_changes) or bool(disappeared) or head_moved
    return ContainmentResult(
        violated=violated,
        new_changes=tuple(sorted(new_changes)),
        pre_existing_changes=tuple(sorted(pre_existing)),
        disappeared_changes=tuple(sorted(disappeared)),
        head_moved=head_moved,
    )


def format_violation_message(assigned_worktree: Path, result: ContainmentResult) -> str:
    parts = [f"Delegated write containment violation: changes appeared outside assigned worktree {assigned_worktree}."]
    if result.new_changes:
        parts.append("New/changed paths: " + ", ".join(result.new_changes))
    if result.disappeared_changes:
        parts.append("Paths that disappeared during delegation: " + ", ".join(result.disappeared_changes))
    if result.head_moved:
        parts.append("Integration HEAD moved during delegation (something was committed there).")
    return " ".join(parts)


def record_containment_friction(
    integration_root: Path,
    assigned_worktree: Path,
    result: ContainmentResult,
    *,
    task: str | None = None,
    enforcement_tier: str | None = None,
) -> None:
    """Record a local friction event for a containment violation.

    Must only be called after check_containment has already produced a definitive
    result (never before). Local JSONL append; does not require GitHub auth.
    """
    observation = format_violation_message(assigned_worktree, result)
    evidence = (
        f"new_changes={list(result.new_changes)!r} "
        f"disappeared_changes={list(result.disappeared_changes)!r} "
        f"head_moved={result.head_moved} "
        f"enforcement_tier={enforcement_tier!r}"
    )
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
