#!/usr/bin/env python3
"""Human-facing Business Requirement intake and pre-authoring linkage.

A Requirement is the durable human-facing unit: an ordinary Development
Backlog Issue labeled ``type:requirement``, carrying only business language
(outcome, context, target repository, acceptance evidence, exclusions) --
never an OpenSpec proposal/design/tasks. Internal managed OpenSpec changes
materialize only once pre-authoring (see orchestrate_pre_authoring.py, #129)
reaches a handoff; each becomes its own ordinary managed task Issue, labeled
``type:internal-change`` and linked back to its parent Requirement.

Aggregation is read-through: this module stores no separate status of its
own. It reads the local pre-authoring orchestrator and each linked child's
real Development Backlog Project status, then derives a display projection
from those authoritative observations. The projection is never persisted, so
a Requirement's progress cannot diverge from the lifecycle that owns it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import managed_project_status
import managed_task
import orchestrate_pre_authoring
from _platform_common import atomic_write_text, current_worktree_root, github_cli_env
from managed_task import ManagedTaskError, fetch_issue, issue_ref, repo, run

REQUIREMENT_LABEL = "type:requirement"
CHILD_LABEL = "type:internal-change"
CHILDREN_START = "<!-- requirement-children:start -->"
CHILDREN_END = "<!-- requirement-children:end -->"
CHILD_ITEM_RE = re.compile(r"^[ \t]*- \[[ xX]\] (?P<ref>\S+/\S+#\d+)\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^## (?P<name>.+?)\s*$", re.MULTILINE)
BACK_REFERENCE_PREFIX = "Requirement: "
REQUIREMENT_CONTEXT_VERSION = 1
PROJECT_STATUSES = frozenset(managed_project_status.EXPECTED_STATUSES)
ORCHESTRATOR_STAGES = frozenset({"selection", "snapshot", "add", "intents", "handoff", "complete"})


class RequirementIntakeError(RuntimeError):
    pass


def requirement_slug(number: int) -> str:
    return f"requirement-{number}"


def render_requirement_body(
    *,
    outcome: str,
    target_repository: str,
    context: str = "",
    acceptance_evidence: str = "",
    exclusions: str = "",
) -> str:
    if not outcome.strip():
        raise RequirementIntakeError("outcome must be a non-empty string")
    if not target_repository.strip():
        raise RequirementIntakeError("target_repository must be a non-empty string")
    sections = [f"## Outcome\n\n{outcome.strip()}\n"]
    if context.strip():
        sections.append(f"## Context\n\n{context.strip()}\n")
    if acceptance_evidence.strip():
        sections.append(f"## Acceptance evidence\n\n{acceptance_evidence.strip()}\n")
    sections.append(f"## Target repository\n\n`{repo(target_repository)}`\n")
    if exclusions.strip():
        sections.append(f"## Exclusions\n\n{exclusions.strip()}\n")
    sections.append(f"{CHILDREN_START}\n{CHILDREN_END}\n")
    return "\n".join(sections)


def parse_requirement_body(body: str) -> dict[str, Any]:
    """Extract sections and linked children. Never raises on a malformed body.

    A Requirement Issue is edited by hand in the ordinary GitHub UI, so
    parsing is best-effort: a missing section is simply absent from the
    result rather than a hard failure. Only the children block is
    structurally load-bearing (used for linkage/aggregation). The children
    block's HTML-comment markers are invisible in the rendered Issue view, so
    a human editing sections may add or move content before or after it;
    section-scanning excises the children block from the body first so a
    section on either side of it is still recognized.
    """
    children_start = body.find(CHILDREN_START)
    children_end = body.find(CHILDREN_END)
    children: list[str] = []
    section_source = body
    if children_start != -1 and children_end != -1 and children_end > children_start:
        block = body[children_start + len(CHILDREN_START):children_end]
        children = [match.group("ref") for match in CHILD_ITEM_RE.finditer(block)]
        section_source = body[:children_start] + body[children_end + len(CHILDREN_END):]
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(section_source))
    for index, match in enumerate(matches):
        name = match.group("name").strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_source)
        sections[name] = section_source[start:end].strip()
    return {"sections": sections, "children": children}


def _normalize_business_text(value: str) -> str:
    """Normalize presentation-only whitespace in a business Requirement section."""
    return " ".join(value.split())


def canonical_requirement_context(parsed: dict[str, Any]) -> dict[str, Any]:
    """Return the complete, deterministic pre-authoring view of a Requirement."""
    sections = parsed.get("sections")
    if not isinstance(sections, dict):
        raise RequirementIntakeError("Requirement sections are invalid")
    outcome = sections.get("outcome")
    target_repository = sections.get("target repository")
    if not isinstance(outcome, str) or not outcome.strip():
        raise RequirementIntakeError("Requirement has no ## Outcome section")
    if not isinstance(target_repository, str) or not target_repository.strip():
        raise RequirementIntakeError("Requirement has no ## Target repository section")
    return {
        "version": REQUIREMENT_CONTEXT_VERSION,
        "outcome": _normalize_business_text(outcome),
        "context": _normalize_business_text(str(sections.get("context") or "")),
        "acceptance_evidence": _normalize_business_text(str(sections.get("acceptance evidence") or "")),
        "exclusions": _normalize_business_text(str(sections.get("exclusions") or "")),
        "target_repository": repo(target_repository.strip("` \n")),
    }


def render_canonical_requirement_context(context: dict[str, Any]) -> str:
    """Serialize the derived context in one stable local representation."""
    return json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def create_requirement(
    root: Path,
    *,
    repository: str,
    title: str,
    outcome: str,
    target_repository: str,
    context: str = "",
    acceptance_evidence: str = "",
    exclusions: str = "",
) -> dict[str, Any]:
    if not title.strip():
        raise RequirementIntakeError("title must be a non-empty string")
    repository = repo(repository)
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required; run gh auth login and retry")
    ensure_label(root, repository, REQUIREMENT_LABEL, env=env)
    body = render_requirement_body(
        outcome=outcome, target_repository=target_repository, context=context,
        acceptance_evidence=acceptance_evidence, exclusions=exclusions,
    )
    result = run(
        ["gh", "issue", "create", "--repo", repository, "--title", title.strip(), "--body", body, "--label", REQUIREMENT_LABEL],
        root, env,
    )
    created_repository, number = issue_ref(result.stdout.strip())
    return {"repository": created_repository, "number": number, "slug": requirement_slug(number)}


def ensure_label(root: Path, repository: str, name: str, *, env: dict[str, str], description: str = "") -> None:
    run(["gh", "label", "create", name, "--repo", repository, "--force", "--description", description], root, env)


def default_base_dir(root: Path) -> Path:
    return orchestrate_pre_authoring.default_base_dir(root)


def start_pre_authoring(
    root: Path, *, requirement: str, base_dir: Path | None = None
) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    issue = fetch_issue(root, repository, number)
    parsed = parse_requirement_body(str(issue.get("body") or ""))
    try:
        context = canonical_requirement_context(parsed)
    except RequirementIntakeError as exc:
        raise RequirementIntakeError(f"{requirement}: {exc}") from exc
    base_dir = base_dir or default_base_dir(root)
    slug = requirement_slug(number)
    directory = orchestrate_pre_authoring.requirement_dir(base_dir, slug)
    directory.mkdir(parents=True, exist_ok=True)
    requirement_file = directory / "requirement.json"
    atomic_write_text(requirement_file, render_canonical_requirement_context(context))
    state = orchestrate_pre_authoring.init(
        root, requirement_id=slug, requirement_file=requirement_file,
        target_repository=context["target_repository"], base_dir=base_dir,
        refresh_requirement=True,
        business_context_file=requirement_file,
    )
    return {"requirement": f"{repository}#{number}", "slug": slug, "state": state}


def link_child(root: Path, *, requirement: str, child: str) -> dict[str, Any]:
    requirement_repository, requirement_number = issue_ref(requirement)
    child_repository, child_number = issue_ref(child)
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required; run gh auth login and retry")
    requirement_ref = f"{requirement_repository}#{requirement_number}"
    child_ref = f"{child_repository}#{child_number}"

    child_issue = fetch_issue(root, child_repository, child_number)
    child_body = str(child_issue.get("body") or "")
    other_parents = re.findall(r"^Requirement: (\S+/\S+#\d+)\s*$", child_body, re.MULTILINE)
    if other_parents and set(other_parents) != {requirement_ref}:
        raise RequirementIntakeError(f"{child_ref} already references a different Requirement: {other_parents}")

    parent_issue = fetch_issue(root, requirement_repository, requirement_number)
    parent_body = str(parent_issue.get("body") or "")
    parsed = parse_requirement_body(parent_body)
    if child_ref not in parsed["children"]:
        start = parent_body.find(CHILDREN_START)
        end = parent_body.find(CHILDREN_END)
        if start == -1 or end == -1 or end < start:
            raise RequirementIntakeError(f"{requirement_ref} is missing its children block; it is not a valid Requirement body")
        insertion_point = start + len(CHILDREN_START)
        block = parent_body[insertion_point:end]
        updated_block = block.rstrip("\n") + f"\n- [ ] {child_ref}\n"
        new_body = parent_body[:insertion_point] + updated_block + parent_body[end:]
        run(["gh", "issue", "edit", str(requirement_number), "--repo", requirement_repository, "--body", new_body], root, env)

    ensure_label(root, child_repository, CHILD_LABEL, env=env)
    back_reference = f"{BACK_REFERENCE_PREFIX}{requirement_ref}"
    if back_reference not in child_body:
        new_child_body = child_body.rstrip("\n") + f"\n\n{back_reference}\n"
        run(["gh", "issue", "edit", str(child_number), "--repo", child_repository, "--body", new_child_body, "--add-label", CHILD_LABEL], root, env)
    else:
        run(["gh", "issue", "edit", str(child_number), "--repo", child_repository, "--add-label", CHILD_LABEL], root, env)
    return {"requirement": requirement_ref, "child": child_ref}


def materialize_handoff(
    root: Path, *, requirement: str, handoff_file: Path, bundle_path: Path,
    base_dir: Path | None = None, confirm_distinct: bool = False,
) -> dict[str, Any]:
    """Create/reuse one managed child and prove bidirectional linkage.

    The authored bundle supplies semantic OpenSpec content. This adapter owns
    only validated handoff provenance and the create/link transaction; it never
    guesses a proposal or creates a second task ledger.
    """
    repository, number = issue_ref(requirement)
    requirement_ref = f"{repository}#{number}"
    parent = fetch_issue(root, repository, number)
    if REQUIREMENT_LABEL not in managed_task.issue_labels(parent):
        raise RequirementIntakeError(f"{requirement_ref} is not labeled {REQUIREMENT_LABEL}")
    slug = requirement_slug(number)
    directory = orchestrate_pre_authoring.requirement_dir(base_dir or default_base_dir(root), slug)
    report = orchestrate_pre_authoring.status(root, requirement_id=slug, base_dir=base_dir)
    if report.get("current_stage") != "complete":
        raise RequirementIntakeError(f"{requirement_ref} handoff is not ready: {report.get('blocker')}")
    resolved = handoff_file.resolve()
    if str(resolved) not in {str(Path(value).resolve()) for value in report.get("handoffs", {}).values()}:
        raise RequirementIntakeError("handoff is not one of the Requirement's current ready handoffs")
    try:
        envelope = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementIntakeError(f"handoff cannot be read: {exc}") from exc
    digest = envelope.get("digest")
    if digest is None and envelope.get("kind") == "direct-requirement-handoff":
        digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RequirementIntakeError("ready handoff has no valid digest")
    marker = f"<!-- requirement-handoff:v1:{requirement_ref}:{digest} -->"
    bundle = managed_task.load_authoring_bundle(str(bundle_path))
    config = managed_task.authoring_config(root)
    if managed_task.origin_repository(root) != report["target_repository"]:
        raise RequirementIntakeError("handoff targets a different repository from this checkout")
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required")
    issues = managed_task.run_json(
        ["gh", "api", "--paginate", f"repos/{config.repository}/issues?state=all&per_page=100"], root, env,
    )
    if not isinstance(issues, list):
        raise RequirementIntakeError("GitHub returned an invalid candidate list")
    candidates = [issue for issue in issues if isinstance(issue, dict) and "pull_request" not in issue
                  and marker in str(issue.get("body") or "")]
    if len(candidates) > 1:
        raise RequirementIntakeError(f"multiple children carry exact handoff identity {marker}")
    if candidates:
        child_number = managed_task.issue_number(candidates[0])
        child_ref = f"{config.repository}#{child_number}"
        try:
            package = managed_task.parse_package(managed_task.issue_bodies(root, config.repository, child_number), child_ref)
        except ManagedTaskError as exc:
            raise RequirementIntakeError(f"exact child {child_ref} has no valid managed package: {exc}") from exc
        if (package.change != bundle.change or package.target_repository != report["target_repository"]
                or package.artifacts != bundle.artifacts or package.contents != bundle.contents):
            raise RequirementIntakeError(f"exact child {child_ref} conflicts with the authored bundle")
    else:
        package, _, _ = managed_task.create_task(
            root, str(bundle_path), None, confirm_distinct, handoff_marker=marker,
        )
        child_ref = package.source_issue
    link_child(root, requirement=requirement_ref, child=child_ref)
    refreshed_parent = fetch_issue(root, repository, number)
    refreshed_child = fetch_issue(root, *issue_ref(child_ref))
    if child_ref not in parse_requirement_body(str(refreshed_parent.get("body") or ""))["children"]:
        raise RequirementIntakeError(f"linkage incomplete: {requirement_ref} does not list {child_ref}")
    if f"{BACK_REFERENCE_PREFIX}{requirement_ref}" not in str(refreshed_child.get("body") or ""):
        raise RequirementIntakeError(f"linkage incomplete: {child_ref} does not reference {requirement_ref}")
    return {"requirement": requirement_ref, "child": child_ref, "handoff_digest": digest}


def _child_observations(root: Path, children: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Read linked-child statuses and retain failures as projection evidence."""
    statuses: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    for child_ref in children:
        try:
            observation = managed_project_status.observe(root, source_issue=child_ref)
            current = observation.current_status if observation else None
        except managed_project_status.ManagedProjectStatusError as exc:
            current = None
            diagnostics.append({"source": "child", "child": child_ref, "reason": f"unreadable Project status: {exc}"})
        if current is None and not any(item.get("child") == child_ref for item in diagnostics):
            diagnostics.append({"source": "child", "child": child_ref, "reason": "missing Project status"})
        elif current is not None and current not in PROJECT_STATUSES:
            diagnostics.append({"source": "child", "child": child_ref, "reason": f"unsupported Project status: {current}"})
        statuses.append({"child": child_ref, "status": current})
    if len(set(children)) != len(children):
        diagnostics.append({"source": "children", "reason": "contradictory duplicate child references"})
    return statuses, diagnostics


