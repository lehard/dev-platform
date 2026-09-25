#!/usr/bin/env python3
"""Resume one Requirement from canonical handoffs through shared delivery.

This is a supervisor adapter, not an autonomous code author or a task queue.
Each invocation performs safe deterministic transitions until bounded child
implementation is needed, then returns the exact worktree to the agent. The
agent reruns this same command after committing and archiving that child.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import agent_board
import managed_project_status
import managed_task
import orchestrate_pre_authoring
import requirement_board
import requirement_intake
import requirement_integration
import start_managed_task
from _platform_common import current_worktree_root, locked_json, machine_path


class RequirementExecutionError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise RequirementExecutionError(result.stderr.strip() or "Git state is unavailable")
    return result.stdout.strip()


def _ordered_handoffs(report: dict[str, Any], requirement: str) -> list[tuple[str, Path]]:
    raw = report.get("handoffs")
    if report.get("current_stage") != "complete" or not isinstance(raw, dict) or not raw:
        raise RequirementExecutionError(f"{requirement}: pre-authoring handoffs are not fresh and complete: {report.get('blocker')}")
    envelopes: dict[str, dict[str, Any]] = {}
    intent_to_change: dict[str, str] = {}
    for change, location in raw.items():
        if not isinstance(change, str) or not isinstance(location, str):
            raise RequirementExecutionError("pre-authoring handoff identity is malformed")
        path = Path(location).resolve()
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RequirementExecutionError(f"cannot read handoff {change}: {exc}") from exc
        expected_id = f"requirement-{requirement.rsplit('#', 1)[1]}"
        if not isinstance(envelope, dict):
            raise RequirementExecutionError(f"handoff {change} is malformed")
        if envelope.get("kind") == "direct-requirement-handoff":
            if change != "direct" or envelope.get("requirement_id") != expected_id or len(raw) != 1:
                raise RequirementExecutionError("direct handoff identity is ambiguous")
            return [(change, path)]
        if envelope.get("add_id") != expected_id:
            raise RequirementExecutionError(f"handoff {change} belongs to another Requirement")
        intents = envelope.get("intents")
        if not isinstance(intents, list) or not intents:
            raise RequirementExecutionError(f"handoff {change} has no intents")
        for intent in intents:
            identity = intent.get("id") if isinstance(intent, dict) else None
            if not isinstance(identity, str) or identity in intent_to_change:
                raise RequirementExecutionError("handoff intents are ambiguous")
            intent_to_change[identity] = change
        envelopes[change] = envelope
    pending = set(envelopes)
    ordered: list[tuple[str, Path]] = []
    while pending:
        ready = sorted(change for change in pending if all(
            intent_to_change.get(dependency) not in pending
            for intent in envelopes[change]["intents"] for dependency in intent.get("dependencies", [])
        ))
        if not ready:
            raise RequirementExecutionError("handoff dependency graph is cyclic or ambiguous")
        for change in ready:
            ordered.append((change, Path(raw[change]).resolve()))
            pending.remove(change)
    return ordered


def _bundle(base_dir: Path, requirement: str, change: str) -> Path:
    number = requirement.rsplit("#", 1)[1]
    path = base_dir / f"requirement-{number}" / "bundles" / change
    if not (path / "manifest.json").is_file():
        raise RequirementExecutionError(f"authored bundle is unavailable for {change}: {path}")
    return path


def _linked_children_by_change(integration: Path, requirement: str, parent: dict[str, Any]) -> dict[str, str]:
    linked = requirement_intake.parse_requirement_body(str(parent.get("body") or ""))["children"]
    result: dict[str, str] = {}
    for child in linked:
        package = managed_task.discover_task(integration, child)
        if package.change in result:
            raise RequirementExecutionError(
                f"{result[package.change]} and {child} both claim managed change {package.change}"
            )
        issue = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(child))
        if requirement_intake.CHILD_LABEL not in managed_task.issue_labels(issue):
            raise RequirementExecutionError(f"linked child {child} lacks its internal-change label")
        backlink = re.search(
            rf"^{re.escape(requirement_intake.BACK_REFERENCE_PREFIX + requirement)}\s*$",
            str(issue.get("body") or ""), re.MULTILINE,
        )
        if backlink is None:
            observation = managed_project_status.observe(integration, source_issue=child)
            if observation is None or observation.current_status != "Done":
                raise RequirementExecutionError(f"{child} lacks its exact parent backlink; repair before child execution")
            requirement_intake.link_child(integration, requirement=requirement, child=child)
        result[package.change] = child
    return result


def _ready_receipt(
    integration: Path, receipt_dir: Path, requirement: str, child: str, change: str,
    *, release_claim: bool = True,
) -> tuple[Path, requirement_integration.ReadyForIntegrationReceipt] | None:
    branch = f"agent/{change}"
    worktree = machine_path("worktrees", integration) / change
    if not worktree.is_dir() or _git(worktree, "branch", "--show-current") != branch:
        return None
    canonical = managed_task.resolve_canonical_provenance(worktree, source_issue=child, change=change)
    if canonical is None or canonical.lifecycle != "archived":
        return None
    archive = canonical.path
    payload = requirement_integration.create_receipt(
        worktree, requirement=requirement, source_issue=child, change=change,
        archived_contract=archive, verification_receipt=archive / "verification.md",
    )
    path = receipt_dir / f"{change}.json"
    receipt = requirement_integration.write_receipt(path, payload)
    if release_claim:
        _release_ready_claim(integration, worktree, receipt)
    return path, receipt


def _done_child_is_delivered(integration: Path, child: str, change: str) -> None:
    canonical = managed_task.resolve_canonical_provenance(integration, source_issue=child, change=change)
    if canonical is None or canonical.lifecycle != "archived":
        raise RequirementExecutionError(f"{child} is marked Done but has no archived contract on main")
    issue = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(child))
    if str(issue.get("state", "")).upper() != "CLOSED":
        raise RequirementExecutionError(f"{child} is marked Done but its source Issue is not closed")


def _release_ready_claim(
    integration: Path, worktree: Path, receipt: requirement_integration.ReadyForIntegrationReceipt,
) -> None:
    """Release only this immutable ready child's active writer claim."""
    board = agent_board.board_path(integration)
    if not board.exists():
        return
    with locked_json(board) as data:
        items = data.get("items")
        if not isinstance(items, list):
            raise RequirementExecutionError("admission board items are unavailable")
        matches = [item for item in items if isinstance(item, dict)
                   and item.get("branch") == receipt.source_branch
                   and item.get("task") == f"Managed task {receipt.source_issue}"
                   and Path(str(item.get("worktree", ""))).resolve() == worktree.resolve()]
        if len(matches) > 1:
            raise RequirementExecutionError("duplicate ready child board claims")
        if matches:
            if _git(worktree, "rev-parse", "HEAD") != receipt.head or _git(worktree, "status", "--porcelain"):
                raise RequirementExecutionError("ready child changed after its receipt; writer claim remains active")
            items.remove(matches[0])


