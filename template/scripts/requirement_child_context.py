#!/usr/bin/env python3
"""Derive a bounded, disposable execution handoff for a Requirement child."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text, run_git
from managed_task import ManagedTaskError, Package, resolve_canonical_provenance
from requirement_integration import ReadyForIntegrationReceipt


PARENT_LINE = re.compile(r"^Requirement: ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9][0-9]*)\s*$", re.MULTILINE)
CONTEXT_VERSION = 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_path(root: Path, change: str) -> Path:
    return root / ".claude" / "requirement-child-context" / f"{change}.json"


def derive_context(
    root: Path, package: Package, *, issue_body: str | None = None,
    predecessor: ReadyForIntegrationReceipt | None = None,
) -> dict[str, Any] | None:
    """Read canonical state only; never copy a sibling body or pre-authoring artifact."""
    parents = PARENT_LINE.findall(issue_body) if issue_body is not None else ([package.parent_requirement] if getattr(package, "parent_requirement", None) else [])
    if not parents:
        if predecessor is not None:
            raise ManagedTaskError("dependent child is missing its parent Requirement reference")
        return None
    if len(parents) != 1:
        raise ManagedTaskError("managed child has ambiguous parent Requirement references")
    parent = parents[0]
    canonical = resolve_canonical_provenance(root, source_issue=package.source_issue, change=package.change)
    if canonical is None or canonical.lifecycle != "active":
        raise ManagedTaskError("Requirement child has no active canonical managed package")
    provenance = canonical.path / ".managed-task.json"
    if not provenance.is_file():
        raise ManagedTaskError("Requirement child canonical provenance is missing")
    head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    if predecessor is not None:
        if predecessor.requirement != parent:
            raise ManagedTaskError("dependent child receipt belongs to a different Requirement")
        if run_git(["merge-base", "--is-ancestor", predecessor.head, "HEAD"], cwd=root, check=False).returncode:
            raise ManagedTaskError("dependent child does not contain the exact predecessor head")
    return {
        "version": CONTEXT_VERSION,
        "requirement": parent,
        "source_issue": package.source_issue,
        "change": package.change,
        "repository_head": head,
        "managed_package": canonical.path.resolve().relative_to(root.resolve()).as_posix(),
        "managed_provenance_sha256": _sha256(provenance),
        "dependencies": ([{
            "source_issue": predecessor.source_issue,
            "change": predecessor.change,
            "head": predecessor.head,
            "receipt_digest": predecessor.digest,
        }] if predecessor else []),
    }


def refresh_context(
    root: Path, package: Package, *, predecessor: ReadyForIntegrationReceipt | None = None,
) -> Path | None:
    """Refresh the local view from discovered linkage and exact imported package."""
    context = derive_context(root, package, predecessor=predecessor)
    path = context_path(root, package.change)
    if context is None:
        return None
    atomic_write_text(path, json.dumps(context, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return path


def validate_context(
    root: Path, package: Package, *, issue_body: str, predecessor: ReadyForIntegrationReceipt | None = None,
) -> dict[str, Any]:
    """Fail closed when a cached view is stale; caller may then refresh it."""
    path = context_path(root, package.change)
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedTaskError(f"Requirement child context is unavailable: {exc}") from exc
    expected = derive_context(root, package, issue_body=issue_body, predecessor=predecessor)
    if expected is None or cached != expected:
        raise ManagedTaskError("Requirement child context is stale; refresh it from canonical source and dependency receipts")
    return expected