def _orchestrator_observation(root: Path, number: int) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    """Return a fresh orchestrator report, failing closed when it cannot be read."""
    try:
        report = orchestrate_pre_authoring.status(root, requirement_id=requirement_slug(number))
    except orchestrate_pre_authoring.OrchestratorError as exc:
        return None, [{"source": "orchestrator", "reason": f"unreadable pre-authoring state: {exc}"}]
    if not isinstance(report, dict):
        return None, [{"source": "orchestrator", "reason": "invalid pre-authoring report"}]
    current_stage = report.get("current_stage")
    stages = report.get("stages")
    if current_stage not in ORCHESTRATOR_STAGES or not isinstance(stages, dict):
        return report, [{"source": "orchestrator", "reason": "contradictory pre-authoring report"}]
    if current_stage != "complete":
        current = stages.get(current_stage)
        if not isinstance(current, dict) or current.get("stage") != current_stage or not isinstance(current.get("state"), str):
            return report, [{"source": "orchestrator", "reason": "contradictory current pre-authoring stage"}]
    elif (
        report.get("blocker") is not None
        or not isinstance(report.get("handoffs"), dict)
        or not report["handoffs"]
    ):
        return report, [{"source": "orchestrator", "reason": "contradictory completed pre-authoring report"}]
    return report, []


