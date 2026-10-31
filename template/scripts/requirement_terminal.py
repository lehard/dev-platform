#!/usr/bin/env python3
"""Reconcile a Requirement after every linked managed child is delivered."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import managed_project_status
import managed_task
import requirement_intake
import requirement_retrospective
import requirement_target_lifecycle
from _platform_common import current_worktree_root, github_cli_env, lifecycle_mode, read_platform_config


class RequirementTerminalError(RuntimeError):
    pass


class OwnerAcceptancePending(RequirementTerminalError):
    """Declared operator acceptance items have no owner decision; the Requirement stays open (BR-943)."""

    def __init__(self, items: list[str]) -> None:
        self.items = items
        super().__init__("Requirement awaits owner acceptance of: " + ", ".join(items))


# ``## Operator acceptance`` lines: an action only the owner can take outside the repository, with its check.
ACCEPTANCE_SECTION = "operator acceptance"
ACCEPTANCE_ITEM = re.compile(r"^- (?P<id>[a-z0-9][a-z0-9-]*): (?P<action>.+?) Check: `(?P<check>[^`]+)`$")
ACCEPTANCE_PREFIX = "dev-platform-requirement-acceptance:v1 "
ACCEPTANCE_DECISIONS = ("confirmed", "waived")
# Writers of the backlog repository; any other author's marker is ignored, never trusted.
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


def issue_state(issue: dict[str, Any], reference: str) -> str:
    """``OPEN`` or ``CLOSED``; any other or a missing state is an error, never read as open."""
    state = issue.get("state")
    if not isinstance(state, str) or state.upper() not in {"OPEN", "CLOSED"}:
        raise RequirementTerminalError(f"{reference} Issue state is {state!r}, expected OPEN or CLOSED")
    return state.upper()


def operator_items(body: str) -> list[dict[str, str]]:
    """The declared operator acceptance items; a Requirement without the section has none."""
    section = requirement_intake.parse_requirement_body(body)["sections"].get(ACCEPTANCE_SECTION)
    if section is None:
        return []
    items: list[dict[str, str]] = []
    for line in (line.strip() for line in section.splitlines()):
        if not line:
            continue
        match = ACCEPTANCE_ITEM.match(line)
        if match is None:
            raise RequirementTerminalError(
                f"## Operator acceptance line {line!r} is malformed; expected '- <id>: <owner action> Check: `<command>`'")
        if any(item["id"] == match["id"] for item in items):
            raise RequirementTerminalError(f"## Operator acceptance repeats item id {match['id']!r}")
        items.append({"id": match["id"], "action": match["action"].strip(), "check": match["check"].strip()})
    if not items:
        raise RequirementTerminalError("## Operator acceptance has no items; remove the section or declare one")
    return items


def acceptance_decisions(comments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The latest trusted owner decision per item; a malformed trusted marker fails, an untrusted one is ignored."""
    decisions: dict[str, dict[str, Any]] = {}
    for comment in sorted(comments, key=lambda item: item.get("id", 0)):
        body = comment.get("body")
        if not isinstance(body, str) or not body.startswith(ACCEPTANCE_PREFIX):
            continue
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
            continue
        try:
            record = json.loads(body[len(ACCEPTANCE_PREFIX):])
        except json.JSONDecodeError as exc:
            raise RequirementTerminalError(f"trusted acceptance decision comment {comment.get('id')} is not JSON") from exc
        if (not isinstance(record, dict) or not isinstance(record.get("item"), str)
                or record.get("decision") not in ACCEPTANCE_DECISIONS
                or not all(isinstance(record.get(key), str) and record[key].strip() for key in ("actor", "reason", "at"))):
            raise RequirementTerminalError(f"trusted acceptance decision comment {comment.get('id')} is malformed")
        decisions[record["item"]] = record
    return decisions


def open_acceptance_items(root: Path, requirement: str, parent: dict[str, Any]) -> list[str]:
    """Declared items without a trusted owner decision, in declaration order."""
    items = operator_items(str(parent.get("body") or ""))
    if not items:
        return []
    decisions = acceptance_decisions(managed_task.issue_comments(root, *requirement_intake.issue_ref(requirement)))
    return [item["id"] for item in items if item["id"] not in decisions]


