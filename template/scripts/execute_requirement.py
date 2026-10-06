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
import requirement_retrospective
import requirement_target_lifecycle
import start_managed_task
from _platform_common import current_worktree_root, locked_json, machine_path


class RequirementExecutionError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, stdin=subprocess.DEVNULL)
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
    for change, envelope in envelopes.items():
        for intent in envelope["intents"]:
            for dependency in intent.get("dependencies", []):
                if dependency not in intent_to_change:
                    raise RequirementExecutionError(f"{change}: unknown dependency {dependency}")
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


def _contribution_publication_supported(root: Path) -> bool:
    from _platform_common import read_platform_config
    config = read_platform_config(root)
    if (config.get("platform_version") != "source" or config.get("publish_mode", "pr") != "pr"
            or config.get("scm_provider", "github").lower() != "github"
            or config.get("harness_mode", "platform") != "platform"):
        return False
    import publication_queue
    return publication_queue.enabled(root)


def _single_child_in_flight(worktree: Path, *, adapter=None) -> bool:
    """Observe trusted handoff ownership and remote advancement before developer publication."""
    if adapter is None:
        import publication_queue as adapter
    branch = _git(worktree, "branch", "--show-current")
    head = _git(worktree, "rev-parse", "HEAD")
    repo = adapter._repo(worktree)
    rows = adapter._gh(worktree, "pr", "list", "--state", "all", "--head", branch,
                       "--base", "main", "--limit", "100", "--json", "number")
    if not isinstance(rows, list) or len(rows) >= 100:
        raise RequirementExecutionError("single-child PR inventory unavailable or exceeds bound")
    owned = []
    for row in rows:
        number = row["number"]
        pr = adapter._pr(worktree, repo, number)
        if pr["head"]["ref"] != branch or pr["base"]["ref"] != "main":
            raise RequirementExecutionError("single-child PR identity changed during observation")
        comments = adapter._comments(worktree, repo, number)
        current = adapter._derive(worktree, pr, comments)
        if adapter._malformed(current):
            raise RequirementExecutionError(f"malformed coordinator ownership for single-child PR #{number}")
        if (adapter._latest(worktree, number, comments) is not None
                or adapter._admission(adapter._events(worktree, repo, number), number) is not None
                or pr["head"]["sha"] != head):
            owned.append(number)
    if len(owned) > 1:
        raise RequirementExecutionError("multiple coordinator candidates for the single child")
    return bool(owned)