def _pre_authoring_progress(report: dict[str, Any]) -> tuple[str, str]:
    """Map a validated orchestrator report to its human-facing display stage."""
    current_stage = report["current_stage"]
    if current_stage == "complete":
        return "ready", "current pre-authoring handoff is ready to materialize"
    current = report["stages"][current_stage]
    state = current["state"]
    if state in {"invalid", "stale", "scope-mismatch"}:
        return "unknown", f"pre-authoring {current_stage} source is {state}"
    if state == "needs-decision":
        return "human-decision", "a consequential design decision requires human resolution"
    if state == "needs-escalation":
        return "blocked", "pre-authoring evidence requires escalation"
    if current_stage in {"add", "intents", "handoff"}:
        return "design", f"pre-authoring {current_stage} is {state}"
    return "pre-authoring", f"pre-authoring {current_stage} is {state}"


def _progress_projection(
    root: Path, *, number: int, children: list[str], child_statuses: list[dict[str, Any]],
    child_diagnostics: list[dict[str, str]],
) -> dict[str, Any]:
    """Derive progress without writing any Requirement lifecycle state.

    Required source failures take precedence over optimistic display stages.
    Once a child exists, its Project lifecycle owns implementation/completion;
    machine-local pre-authoring state is no longer a required source.
    """
    report, orchestrator_diagnostics = (
        (None, []) if children else _orchestrator_observation(root, number)
    )
    diagnostics = [*child_diagnostics, *orchestrator_diagnostics]
    sources: dict[str, Any] = {"children": child_statuses, "orchestrator": report}
    if any(entry["status"] is None or entry["status"] not in PROJECT_STATUSES for entry in child_statuses):
        return {"stage": "unknown", "reason": "a linked child Project status is unreadable or unsupported", "diagnostics": diagnostics, "sources": sources}
    if child_diagnostics or orchestrator_diagnostics:
        return {"stage": "unknown", "reason": "a progress source is unreadable or contradictory", "diagnostics": diagnostics, "sources": sources}
    if any(entry["status"] == "Blocked" for entry in child_statuses):
        return {"stage": "blocked", "reason": "a linked child is blocked", "diagnostics": diagnostics, "sources": sources}
    if children:
        if all(entry["status"] == "Done" for entry in child_statuses):
            return {"stage": "done", "reason": "all linked children are done", "diagnostics": diagnostics, "sources": sources}
        return {"stage": "implementation", "reason": "linked child lifecycle is active", "diagnostics": diagnostics, "sources": sources}
    assert report is not None  # validated above; retained to make the mapping total.
    stage, reason = _pre_authoring_progress(report)
    return {"stage": stage, "reason": reason, "diagnostics": diagnostics, "sources": sources}