def post_merge_closes(root: Path) -> bool:
    """With the coordinator queue only the post-merge jobs record the Requirement retrospective and close it (BR-950).

    Without the queue (portable lifecycle) no runner exists, so the developer session closes through the same
    ``reconcile_parent``.
    """
    if lifecycle_mode(read_platform_config(root)) != "coordinator":
        return False
    import publication_queue
    return publication_queue.enabled(root)


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
    # Closing an Issue that something else already closed answers 422; read the current state first.
    state = requirement_intake.fetch_issue(root, repository, number).get("state")
    if not isinstance(state, str) or state.lower() not in {"open", "closed"}:
        raise RequirementTerminalError(f"{reference} Issue state is {state!r}, expected 'open' or 'closed'")
    if state.lower() == "closed":
        return
    closed = subprocess.run(
        ["gh", "api", "--method", "PATCH", f"repos/{repository}/issues/{number}", "-f", "state=closed", "-f", "state_reason=completed"],
        cwd=root, env=env, text=True, capture_output=True,
    )
    if closed.returncode:
        raise RequirementTerminalError(f"{reference} Issue closure failed: " + (closed.stderr.strip() or closed.stdout.strip()))


def reconcile_parent(root: Path, *, requirement: str, merged_children: set[str] | None = None) -> dict[str, Any]:
    """Use archived lineage on freshly fetched origin main plus terminal child/Project state as delivery proof.

    The lineage is read from the fetched commit, so an integration main that was not
    fast-forwarded never hides a merged archive and is never advanced here.
    """
    root = root.resolve()
    lifecycle_mode(read_platform_config(root))
    if subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True).stdout.strip() != "main":
        raise RequirementTerminalError("Requirement terminal reconciliation requires integration main")
    parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementTerminalError(f"{requirement} is not a Business Requirement")
    try:
        context = requirement_intake.canonical_requirement_context(
            requirement_intake.parse_requirement_body(str(parent.get("body") or ""))
        )
        requirement_target_lifecycle.require_local_target_support(root, target_repository=context["target_repository"])
    except (requirement_intake.RequirementIntakeError, requirement_target_lifecycle.RequirementTargetLifecycleError) as exc:
        raise RequirementTerminalError(str(exc)) from exc
    children = requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]
    if not children or len(children) != len(set(children)):
        raise RequirementTerminalError("Requirement needs a nonempty, unambiguous child set")
    pending = open_acceptance_items(root, requirement, parent)
    if pending:
        raise OwnerAcceptancePending(pending)
    requirement_retrospective.require_checkpoint(root, requirement=requirement, parent=parent)
    commit = managed_task.target_main(root)
    for child in children:
        issue = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(child))
        if requirement_intake.CHILD_LABEL not in managed_task.issue_labels(issue) or parent_for_child(root, child) != requirement:
            raise RequirementTerminalError(f"{child} is not reciprocally linked")
        observed = managed_project_status.observe(root, source_issue=child)
        if observed is None or observed.current_status != "Done":
            raise RequirementTerminalError(f"{child} has no terminal Project state")
        package = managed_task.discover_task(root, child)
        lineage = managed_task.resolve_committed_lineage(root, commit, source_issue=child, change=package.change)
        if lineage is None or lineage.lifecycle != "archived" or not lineage.verified:
            raise RequirementTerminalError(f"{child} has no archived verified contract on origin main {commit}")
        if str(issue.get("state", "")).upper() != "CLOSED":
            if merged_children is None or child not in merged_children:
                raise RequirementTerminalError(f"{child} is not closed after delivery")
            _close_issue(root, child)
    observed = managed_project_status.reconcile(root, "Done", source_issue=requirement)
    if observed is None or observed.current_status != "Done":
        raise RequirementTerminalError("parent Project Done reconciliation failed")
    if issue_state(parent, requirement) != "CLOSED":
        _close_issue(root, requirement)
    return {"status": "done", "requirement": requirement, "children": children}


