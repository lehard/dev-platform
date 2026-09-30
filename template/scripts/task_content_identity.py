"""Deterministic, auditable identity for managed task content.

The commit SHA remains provenance.  This helper deliberately identifies the
semantic task diff so archive bookkeeping and an irrelevant clean main merge
do not discard otherwise valid completion evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

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


def content_identity(
    root: Path,
    change: str,
    base_ref: str = "origin/main",
    *,
    exclude: Callable[[str, str], bool] | None = None,
    scope: str | None = None,
) -> dict[str, object] | None:
    """Return a proof for the current task-owned diff, or ``None`` if unknown.

    The proof uses the merge base rather than a commit range.  After a clean,
    irrelevant merge from main, the task patch is therefore identical.  Path
    and blob records make the digest inspectable and make deletions explicit.

    ``exclude(canonical_path, raw_path)`` optionally drops lifecycle-only paths
    from the proof; ``scope`` names that exclusion set inside the digest so a
    narrowed proof is never confused with the full completion proof.  Existing
    callers pass neither and keep the exact historical digest.
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
        if exclude is not None and exclude(canonical, raw):
            continue
        blob = run_git(["rev-parse", f"HEAD:{raw}"], cwd=root, check=False)
        value = blob.stdout.strip() if blob.returncode == 0 and blob.stdout.strip() else None
        if canonical not in records or raw.startswith("openspec/changes/archive/"):
            records[canonical] = value
    payload: dict[str, object] = {"version": 1, "change": change, "paths": records}
    if scope is not None:
        payload["scope"] = scope
    digest_input = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    proof: dict[str, object] = {"version": 1, "digest": hashlib.sha256(digest_input).hexdigest(), "paths": records, "base": merge_base}
    if scope is not None:
        proof["scope"] = scope
    return proof


# Lifecycle-only files inside the change directory: receipts and review
# evidence describe the candidate rather than being part of it.
REVIEW_EXCLUDED_FILES = (
    "verification.md",
    "automated-checks.json",
    "independent-review-request.json",
    "independent-review-dispositions.json",
)
REVIEW_EXCLUDED_DIRS = ("evidence/", "independent-reviews/")
REVIEW_SCOPE = "independent-review-v1"


def review_exclusion(root: Path, change: str, base_ref: str = "origin/main") -> Callable[[str, str], bool]:
    """Exclude lifecycle receipts, review evidence and own spec materialization.

    ``openspec/specs/<capability>/spec.md`` is excluded only after archive and
    only for capabilities the change's own delta specs name, because archive
    materializes exactly those files.
    """
    active = f"openspec/changes/{change}/"
    capabilities: set[str] = set()
    base = run_git(["merge-base", "HEAD", base_ref], cwd=root, check=False)
    if base.returncode == 0 and base.stdout.strip():
        changed = run_git(["diff", "--name-only", f"{base.stdout.strip()}...HEAD"], cwd=root, check=False)
        for raw in changed.stdout.splitlines() if changed.returncode == 0 else []:
            canonical = _canonical_path(raw, change)
            if canonical.startswith(active + "specs/"):
                parts = canonical[len(active + "specs/"):].split("/")
                if len(parts) >= 2 and parts[0]:
                    capabilities.add(parts[0])

    # Archive materializes exactly ``openspec/specs/<capability>/spec.md`` for
    # the delta's capabilities; before archive any accepted-spec edit counts.
    archived = any(
        (root / "openspec" / "changes" / "archive").glob(f"*-{change}")
    ) and not (root / active).is_dir()

    def exclude(canonical: str, raw: str) -> bool:
        if canonical.startswith(active):
            relative = canonical[len(active):]
            return relative in REVIEW_EXCLUDED_FILES or relative.startswith(REVIEW_EXCLUDED_DIRS)
        if canonical.startswith("openspec/specs/") and archived:
            parts = canonical[len("openspec/specs/"):].split("/")
            return len(parts) == 2 and parts[0] in capabilities and parts[1] == "spec.md"
        return False

    return exclude


def review_path_partition(
    root: Path, change: str, base_ref: str = "origin/main", merge_base: str | None = None,
) -> tuple[list[str], list[str]] | None:
    """Split changed paths into ``(reviewed, excluded_lifecycle)`` raw paths.

    The reviewed set is exactly what ``review_content_identity`` binds, so what
    a reviewer sees and what invalidates its evidence stay the same set.
    Renames are listed as a deletion plus an addition so the reviewer also sees
    removed task content.  Returns ``None`` when the diff cannot be listed.
    """
    if merge_base is None:
        base = run_git(["merge-base", "HEAD", base_ref], cwd=root, check=False)
        if base.returncode != 0 or not base.stdout.strip():
            return None
        merge_base = base.stdout.strip()
    # ``-z`` yields unquoted names, safe for literal pathspecs.
    changed = run_git(["diff", "--name-only", "--no-renames", "-z", f"{merge_base}...HEAD"], cwd=root, check=False)
    if changed.returncode != 0:
        return None
    exclude = review_exclusion(root, change, base_ref)
    reviewed: list[str] = []
    excluded: list[str] = []
    for raw in sorted(dict.fromkeys(item for item in changed.stdout.split("\0") if item)):
        (excluded if exclude(_canonical_path(raw, change), raw) else reviewed).append(raw)
    return reviewed, excluded


def review_content_identity(root: Path, change: str, base_ref: str = "origin/main") -> dict[str, object] | None:
    """Task-content identity that independent review evidence binds to."""
    return content_identity(
        root, change, base_ref, exclude=review_exclusion(root, change, base_ref), scope=REVIEW_SCOPE
    )


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
    if recorded.get("scope") != current.get("scope"):
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
