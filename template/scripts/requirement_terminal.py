#!/usr/bin/env python3
"""Reconcile a Requirement after every linked managed child is delivered."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import managed_project_status
import managed_task
import requirement_intake
from _platform_common import current_worktree_root, github_cli_env


class RequirementTerminalError(RuntimeError):
    pass


def parent_for_child(root: Path, child: str) -> str | None:
    issue = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(child))
    parents = re.findall(r"^Requirement: (\S+/\S+#\d+)\s*$", str(issue.get("body") or ""), re.MULTILINE)
    if not parents:
        return None
    if len(parents) != 1:
        raise RequirementTerminalError(f"{child} has ambiguous Requirement backlinks")
    return parents[0]


def _close_issue(root: Path, reference: str) -> None:
    env = github_cli_env(root)
    if env is None:
        raise RequirementTerminalError("GitHub authentication is required for terminal Issue closure")
    repository, number = requirement_intake.issue_ref(reference)
    closed = subprocess.run(
        ["gh", "api", "--method", "PATCH", f"repos/{repository}/issues/{number}", "-f", "state=closed", "-f", "state_reason=completed"],
        cwd=root, env=env, text=True, capture_output=True,
    )
    if closed.returncode:
        raise RequirementTerminalError(f"{reference} Issue closure failed: " + (closed.stderr.strip() or closed.stdout.strip()))


def reconcile_parent(root: Path, *, requirement: str, merged_children: set[str] | None = None) -> dict[str, Any]:
    """Use main's archived lineage plus terminal child/Project state as delivery proof."""
    root = root.resolve()
    if subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True).stdout.strip() != "main":
        raise RequirementTerminalError("Requirement terminal reconciliation requires integration main")
    parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementTerminalError(f"{requirement} is not a Business Requirement")
    children = requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]
    if not children or len(children) != len(set(children)):
        raise RequirementTerminalError("Requirement needs a nonempty, unambiguous child set")
    for child in children:
        issue = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(child))
        if requirement_intake.CHILD_LABEL not in managed_task.issue_labels(issue) or parent_for_child(root, child) != requirement:
            raise RequirementTerminalError(f"{child} is not reciprocally linked")
        observed = managed_project_status.observe(root, source_issue=child)
        if observed is None or observed.current_status != "Done":
            raise RequirementTerminalError(f"{child} has no terminal Project state")
        package = managed_task.discover_task(root, child)
        canonical = managed_task.resolve_canonical_provenance(root, source_issue=child, change=package.change)
        if canonical is None or canonical.lifecycle != "archived" or not (canonical.path / "verification.md").is_file():
            raise RequirementTerminalError(f"{child} has no archived verified contract on main")
        if str(issue.get("state", "")).upper() != "CLOSED":
            if merged_children is None or child not in merged_children:
                raise RequirementTerminalError(f"{child} is not closed after delivery")
            _close_issue(root, child)
    observed = managed_project_status.reconcile(root, "Done", source_issue=requirement)
    if observed is None or observed.current_status != "Done":
        raise RequirementTerminalError("parent Project Done reconciliation failed")
    if str(parent.get("state", "")).upper() != "CLOSED":
        _close_issue(root, requirement)
    return {"status": "done", "requirement": requirement, "children": children}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a delivered Business Requirement")
    parser.add_argument("reconcile", choices=["reconcile"])
    parser.add_argument("--requirement", required=True)
    args = parser.parse_args()
    try:
        result = reconcile_parent(current_worktree_root(), requirement=args.requirement)
    except (RequirementTerminalError, managed_task.ManagedTaskError, managed_project_status.ManagedProjectStatusError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
