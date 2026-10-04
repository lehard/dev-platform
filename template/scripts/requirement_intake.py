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
import managed_work_identity as work_identity
import orchestrate_pre_authoring
import requirement_target_lifecycle
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
    section_source = re.sub(r"^Work identity: .*\n?", "", section_source, flags=re.MULTILINE)
    section_source = work_identity.RESERVATION.sub("", section_source)
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


def requirement_label_problems(
    labels: set[str], project_label: str, priority_label: str,
) -> tuple[list[str], list[str]]:
    """Pure label-set check shared by the local read-back and the connected reference path.

    ``labels`` is assumed lowercased (as ``managed_task.issue_labels`` returns
    it). Conflicting is any ``project:*``/``priority:*`` label present that is
    not exactly the expected one; missing is any of ``type:requirement``,
    ``project_label``, ``priority_label`` absent from ``labels``
    (case-insensitive).
    """
    expected_project = project_label.lower()
    expected_priority = priority_label.lower()
    conflicting = sorted(
        label for label in labels
        if (label.startswith("project:") and label != expected_project)
        or (label.startswith("priority:") and label != expected_priority)
    )
    expected_labels = (REQUIREMENT_LABEL, project_label, priority_label)
    missing = [label for label in expected_labels if label.lower() not in labels]
    return conflicting, missing


def _reconcile_requirement_labels(
    root: Path, *, repository: str, number: int, config: managed_task.AuthoringConfig, priority: str,
) -> None:
    """Verify a created Requirement's labels, completing only missing ones.

    Mirrors ``managed_task.repair_authoring_labels``: a conflicting
    ``project:*``/``priority:*`` label fails closed by exact Issue reference,
    while a merely missing expected label (including ``type:requirement``) is
    completed once and re-verified. Success is never reported without this
    read-back proving the exact expected label set.
    """
    ref = f"{repository}#{number}"
    project_label = config.project_label
    priority_label_value = managed_task.priority_label(priority)

    def _check(labels: set[str]) -> list[str]:
        conflicting, missing = requirement_label_problems(labels, project_label, priority_label_value)
        if conflicting:
            found = ", ".join(sorted(labels)) or "none"
            raise RequirementIntakeError(
                f"{ref} has conflicting project/priority labels "
                f"(expected {project_label!r} and {priority_label_value!r}; found {found})"
            )
        return missing

    issue = fetch_issue(root, repository, number)
    labels = managed_task.issue_labels(issue)
    missing = _check(labels)
    if missing:
        env = github_cli_env(root)
        if env is None:
            raise RequirementIntakeError("GitHub CLI authentication is required; run gh auth login and retry")
        endpoint = f"repos/{repository}/issues/{number}/labels"
        for label in missing:
            run(["gh", "api", "--method", "POST", endpoint, "-f", f"labels[]={label}"], root, env)
        issue = fetch_issue(root, repository, number)
        labels = managed_task.issue_labels(issue)
        missing = _check(labels)
    conflicting, missing = requirement_label_problems(labels, project_label, priority_label_value)
    if missing or conflicting:
        found = ", ".join(sorted(labels)) or "none"
        raise RequirementIntakeError(
            f"{ref} does not carry the expected Requirement labels "
            f"(expected {REQUIREMENT_LABEL!r}, {project_label!r} and {priority_label_value!r}; found {found})"
        )


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
    priority: str | None = None,
) -> dict[str, Any]:
    if not title.strip():
        raise RequirementIntakeError("title must be a non-empty string")
    config = managed_task.authoring_config(root)
    repository = repo(repository)
    if repository != config.repository:
        raise RequirementIntakeError(
            f"repository {repository!r} does not match the configured development_backlog.repository {config.repository!r}"
        )
    normalized_target = repo(target_repository)
    try:
        requirement_target_lifecycle.require_local_target_support(root, target_repository=normalized_target)
    except requirement_target_lifecycle.RequirementTargetLifecycleError as exc:
        raise RequirementIntakeError(str(exc)) from exc
    origin = managed_task.origin_repository(root)
    if normalized_target != origin:
        raise RequirementIntakeError(
            f"target repository {normalized_target!r} is not this checkout's origin {origin!r}; "
            "its project label is not configured here -- create this Requirement from the target repository's own checkout"
        )
    effective_priority = priority or config.default_priority
    priority_label_value = managed_task.priority_label(effective_priority)
    managed_task.validate_backlog_labels(root, config, effective_priority)
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required; run gh auth login and retry")
    ensure_label(root, repository, REQUIREMENT_LABEL, env=env)
    body = render_requirement_body(
        outcome=outcome, target_repository=target_repository, context=context,
        acceptance_evidence=acceptance_evidence, exclusions=exclusions,
    )
    result = run(
        [
            "gh", "issue", "create", "--repo", repository, "--title", title.strip(), "--body", body,
            "--label", REQUIREMENT_LABEL, "--label", config.project_label, "--label", priority_label_value,
        ],
        root, env,
    )
    created_repository, number = issue_ref(result.stdout.strip())
    _reconcile_requirement_labels(root, repository=created_repository, number=number, config=config, priority=effective_priority)
    reconcile_requirement_identity(
        root, f"{created_repository}#{number}", fetch_issue(root, created_repository, number),
    )
    return {
        "repository": created_repository, "number": number, "slug": requirement_slug(number),
        "project_label": config.project_label, "priority": priority_label_value,
    }


