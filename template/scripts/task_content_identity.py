"""Deterministic, auditable identity for managed task content.

The commit SHA remains provenance.  This helper deliberately identifies the
semantic task diff so archive bookkeeping and an irrelevant clean main merge
do not discard otherwise valid completion evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _platform_common import run_git


def _canonical_path(path: str, change: str) -> str:
    active = f"openspec/changes/{change}/"
    archive = "openspec/changes/archive/"
    if path.startswith(active):
        return active + path[len(active):]
    # An archived copy is the same task-owned OpenSpec material under a
    # lifecycle-only location.  Preserve the suffix as its stable name.
    marker = f"-{change}/"
    if path.startswith(archive) and marker in path:
        return active + path.split(marker, 1)[1]
    return path


def content_identity(root: Path, change: str, base_ref: str = "origin/main") -> dict[str, object] | None:
    """Return a proof for the current task-owned diff, or ``None`` if unknown.

    The proof uses the merge base rather than a commit range.  After a clean,
    irrelevant merge from main, the task patch is therefore identical.  Path
    and blob records make the digest inspectable and make deletions explicit.
    """
    base = run_git(["merge-base", "HEAD", base_ref], cwd=root, check=False)
    if base.returncode != 0 or not base.stdout.strip():
        return None
    merge_base = base.stdout.strip()
    changed = run_git(["diff", "--name-only", f"{merge_base}...HEAD"], cwd=root, check=False)
    if changed.returncode != 0:
        return None
    records: dict[str, str | None] = {}
    # Read the final tree, collapsing active/archive aliases to one stable
    # logical path. Archive wins if both appear during the move.
    for raw in sorted(line for line in changed.stdout.splitlines() if line):
        canonical = _canonical_path(raw, change)
        blob = run_git(["rev-parse", f"HEAD:{raw}"], cwd=root, check=False)
        value = blob.stdout.strip() if blob.returncode == 0 and blob.stdout.strip() else None
        if canonical not in records or raw.startswith("openspec/changes/archive/"):
            records[canonical] = value
    payload = {"version": 1, "change": change, "paths": records}
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {"version": 1, "digest": hashlib.sha256(digest_input).hexdigest(), "paths": records, "base": merge_base}


def equivalent_proofs(root: Path, recorded: object, current: object) -> bool:
    """Prove equal task content across a base move with no task-path overlap."""
    if not isinstance(recorded, dict) or not isinstance(current, dict):
        return False
    if recorded.get("version") != 1 or current.get("version") != 1:
        return False
    if not isinstance(recorded.get("paths"), dict) or not isinstance(current.get("paths"), dict):
        return False
    if recorded.get("digest") != current.get("digest"):
        return False
    old_base, new_base = recorded.get("base"), current.get("base")
    if not isinstance(old_base, str) or not isinstance(new_base, str):
        return False
    if old_base == new_base:
        return True
    if run_git(["merge-base", "--is-ancestor", old_base, new_base], cwd=root, check=False).returncode:
        return False
    changed = run_git(["diff", "--name-only", old_base, new_base], cwd=root, check=False)
    if changed.returncode:
        return False
    task_paths = set(recorded["paths"]) | set(current["paths"])
    return task_paths.isdisjoint(changed.stdout.splitlines())