def _publish_active_child(integration: Path, child: str, change: str) -> bool:
    if not _contribution_publication_supported(integration):
        return False
    worktree = machine_path("worktrees", integration) / change
    if not worktree.is_dir():
        return False
    if _single_child_in_flight(worktree):
        return True
    canonical = managed_task.resolve_canonical_provenance(worktree, source_issue=child, change=change)
    if canonical is None or canonical.lifecycle != "active":
        return False
    from openspec_lifecycle import task_state
    total, incomplete = task_state(canonical.path)
    if not total or incomplete:
        return False
    result = subprocess.run(["python3", "scripts/finish_task.py"], cwd=worktree, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise RequirementExecutionError(f"single-child developer handoff blocked (exit {result.returncode})")
    return True


def _ready_receipt(
    integration: Path, receipt_dir: Path, requirement: str, child: str, change: str,
    *, release_claim: bool = True, superseded: list[dict[str, str]] | None = None,
) -> tuple[Path, requirement_integration.ReadyForIntegrationReceipt] | None:
    worktree = machine_path("worktrees", integration) / change
    if not worktree.is_dir():
        return None
    branch = requirement_integration._registered_worktrees(integration).get(worktree.resolve())
    if not branch or _git(worktree, "branch", "--show-current") != branch:
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
    # A failed earlier attempt may have left this lifecycle's own receipt for an
    # ancestor head; supersede it only on proven advancement in the child worktree.
    previous = requirement_integration.superseded_receipt_head(path, payload, root=worktree)
    receipt = requirement_integration.write_receipt(path, payload, root=worktree)
    if previous is not None and superseded is not None:
        superseded.append({
            "source_issue": child, "change": change, "receipt": str(path),
            "superseded_head": previous, "head": receipt.head,
        })
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


def _child_review_state(worktree: Path, child: str, change: str) -> dict[str, Any]:
    """Derived independent review state of a child, read from its change files."""
    try:
        from independent_review import review_state
    except (ImportError, ModuleNotFoundError):
        return {"state": "not-required", "next": None, "detail": None}
    try:
        canonical = managed_task.resolve_canonical_provenance(worktree, source_issue=child, change=change)
        return review_state(worktree, canonical.path if canonical is not None else None)
    except Exception as exc:  # Resume guidance must not fail on unreadable evidence.
        return {"state": "unknown", "next": None, "detail": str(exc)}


def _expected_changes(ordered: list[tuple[str, Path]], linked_by_change: dict[str, str], completed: list[str]) -> list[str]:
    """Mandatory changes still to be delivered, in handoff order."""
    return [change for change, _ in ordered if linked_by_change.get(change) not in completed]


def _existing_candidate(integration: Path, requirement: str, ready: list[Path]) -> dict[str, Any] | None:
    """Find the one early candidate whose committed children are an exact prefix of the ready chain."""
    slug = requirement_integration._candidate_slug(requirement_integration._public_requirement(integration, requirement))
    path = requirement_integration._candidate_manifest_path(requirement, integration).as_posix()
    heads: list[str] | None = None
    matches: list[dict[str, Any]] = []
    for branch in _git(integration, "for-each-ref", "--format=%(refname:short)", f"refs/heads/agent/{slug}*").splitlines():
        shown = subprocess.run(["git", "show", f"{branch}:{path}"], cwd=integration, text=True, capture_output=True)
        if shown.returncode:
            continue
        try:
            manifest = json.loads(shown.stdout)
        except json.JSONDecodeError:
            continue
        if not isinstance(manifest, dict) or manifest.get("expected_changes") is None:
            continue
        if heads is None:
            heads = [requirement_integration.read_receipt(item).head for item in ready]
        committed = [child.get("head") for child in manifest.get("children", [])]
        if committed and committed == heads[:len(committed)] and branch == "agent/" + requirement_integration._candidate_slug(
                manifest["requirement"], manifest.get("generation")):
            matches.append(manifest)
    if len(matches) > 1:
        raise RequirementExecutionError("multiple shared candidates match this Requirement's ready children; resolve the ambiguity")
    return matches[0] if matches else None


def _candidate_for(integration: Path, requirement: str, ready: list[Path], expected: list[str]) -> tuple[dict[str, Any], Path, str]:
    """Resume the existing early candidate (keeping its base) or bind a new one to current main."""
    existing = _existing_candidate(integration, requirement, ready)
    base = existing["base"] if existing is not None else _git(integration, "rev-parse", "HEAD")
    manifest = requirement_integration.assemble_candidate(
        integration, requirement=requirement, base=base, receipt_paths=ready, expected_changes=expected,
    )
    slug = requirement_integration._candidate_slug(
        requirement_integration._public_requirement(integration, requirement), manifest.get("generation"),
    )
    return manifest, integration / ".claude" / "worktrees" / slug, f"agent/{slug}"


def _publish_early_draft(
    integration: Path, requirement: str, ordered: list[tuple[str, Path]], linked_by_change: dict[str, str],
    ready: list[Path], completed: list[str],
) -> dict[str, Any] | None:
    """Open or grow the one shared draft PR while later mandatory children are still in progress."""
    expected = _expected_changes(ordered, linked_by_change, completed)
    if len(expected) < 2:
        return None
    manifest, candidate, branch = _candidate_for(integration, requirement, ready, expected)
    requirement_integration.compose_candidate(
        integration, manifest=manifest, receipt_paths=ready, worktree=candidate, branch=branch,
    )
    return requirement_integration.publish_candidate(candidate, manifest=manifest, receipt_paths=ready)


def advance(integration: Path, *, requirement: str, base_dir: Path, confirm_distinct: bool = False) -> dict[str, Any]:
    """Run deterministic transitions; return one bounded agent action or delivery result."""
    integration = integration.resolve()
    if current_worktree_root().resolve() != integration or _git(integration, "branch", "--show-current") != "main":
        raise RequirementExecutionError("Execute Requirement must run from the integration main checkout")
    parent = requirement_intake.fetch_issue(integration, *requirement_intake.issue_ref(requirement))
    if requirement_intake.REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementExecutionError(f"{requirement} is not a Business Requirement")
    try:
        context = requirement_intake.canonical_requirement_context(
            requirement_intake.parse_requirement_body(str(parent.get("body") or ""))
        )
        requirement_target_lifecycle.require_local_target_support(
            integration, target_repository=context["target_repository"]
        )
    except (requirement_intake.RequirementIntakeError, requirement_target_lifecycle.RequirementTargetLifecycleError) as exc:
        raise RequirementExecutionError(str(exc)) from exc
    report = orchestrate_pre_authoring.status(
        integration, requirement_id=f"requirement-{requirement.rsplit('#', 1)[1]}", base_dir=base_dir,
    )
    # Claim the card before child discovery so a resumed Requirement is not left in the free queue.
    requirement_board.claim_started(integration, requirement=requirement)
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
    if len(ordered) > 1 and _contribution_publication_supported(integration):
        return _advance_contributions(integration, requirement, ordered, linked_by_change, base_dir, confirm_distinct)
    receipt_dir = integration / ".claude" / "requirement-integration" / f"requirement-{requirement.rsplit('#', 1)[1]}"
    superseded: list[dict[str, str]] = []

    def audited(result: dict[str, Any]) -> dict[str, Any]:
        # Replaced own stale receipts are reported for operator audit.
        return {**result, "superseded_receipts": list(superseded)} if superseded else result

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
        if len(ordered) == 1 and _publish_active_child(integration, child, change):
            return audited({"status": "await-child-review", "requirement": requirement, "child": child,
                            "change": change, "reason": "child handed off; coordinator work is in flight"})
        existing = _ready_receipt(
            integration, receipt_dir, requirement, child, change,
            release_claim=len(ordered) > 1, superseded=superseded,
        )
        if existing is not None:
            path, _ = existing
            ready.append(path)
            receipts_by_change[change] = path
            continue
        draft = _publish_early_draft(integration, requirement, ordered, linked_by_change, ready, completed) if ready else None
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
        return audited({
            "status": "implement-child", "requirement": requirement, "child": child,
            "change": change, "worktree": str(started.task_root),
            "predecessor_receipt": str(predecessor) if predecessor else None,
            "shared_draft": draft,
            "independent_review": _child_review_state(Path(started.task_root), child, change),
            "next": (
                "Perform routed bounded implementation, establish selected checks and semantic verification, and commit; "
                "rerun execute_requirement.py advance to publish the active child for coordinator review and finalization."
                if len(ordered) == 1 and _contribution_publication_supported(integration) else
                "Perform routed bounded implementation, verify, archive and commit; rerun execute_requirement.py advance. "
                "When independent review is required, archive runs it automatically; follow independent_review.next if it is blocked. "
                f"Check reviewer runtime readiness after routing with: python3 scripts/independent_review.py preflight {change}"
            ),
        })
    if len(ordered) == 1:
        if ready:
            requirement_retrospective.require_checkpoint(integration, requirement=requirement)
            change = ordered[0][0]
            child = linked_by_change[change]
            worktree = machine_path("worktrees", integration) / change
            result = subprocess.run(["python3", "scripts/finish_task.py"], cwd=worktree, stdin=subprocess.DEVNULL)
            if result.returncode:
                raise RequirementExecutionError(f"single-child managed finish did not complete (exit {result.returncode})")
        from requirement_terminal import reconcile_parent
        return audited(reconcile_parent(integration, requirement=requirement))
    if len(ready) < 2:
        if not ready and completed:
            return audited({"status": "already-delivered", "requirement": requirement, "children": completed})
        raise RequirementExecutionError("shared delivery requires at least two verified nonterminal child receipts")
    requirement_retrospective.require_checkpoint(integration, requirement=requirement)
    expected = _expected_changes(ordered, linked_by_change, completed)
    manifest, candidate, branch = _candidate_for(integration, requirement, ready, expected)
    requirement_integration.compose_candidate(
        integration, manifest=manifest, receipt_paths=ready, worktree=candidate, branch=branch,
    )
    result = requirement_integration.publish_candidate(candidate, manifest=manifest, receipt_paths=ready)
    return audited({**result, "completed_before_shared_integration": completed})


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
        requirement_retrospective.RequirementRetrospectiveError,
        requirement_integration.RequirementIntegrationError, managed_task.ManagedTaskError,
        orchestrate_pre_authoring.OrchestratorError, start_managed_task.ManagedAdmissionWait,
        requirement_board.RequirementBoardError, managed_project_status.ManagedProjectStatusError,
    ) as exc:
        print(json.dumps({"status": "blocked", "requirement": args.requirement, "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0





def _handoff_dependencies(ordered: list[tuple[str, Path]]) -> dict[str, list[str]]:
    envelopes = {change: json.loads(path.read_text()) for change, path in ordered}
    owners = {intent["id"]: change for change, envelope in envelopes.items() for intent in envelope.get("intents", [])}
    return {change: sorted({owners[d] for intent in envelope.get("intents", [])
                            for d in intent.get("dependencies", []) if owners[d] != change})
            for change, envelope in envelopes.items()}


def _advance_contributions(integration: Path, requirement: str, ordered: list[tuple[str, Path]],
                           linked: dict[str, str], base_dir: Path, confirm_distinct: bool) -> dict:
    from requirement_contributions import ensure_integration_branch, in_flight_children
    from _platform_common import read_platform_config
    from requirement_composition import publish_composition

    # Materialize all identities before starting work. No sibling backlog is invented.
    for change, handoff in ordered:
        if change not in linked:
            linked[change] = requirement_intake.materialize_handoff(
                integration, requirement=requirement, handoff_file=handoff,
                bundle_path=_bundle(base_dir, requirement, change), base_dir=base_dir,
                confirm_distinct=confirm_distinct)["child"]
    config = read_platform_config(integration)
    repository = str(config.get("repository") or managed_task.origin_repository(integration))
    graph = _handoff_dependencies(ordered)
    boundary = ensure_integration_branch(integration, requirement=requirement, repository=repository,
                                         expected_changes=[c for c, _ in ordered], dependencies=graph)
    branch, head, manifest = boundary["branch"], boundary["head"], boundary["manifest"]
    _git(integration, "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}")
    integrated = {child["change"]: child for child in manifest["children"]}
    in_flight = in_flight_children(integration, repository, requirement, branch)
    actions, waiting = [], []
    for change, _ in ordered:
        if change in integrated:
            continue
        if change in in_flight:
            waiting.append(in_flight[change])
            continue
        missing = [d for d in graph[change] if d not in integrated]
        if missing:
            waiting.append({"change": change, "dependencies": missing})
            continue
        contribution = {"requirement": requirement, "branch": f"origin/{branch}", "target_branch": branch,
                        "head": head, "dependencies": [integrated[d] for d in graph[change]]}
        # A resumed child keeps its original exact base even as other contributions arrive.
        from requirement_child_context import context_path
        cached = context_path(machine_path("worktrees", integration) / change, change)
        if cached.is_file():
            contribution = json.loads(cached.read_text()).get("contribution") or contribution
        try:
            started, _, _ = start_managed_task.start_managed_task(integration, linked[change], contribution=contribution)
        except start_managed_task.ManagedAdmissionWait as exc:
            waiting.append({"change": change, "reason": str(exc)})
            continue
        actions.append({"child": linked[change], "change": change, "worktree": str(started.task_root),
                        "contribution_base": contribution["head"], "target_branch": branch,
                        "next": "Perform routed implementation and developer handoff; rerun advance after contribution integration."})
    requirement_board.reconcile_nonterminal(integration, requirement=requirement)
    draft = publish_composition(integration, repository, manifest, head)
    return {"status": draft["status"] if draft["status"] == "merged-and-reconciled" else
            "implement-children" if actions else "await-contributions", "requirement": requirement,
            "actions": actions, "waiting": waiting, "shared_draft": draft}


if __name__ == "__main__":
    raise SystemExit(main())
