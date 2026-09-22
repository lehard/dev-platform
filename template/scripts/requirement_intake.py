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
own. It only asks the existing ``managed_project_status.observe()`` for each
linked child's real Development Backlog Project status and derives one label
from that, so a Requirement's progress can never diverge from the lifecycle
that already owns it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import managed_project_status
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
    child_issue = fetch_issue(root, child_repository, child_number)
    child_body = str(child_issue.get("body") or "")
    back_reference = f"{BACK_REFERENCE_PREFIX}{requirement_ref}"
    if back_reference not in child_body:
        new_child_body = child_body.rstrip("\n") + f"\n\n{back_reference}\n"
        run(["gh", "issue", "edit", str(child_number), "--repo", child_repository, "--body", new_child_body, "--add-label", CHILD_LABEL], root, env)
    else:
        run(["gh", "issue", "edit", str(child_number), "--repo", child_repository, "--add-label", CHILD_LABEL], root, env)
    return {"requirement": requirement_ref, "child": child_ref}


def aggregate(root: Path, *, requirement: str) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    issue = fetch_issue(root, repository, number)
    parsed = parse_requirement_body(str(issue.get("body") or ""))
    children = parsed["children"]
    if not children:
        return {"requirement": f"{repository}#{number}", "status": "pre-authoring", "children": []}
    statuses: list[dict[str, Any]] = []
    for child_ref in children:
        try:
            observation = managed_project_status.observe(root, source_issue=child_ref)
            current = observation.current_status if observation else None
        except managed_project_status.ManagedProjectStatusError:
            current = None
        statuses.append({"child": child_ref, "status": current})
    values = [entry["status"] for entry in statuses]
    if any(value is None for value in values):
        overall = "unknown"
    elif all(value == "Done" for value in values):
        overall = "Done"
    elif any(value == "Blocked" for value in values):
        overall = "Blocked"
    else:
        overall = "In progress"
    return {"requirement": f"{repository}#{number}", "status": overall, "children": statuses}


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

    aggregate_parser = sub.add_parser("aggregate", help="report a Requirement's status derived from its linked children")
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