def ensure_label(root: Path, repository: str, name: str, *, env: dict[str, str], description: str = "") -> None:
    run(["gh", "label", "create", name, "--repo", repository, "--force", "--description", description], root, env)


def routing_parameters(root: Path) -> dict[str, str]:
    """Render the ChatGPT Project routing parameters from this checkout's own configuration.

    These are the exact values an operator-managed target (one that
    intentionally keeps ``.dev-platform.toml`` untracked, so connected
    ChatGPT cannot read it) declares as its Project parameters. They are
    always derived from the same ``[development_backlog]`` configuration
    ``create`` uses -- never hand-authored, never a second default.
    """
    config = managed_task.authoring_config(root)
    origin = managed_task.origin_repository(root)
    return {
        "BACKLOG_REPOSITORY": config.repository,
        "TARGET_REPOSITORY": origin,
        "PROJECT_LABEL": config.project_label,
        "DEFAULT_PRIORITY": config.default_priority,
    }


def resolve_connected_routing(
    *,
    target_repository: str,
    backlog_repository: str,
    committed_config: dict[str, Any] | None,
    project_parameters: dict[str, str],
    priority: str | None = None,
    lifecycle_evidence: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Reference model of the connected ChatGPT adapter's Requirement routing rule.

    This is the pure resolver the connected adapter must behave equivalently
    to. Routing resolution is ordered:

    1. When ``committed_config`` (the target's committed
       ``[development_backlog]`` table, read from its default branch) is
       present, it is authoritative: its ``repository`` must equal
       ``backlog_repository``, its ``project_label`` must be a
       ``project:<slug>`` label, and its ``default_priority`` must be one of
       P0..P3. A declared ``PROJECT_LABEL``/``DEFAULT_PRIORITY`` Project
       parameter that disagrees with it is a conflict, and a declared
       ``BACKLOG_REPOSITORY`` that disagrees with it is also a conflict.
    2. Otherwise (an operator-managed target that intentionally does not
       track that configuration) the declared Project parameters --
       ``BACKLOG_REPOSITORY``, ``TARGET_REPOSITORY``, ``PROJECT_LABEL``,
       ``DEFAULT_PRIORITY`` -- must all be present and valid, and
       ``BACKLOG_REPOSITORY``/``TARGET_REPOSITORY`` must equal the intended
       backlog/target.

    Anything missing, invalid, or disagreeing raises ``RequirementIntakeError``
    naming the routing blocker; nothing is created without resolved routing.
    """
    try:
        requirement_target_lifecycle.require_connected_target_support(
            committed_config=committed_config, lifecycle_evidence=lifecycle_evidence,
        )
    except requirement_target_lifecycle.RequirementTargetLifecycleError as exc:
        raise RequirementIntakeError(str(exc)) from exc

    def _normalize_repo(value: Any) -> str | None:
        """Return the normalized owner/name form, or None when ``value`` is
        not a valid repository string. Never raises: an invalid owner/name
        string in a routing parameter is a routing blocker
        (``RequirementIntakeError``), not the lower-level ``ManagedTaskError``
        that ``managed_task.repo`` raises for CLI-args use."""
        if not isinstance(value, str):
            return None
        try:
            return repo(value)
        except ManagedTaskError:
            return None

    normalized_target = _normalize_repo(target_repository)
    if normalized_target is None:
        raise RequirementIntakeError(f"target_repository must be owner/name, got {target_repository!r}")
    normalized_backlog = _normalize_repo(backlog_repository)
    if normalized_backlog is None:
        raise RequirementIntakeError(f"backlog_repository must be owner/name, got {backlog_repository!r}")

    if committed_config is not None:
        committed_repository = committed_config.get("repository")
        committed_project_label = committed_config.get("project_label")
        committed_default_priority = committed_config.get("default_priority")
        normalized_committed_repository = _normalize_repo(committed_repository)
        if normalized_committed_repository is None:
            raise RequirementIntakeError("committed development_backlog.repository must be owner/name")
        if normalized_committed_repository != normalized_backlog:
            raise RequirementIntakeError(
                f"committed development_backlog.repository {committed_repository!r} does not match "
                f"BACKLOG_REPOSITORY {backlog_repository!r}"
            )
        if not isinstance(committed_project_label, str) or not re.fullmatch(r"project:[A-Za-z0-9_.-]+", committed_project_label):
            raise RequirementIntakeError("committed development_backlog.project_label must be a project:<slug> label")
        if not isinstance(committed_default_priority, str) or not managed_task.PRIORITY_RE.fullmatch(committed_default_priority):
            raise RequirementIntakeError("committed development_backlog.default_priority must be one of P0, P1, P2 or P3")

        declared_backlog = project_parameters.get("BACKLOG_REPOSITORY")
        if declared_backlog is not None and _normalize_repo(declared_backlog) != normalized_backlog:
            raise RequirementIntakeError(
                f"declared BACKLOG_REPOSITORY {declared_backlog!r} conflicts with committed "
                f"development_backlog.repository {committed_repository!r}"
            )
        declared_project_label = project_parameters.get("PROJECT_LABEL")
        if declared_project_label is not None and declared_project_label.lower() != committed_project_label.lower():
            raise RequirementIntakeError(
                f"declared PROJECT_LABEL {declared_project_label!r} conflicts with committed "
                f"development_backlog.project_label {committed_project_label!r}"
            )
        declared_default_priority = project_parameters.get("DEFAULT_PRIORITY")
        if declared_default_priority is not None and declared_default_priority.upper() != committed_default_priority.upper():
            raise RequirementIntakeError(
                f"declared DEFAULT_PRIORITY {declared_default_priority!r} conflicts with committed "
                f"development_backlog.default_priority {committed_default_priority!r}"
            )
        project_label = committed_project_label
        default_priority = committed_default_priority
    else:
        declared_backlog = project_parameters.get("BACKLOG_REPOSITORY")
        declared_target = project_parameters.get("TARGET_REPOSITORY")
        declared_project_label = project_parameters.get("PROJECT_LABEL")
        declared_default_priority = project_parameters.get("DEFAULT_PRIORITY")
        problems: list[str] = []
        if _normalize_repo(declared_backlog) != normalized_backlog:
            problems.append(f"BACKLOG_REPOSITORY must equal {backlog_repository!r}")
        if _normalize_repo(declared_target) != normalized_target:
            problems.append(f"TARGET_REPOSITORY must equal {target_repository!r}")
        if not isinstance(declared_project_label, str) or not re.fullmatch(r"project:[A-Za-z0-9_.-]+", declared_project_label):
            problems.append("PROJECT_LABEL must be a project:<slug> label")
        if not isinstance(declared_default_priority, str) or not managed_task.PRIORITY_RE.fullmatch(declared_default_priority):
            problems.append("DEFAULT_PRIORITY must be one of P0, P1, P2 or P3")
        if problems:
            raise RequirementIntakeError(
                "connected Requirement routing cannot be resolved: no committed development_backlog "
                "configuration, and the declared Project parameters are incomplete or invalid (" + "; ".join(problems) + ")"
            )
        project_label = declared_project_label
        default_priority = declared_default_priority

    effective_priority = priority or default_priority
    try:
        priority_label_value = managed_task.priority_label(effective_priority)
    except ManagedTaskError as exc:
        raise RequirementIntakeError(str(exc)) from exc
    return {"project_label": project_label, "priority": priority_label_value}


def verify_connected_requirement(issue: dict[str, Any], *, routing: dict[str, str]) -> None:
    """Pure read-back check that a connected Requirement Issue carries exactly the resolved routing.

    Mirrors the terminal check in ``_reconcile_requirement_labels`` but
    performs no mutation: the connected adapter's own read-back after
    fixation must already find the resolved ``project:*``/``priority:*``
    labels applied, on an open Issue that is not a pull request.
    """
    if issue.get("pull_request"):
        raise RequirementIntakeError("connected Requirement read-back target is a pull request, not an Issue")
    if issue.get("state") != "open":
        raise RequirementIntakeError("connected Requirement read-back target is not open")
    labels = managed_task.issue_labels(issue)
    conflicting, missing = requirement_label_problems(labels, routing["project_label"], routing["priority"])
    if conflicting or missing:
        found = ", ".join(sorted(labels)) or "none"
        raise RequirementIntakeError(
            "connected Requirement read-back does not carry the expected labels "
            f"(expected {REQUIREMENT_LABEL!r}, {routing['project_label']!r} and {routing['priority']!r}; found {found})"
        )


def default_base_dir(root: Path) -> Path:
    return orchestrate_pre_authoring.default_base_dir(root)


def reconcile_requirement_identity(root: Path, requirement: str, issue: dict[str, Any]) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    requirement = f"{repository}#{number}"
    try:
        with work_identity.allocation_lock(requirement):
            return _reconcile_requirement_identity(root, requirement, issue)
    except work_identity.IdentityError as exc:
        raise RequirementIntakeError(str(exc)) from exc


def _reconcile_requirement_identity(root: Path, requirement: str, issue: dict[str, Any]) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    body = str(issue.get("body") or "")
    try:
        expected = work_identity.with_identity(body, work_identity.parent_identity(requirement))
    except work_identity.IdentityError as exc:
        raise RequirementIntakeError(str(exc)) from exc
    if expected == body:
        return issue
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required for Requirement identity recovery")
    if str(fetch_issue(root, repository, number).get("body") or "") != body:
        raise RequirementIntakeError("Requirement changed during identity recovery; inspect and retry")
    run(["gh", "issue", "edit", str(number), "--repo", repository, "--body", expected], root, env)
    observed = fetch_issue(root, repository, number)
    if str(observed.get("body") or "") != expected:
        raise RequirementIntakeError("Requirement identity recovery readback failed; inspect and retry")
    return observed


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
    try:
        requirement_target_lifecycle.require_local_target_support(root, target_repository=context["target_repository"])
    except requirement_target_lifecycle.RequirementTargetLifecycleError as exc:
        raise RequirementIntakeError(str(exc)) from exc
    reconcile_requirement_identity(root, f"{repository}#{number}", issue)
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


def _identity_siblings(root: Path, requirement: str, env: dict[str, str]) -> dict[str, str]:
    repository, _ = issue_ref(requirement)
    issues = managed_task.run_json(
        ["gh", "api", "--paginate", "--slurp", f"repos/{repository}/issues?state=all&per_page=100"], root, env,
    )
    if not isinstance(issues, list) or any(not isinstance(page, list) for page in issues):
        raise RequirementIntakeError("cannot read sibling Issue pages")
    issues = [issue for page in issues for issue in page]
    if any(not isinstance(issue, dict) for issue in issues):
        raise RequirementIntakeError("cannot read sibling Issue claims")
    result = {}
    for issue in issues:
        body = str(issue.get("body") or "")
        if "pull_request" not in issue and re.search(
            rf"^Requirement: {re.escape(requirement)}\s*$", body, re.MULTILINE,
        ):
            result[f"{repository}#{managed_task.issue_number(issue)}"] = body
    return result


def link_child(root: Path, *, requirement: str, child: str) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    requirement = f"{repository}#{number}"
    try:
        with work_identity.allocation_lock(requirement):
            return _link_child_identity(root, requirement=requirement, child=child)
    except work_identity.IdentityError as exc:
        raise RequirementIntakeError(str(exc)) from exc


def _link_child_identity(root: Path, *, requirement: str, child: str) -> dict[str, Any]:
    repository, number = issue_ref(requirement)
    child_repository, child_number = issue_ref(child)
    requirement = f"{repository}#{number}"
    child = f"{child_repository}#{child_number}"
    if child_repository != repository or child == requirement:
        raise RequirementIntakeError("child must be a distinct Issue in the Requirement Backlog repository")
    env = github_cli_env(root)
    if env is None:
        raise RequirementIntakeError("GitHub CLI authentication is required")
    parent_body = str(fetch_issue(root, repository, number).get("body") or "")
    child_body = str(fetch_issue(root, child_repository, child_number).get("body") or "")
    parsed = parse_requirement_body(parent_body)
    siblings = _identity_siblings(root, requirement, env)
    # Read legacy links too; deleted checklist entries remain in reservations/claims.
    if len(parsed["children"]) != len(set(parsed["children"])):
        raise RequirementIntakeError("duplicate child checklist links")
    reserved_refs = [ref for ref, _ in work_identity.RESERVATION.findall(parent_body)]
    for ref in set(parsed["children"] + reserved_refs):
        if issue_ref(ref)[0] != repository:
            raise RequirementIntakeError("child reservation points outside the Requirement Backlog")
        siblings[ref] = str(fetch_issue(root, *issue_ref(ref)).get("body") or "")
    siblings[child] = child_body
    allocated = work_identity.assignments(parent_body, requirement, siblings)
    ordinal = allocated.get(child, max(allocated.values(), default=0) + 1)
    identity = f"{work_identity.parent_identity(requirement)}/T{ordinal}"
    start, end = parent_body.find(CHILDREN_START), parent_body.find(CHILDREN_END)
    if start < 0 or end < start or parent_body.count(CHILDREN_START) != 1 or parent_body.count(CHILDREN_END) != 1:
        raise RequirementIntakeError("Requirement is missing a unique valid children block")
    new_child = work_identity.with_identity(child_body, identity)
    back_reference = f"Requirement: {requirement}"
    if not re.search(rf"^{re.escape(back_reference)}\s*$", new_child, re.MULTILINE):
        new_child = new_child.rstrip("\n") + f"\n\n{back_reference}\n"
    if str(fetch_issue(root, repository, child_number).get("body") or "") != child_body:
        raise RequirementIntakeError("child changed during allocation; retry after inspecting its Issue")
    ensure_label(root, repository, CHILD_LABEL, env=env)
    args = ["gh", "issue", "edit", str(child_number), "--repo", repository, "--add-label", CHILD_LABEL]
    if new_child != child_body:
        args += ["--body", new_child]
    run(args, root, env)
    # Claim-first makes interrupted allocations recoverable from the child.
    allocated[child] = ordinal
    new_parent = parent_body
    if child not in parsed["children"]:
        new_parent = parent_body[:end] + f"- [ ] {child}\n" + parent_body[end:]
    new_parent = work_identity.with_identity(new_parent, work_identity.parent_identity(requirement))
    for ref, value in allocated.items():
        marker = f"<!-- br-child:{ref}:{value} -->"
        if marker not in new_parent:
            new_parent = new_parent.rstrip("\n") + f"\n{marker}\n"
    if str(fetch_issue(root, repository, number).get("body") or "") != parent_body:
        raise RequirementIntakeError("Requirement changed during allocation; retry to reconcile child claim")
    if new_parent != parent_body:
        run(["gh", "issue", "edit", str(number), "--repo", repository, "--body", new_parent], root, env)
    final_parent = str(fetch_issue(root, repository, number).get("body") or "")
    final_child = str(fetch_issue(root, repository, child_number).get("body") or "")
    final_siblings = _identity_siblings(root, requirement, env)
    final_refs = set(allocated) | set(parse_requirement_body(final_parent)["children"])
    final_refs.update(ref for ref, _ in work_identity.RESERVATION.findall(final_parent))
    for ref in final_refs:
        if issue_ref(ref)[0] != repository:
            raise RequirementIntakeError("child reservation points outside the Requirement Backlog")
        final_siblings[ref] = str(fetch_issue(root, *issue_ref(ref)).get("body") or "")
    final_child = final_siblings[child]
    observed = work_identity.assignments(final_parent, requirement, final_siblings)
    for ref, value in allocated.items():
        retained = final_siblings.get(ref, "")
        parents = re.findall(r"^Requirement: (\S+)\s*$", retained, re.MULTILINE)
        if (work_identity.identity_in(retained) != f"{work_identity.parent_identity(requirement)}/T{value}"
                or parents != [requirement]):
            raise RequirementIntakeError("allocated child claim missing or changed during readback; inspect Issue records")
    reservations = dict((ref, int(value)) for ref, value in work_identity.RESERVATION.findall(final_parent))
    if (final_parent != new_parent or final_child != new_child
            or work_identity.identity_in(final_parent) != work_identity.parent_identity(requirement)
            or not set(parsed["children"]).issubset(parse_requirement_body(final_parent)["children"])
            or any(reservations.get(ref) != value for ref, value in observed.items())
            or any(observed.get(ref) != value for ref, value in allocated.items())
            or child not in parse_requirement_body(final_parent)["children"]
            or work_identity.identity_in(final_child) != identity
            or not re.search(rf"^{re.escape(back_reference)}\s*$", final_child, re.MULTILINE)):
        raise RequirementIntakeError("identity readback incomplete or concurrent update lost; retry after inspecting Issue claims")
    return {"requirement": requirement, "child": child, "work_identity": identity}


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
    try:
        context = canonical_requirement_context(parse_requirement_body(str(parent.get("body") or "")))
        requirement_target_lifecycle.require_local_target_support(root, target_repository=context["target_repository"])
    except requirement_target_lifecycle.RequirementTargetLifecycleError as exc:
        raise RequirementIntakeError(str(exc)) from exc
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
    if not re.search(rf"^{re.escape(BACK_REFERENCE_PREFIX + requirement_ref)}\s*$", str(refreshed_child.get("body") or ""), re.MULTILINE):
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
    create_parser.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], default=None,
                                help="defaults to the configured development_backlog.default_priority")

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

    sub.add_parser(
        "routing-parameters",
        help="render the ChatGPT Project parameters (BACKLOG_REPOSITORY, TARGET_REPOSITORY, "
             "PROJECT_LABEL, DEFAULT_PRIORITY) from the existing [development_backlog] configuration",
    )

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
                priority=args.priority,
            )
            print(
                f"Requirement created: {payload['repository']}#{payload['number']} ({payload['slug']}) "
                f"[{payload['project_label']}, {payload['priority']}]"
            )
            return 0
        if args.command == "start":
            payload = start_pre_authoring(root, requirement=args.requirement, base_dir=args.base_dir)
            print(f"Pre-authoring initialized for {payload['requirement']} ({payload['slug']})")
            import requirement_board  # lazy: requirement_board imports this module

            try:
                requirement_board.claim_started(root, requirement=payload["requirement"])
            except requirement_board.RequirementBoardError as exc:
                raise RequirementIntakeError(str(exc)) from exc
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
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "routing-parameters":
            payload = routing_parameters(root)
            for name in ("BACKLOG_REPOSITORY", "TARGET_REPOSITORY", "PROJECT_LABEL", "DEFAULT_PRIORITY"):
                print(f"{name}={payload[name]}")
            return 0
        raise RequirementIntakeError(f"unsupported command: {args.command}")  # pragma: no cover - argparse enforces the choice set
    except (RequirementIntakeError, ManagedTaskError, orchestrate_pre_authoring.OrchestratorError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