def aggregate(root: Path, *, requirement: str) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    issue = fetch_issue(root, repository, number)
    parsed = parse_requirement_body(str(issue.get("body") or ""))
    children = parsed["children"]
    statuses, child_diagnostics = _child_observations(root, children)
    values = [entry["status"] for entry in statuses]
    if not children:
        overall = "pre-authoring"
    elif any(value is None for value in values):
        overall = "unknown"
    elif all(value == "Done" for value in values):
        overall = "Done"
    elif any(value == "Blocked" for value in values):
        overall = "Blocked"
    else:
        overall = "In progress"
    return {
        "requirement": f"{repository}#{number}", "status": overall,
        "children": statuses,
        "progress": _progress_projection(
            root, number=number, children=children, child_statuses=statuses,
            child_diagnostics=child_diagnostics,
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Human-facing Business Requirement intake, pre-authoring linkage and aggregation.")
    sub = parser.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create", help="author a Requirement Issue with no OpenSpec artifact")
    create_parser.add_argument("--repository", required=True)
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--outcome-file", required=True, type=Path)
    create_parser.add_argument("--target-repository", required=True)
    create_parser.add_argument("--context-file", type=Path)
    create_parser.add_argument("--acceptance-file", type=Path)
    create_parser.add_argument("--exclusions-file", type=Path)

    start_parser = sub.add_parser("start", help="bridge a Requirement into orchestrate_pre_authoring.py init")
    start_parser.add_argument("--requirement", required=True)
    start_parser.add_argument("--base-dir", type=Path, default=None)

    link_parser = sub.add_parser("link-child", help="attach a materialized internal managed OpenSpec Issue to its parent Requirement")
    link_parser.add_argument("--requirement", required=True)
    link_parser.add_argument("--child", required=True)

    materialize_parser = sub.add_parser("materialize-handoff", help="create or exactly reuse and link a ready handoff's managed child")
    materialize_parser.add_argument("--requirement", required=True)
    materialize_parser.add_argument("--handoff", required=True, type=Path)
    materialize_parser.add_argument("--bundle", required=True, type=Path)
    materialize_parser.add_argument("--base-dir", type=Path, default=None)
    materialize_parser.add_argument("--confirm-distinct", action="store_true")

    aggregate_parser = sub.add_parser("aggregate", help="report a Requirement's derived progress from pre-authoring and linked children")
    aggregate_parser.add_argument("--requirement", required=True)

    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "create":
            payload = create_requirement(
                root, repository=args.repository, title=args.title,
                outcome=args.outcome_file.read_text(encoding="utf-8"),
                target_repository=args.target_repository,
                context=args.context_file.read_text(encoding="utf-8") if args.context_file else "",
                acceptance_evidence=args.acceptance_file.read_text(encoding="utf-8") if args.acceptance_file else "",
                exclusions=args.exclusions_file.read_text(encoding="utf-8") if args.exclusions_file else "",
            )
            print(f"Requirement created: {payload['repository']}#{payload['number']} ({payload['slug']})")
            return 0
        if args.command == "start":
            payload = start_pre_authoring(root, requirement=args.requirement, base_dir=args.base_dir)
            print(f"Pre-authoring initialized for {payload['requirement']} ({payload['slug']})")
            return 0
        if args.command == "link-child":
            payload = link_child(root, requirement=args.requirement, child=args.child)
            print(f"Linked {payload['child']} -> {payload['requirement']}")
            return 0
        if args.command == "materialize-handoff":
            payload = materialize_handoff(root, requirement=args.requirement, handoff_file=args.handoff,
                                          bundle_path=args.bundle, base_dir=args.base_dir,
                                          confirm_distinct=args.confirm_distinct)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "aggregate":
            payload = aggregate(root, requirement=args.requirement)
            import json
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        raise RequirementIntakeError(f"unsupported command: {args.command}")  # pragma: no cover - argparse enforces the choice set
    except (RequirementIntakeError, ManagedTaskError, orchestrate_pre_authoring.OrchestratorError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