def _acting_login(root: Path) -> str:
    env = github_cli_env(root)
    if env is None:
        raise RequirementTerminalError("GitHub authentication is required to record an acceptance decision")
    done = subprocess.run(["gh", "api", "user"], cwd=root, env=env, text=True, capture_output=True)
    try:
        login = json.loads(done.stdout).get("login") if not done.returncode else None
    except json.JSONDecodeError:
        login = None
    if not isinstance(login, str) or not login.strip():
        raise RequirementTerminalError("the acting GitHub identity cannot be resolved: "
                                       + (done.stderr.strip() or "no login in gh api user"))
    return login.strip()


def _post_decision(root: Path, requirement: str, record: dict[str, Any]) -> None:
    env = github_cli_env(root)
    if env is None:
        raise RequirementTerminalError("GitHub authentication is required to record an acceptance decision")
    repository, number = requirement_intake.issue_ref(requirement)
    body = ACCEPTANCE_PREFIX + json.dumps(record, sort_keys=True, ensure_ascii=False)
    posted = subprocess.run(["gh", "api", f"repos/{repository}/issues/{number}/comments", "-f", f"body={body}"],
                            cwd=root, env=env, text=True, capture_output=True)
    if posted.returncode:
        raise RequirementTerminalError("acceptance decision was not recorded: " + (posted.stderr.strip() or posted.stdout.strip()))


def accept(root: Path, *, requirement: str, item: str, decision: str, reason: str, via: str | None = None,
           actor: str | None = None, post=None) -> dict[str, Any]:
    """Record the owner's decision on one operator acceptance item; close the Requirement once none is open.

    This is the owner-acceptance stage entry: the close itself is the single closer ``reconcile_parent`` with
    every delivery and retrospective check, so a Requirement that still lacks them is reported, not closed.
    """
    if decision not in ACCEPTANCE_DECISIONS:
        raise RequirementTerminalError(f"--decision must be one of {', '.join(ACCEPTANCE_DECISIONS)}")
    if not reason or not reason.strip():
        raise RequirementTerminalError("an acceptance decision needs the owner's reason")
    parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementTerminalError(f"{requirement} is not a Business Requirement")
    if issue_state(parent, requirement) == "CLOSED":
        raise RequirementTerminalError(f"{requirement} is already closed; nothing to accept")
    declared = [entry["id"] for entry in operator_items(str(parent.get("body") or ""))]
    if item not in declared:
        raise RequirementTerminalError(f"{requirement} declares no operator acceptance item {item!r}"
                                       + (f"; declared: {', '.join(declared)}" if declared else ""))
    record = {"item": item, "decision": decision, "actor": actor or _acting_login(root), "reason": reason.strip()[:300],
              **({"via": via.strip()} if via and via.strip() else {}),
              "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (post or _post_decision)(root, requirement, record)
    pending = open_acceptance_items(root, requirement, parent)
    if pending:
        return {"status": "awaits-owner-acceptance", "requirement": requirement, "recorded": record, "open": pending}
    children = requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]
    return {**reconcile_parent(root, requirement=requirement, merged_children=set(children)), "recorded": record}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a delivered Business Requirement")
    sub = parser.add_subparsers(dest="command", required=True)
    reconcile = sub.add_parser("reconcile", help="coordinator recovery: close a delivered Requirement")
    reconcile.add_argument("--requirement", required=True)
    decide = sub.add_parser("accept", help="record the owner's decision on one operator acceptance item")
    decide.add_argument("--requirement", required=True)
    decide.add_argument("--item", required=True)
    decide.add_argument("--decision", required=True, choices=ACCEPTANCE_DECISIONS)
    decide.add_argument("--reason", required=True)
    decide.add_argument("--via")
    args = parser.parse_args()
    try:
        if args.command == "accept":
            result = accept(current_worktree_root(), requirement=args.requirement, item=args.item,
                            decision=args.decision, reason=args.reason, via=args.via)
        else:
            result = reconcile_parent(current_worktree_root(), requirement=args.requirement)
    except (RequirementTerminalError, requirement_retrospective.RequirementRetrospectiveError,
            managed_task.ManagedTaskError, managed_project_status.ManagedProjectStatusError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
