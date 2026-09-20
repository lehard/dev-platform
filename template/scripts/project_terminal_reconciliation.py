"""Idempotent terminal reconciliation for a proven exact project-harness PR."""
from __future__ import annotations

import subprocess
from pathlib import Path

from _platform_common import github_cli_env, read_platform_config
from exact_head_safety import exact_pr, exact_state
from managed_project_status import ManagedProjectStatusError, discover_source_issue, reconcile


def reconcile_if_exact_merged(root: Path, branch: str, source_issue: str | None = None) -> bool:
    """Return true only after exact merge proof and terminal Issue/Project reconciliation."""
    config = read_platform_config(root)
    env = github_cli_env(root)
    if env is None:
        raise ManagedProjectStatusError("GitHub authentication is unavailable for terminal reconciliation")
    pr, expected_head = exact_pr(root, branch, str(config.get("main_branch", "main")), env)
    if pr is None or not exact_state(root, pr, expected_head, env):
        return False
    source = discover_source_issue(root) if source_issue is None else None
    reference = source_issue or (source.reference if source is not None else None)
    if reference is None:
        raise ManagedProjectStatusError("exact merged PR has no unambiguous managed source issue")
    observation = reconcile(root, "Done", source_issue=reference)
    issue = source if source is not None and source.reference == reference else discover_source_issue(root)
    if issue is None:
        from managed_project_status import parse_source_issue
        issue = parse_source_issue(reference)
    closed = subprocess.run(
        ["gh", "api", "--method", "PATCH", f"repos/{issue.repository}/issues/{issue.number}", "-f", "state=closed", "-f", "state_reason=completed"],
        cwd=root, env=env, text=True, capture_output=True, check=False,
    )
    if closed.returncode != 0:
        detail = closed.stderr.strip() or closed.stdout.strip() or "GitHub Issue update failed"
        raise ManagedProjectStatusError("terminal Issue reconciliation failed: " + detail)
    if observation is not None:
        print(f"Managed Project status {'updated' if observation.changed else 'already current'}: {reference} -> Done")
    print(f"Managed source Issue closed: {reference}")
    return True