def advance(integration: Path, *, requirement: str, base_dir: Path, confirm_distinct: bool = False) -> dict[str, Any]:
    """Run deterministic transitions; return one bounded agent action or delivery result."""
    integration = integration.resolve()
    if current_worktree_root().resolve() != integration or _git(integration, "branch", "--show-current") != "main":
        raise RequirementExecutionError("Execute Requirement must run from the integration main checkout")
    parent = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementExecutionError(f"{requirement} is not a Business Requirement")
    report = orchestrate_pre_authoring.status(
        integration, requirement_id=f"requirement-{requirement.rsplit('#', 1)[1]}", base_dir=base_dir,
    )
    ordered = _ordered_handoffs(report, requirement)
    linked_by_change = _linked_children_by_change(integration, requirement, parent)
    direct = ordered[0][0] == "direct" if len(ordered) == 1 else False
    if direct:
        if len(linked_by_change) == 1:
            direct_change = next(iter(linked_by_change))
        elif not linked_by_change:
            direct_change = managed_task.load_authoring_bundle(
                str(_bundle(base_dir, requirement, "direct"))
            ).change
        else:
            raise RequirementExecutionError("direct handoff has multiple linked children")
        ordered = [(direct_change, ordered[0][1])]
    current_changes = {change for change, _ in ordered}
    for historical_change, historical_child in linked_by_change.items():
        if historical_change in current_changes:
            continue
        observation = managed_project_status.observe(integration, source_issue=historical_child)
        if observation is None or observation.current_status != "Done":
            raise RequirementExecutionError(f"historical linked child {historical_child} is not terminal")
        _done_child_is_delivered(integration, historical_child, historical_change)
    receipt_dir = integration / ".claude" / "requirement-integration" / f"requirement-{requirement.rsplit('#', 1)[1]}"
    ready: list[Path] = []
    completed: list[str] = []
    receipts_by_change: dict[str, Path] = {}
    for change, handoff in ordered:
        child = linked_by_change.get(change)
        if child is None:
            linked = requirement_intake.materialize_handoff(
                integration, requirement=requirement, handoff_file=handoff,
                bundle_path=_bundle(base_dir, requirement, "direct" if direct else change), base_dir=base_dir,
                confirm_distinct=confirm_distinct,
            )
            child = linked["child"]
            linked_by_change[change] = child
        observation = managed_project_status.observe(integration, source_issue=child)
        status = observation.current_status if observation else None
        if status == "Done":
            _done_child_is_delivered(integration, child, change)
            completed.append(child)
            continue
        existing = _ready_receipt(
            integration, receipt_dir, requirement, child, change,
            release_claim=len(ordered) > 1,
        )
        if existing is not None:
            path, _ = existing
            ready.append(path)
            receipts_by_change[change] = path
            continue
        envelope = json.loads(handoff.read_text(encoding="utf-8"))
        predecessors = [receipts_by_change[dependency] for intent in envelope.get("intents", [])
                        for dependency in intent.get("dependencies", []) if dependency in receipts_by_change]
        if len(set(predecessors)) > 1:
            raise RequirementExecutionError(f"{change} has multiple ready predecessors; select an exact dependency boundary")
        predecessor = predecessors[0] if predecessors else None
        started, _, _ = start_managed_task.start_managed_task(
            integration, child, base_child_receipt=predecessor,
        )
        requirement_board.reconcile_nonterminal(integration, requirement=requirement)
        return {
            "status": "implement-child", "requirement": requirement, "child": child,
            "change": change, "worktree": str(started.task_root),
            "predecessor_receipt": str(predecessor) if predecessor else None,
            "next": "Perform routed bounded implementation, verify, archive and commit; rerun execute_requirement.py advance.",
        }
    if len(ordered) == 1:
        if ready:
            change = ordered[0][0]
            child = linked_by_change[change]
            worktree = machine_path("worktrees", integration) / change
            result = subprocess.run(["python3", "scripts/finish_task.py"], cwd=worktree)
            if result.returncode:
                raise RequirementExecutionError(f"single-child managed finish did not complete (exit {result.returncode})")
        from requirement_terminal import reconcile_parent
        return reconcile_parent(integration, requirement=requirement)
    if len(ready) < 2:
        if not ready and completed:
            return {"status": "already-delivered", "requirement": requirement, "children": completed}
        raise RequirementExecutionError("shared delivery requires at least two verified nonterminal child receipts")
    base = _git(integration, "rev-parse", "HEAD")
    manifest = requirement_integration.assemble_candidate(integration, requirement=requirement, base=base, receipt_paths=ready)
    slug = requirement_integration._candidate_slug(requirement_integration._public_requirement(integration, requirement))
    candidate = integration / ".claude" / "worktrees" / slug
    branch = f"agent/{slug}"
    requirement_integration.compose_candidate(
        integration, manifest=manifest, receipt_paths=ready, worktree=candidate, branch=branch,
    )
    result = requirement_integration.publish_candidate(candidate, manifest=manifest, receipt_paths=ready)
    return {**result, "completed_before_shared_integration": completed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume one Business Requirement through managed child and shared delivery.")
    parser.add_argument("advance", choices=["advance"])
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--base-dir", type=Path)
    parser.add_argument("--confirm-distinct", action="store_true", help="Confirm that reviewed similar Issues are distinct before creating a missing child")
    args = parser.parse_args()
    integration = current_worktree_root().resolve()
    base_dir = (args.base_dir or orchestrate_pre_authoring.default_base_dir(integration)).resolve()
    try:
        result = advance(integration, requirement=args.requirement, base_dir=base_dir, confirm_distinct=args.confirm_distinct)
    except (
        RequirementExecutionError, requirement_intake.RequirementIntakeError,
        requirement_integration.RequirementIntegrationError, managed_task.ManagedTaskError,
        orchestrate_pre_authoring.OrchestratorError, start_managed_task.ManagedAdmissionWait,
        requirement_board.RequirementBoardError, managed_project_status.ManagedProjectStatusError,
    ) as exc:
        print(json.dumps({"status": "blocked", "requirement": args.requirement, "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
