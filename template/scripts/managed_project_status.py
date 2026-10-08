from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from _platform_common import github_cli_env, read_platform_config, run_git


EXPECTED_STATUSES = ("Backlog", "Ready", "In progress", "In review", "Blocked", "Done")
AUTOMATED_STATUSES = ("In progress", "In review", "Blocked", "Done")
SOURCE_ISSUE_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9]\d*)$")
OWNER_RE = re.compile(r"^[A-Za-z0-9-]+$")


class ManagedProjectStatusError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceIssue:
    repository: str
    number: int

    @property
    def reference(self) -> str:
        return f"{self.repository}#{self.number}"


@dataclass(frozen=True)
class ProjectLocator:
    owner: str
    number: int


@dataclass(frozen=True)
class ProjectObservation:
    source_issue: str
    project_owner: str
    project_number: int
    project_title: str
    current_status: str | None
    desired_status: str | None
    changed: bool


PROJECT_QUERY = """
query($login: String!, $number: Int!, $cursor: String) {
  user(login: $login) {
    projectV2(number: $number) {
      id
      title
      fields(first: 100) {
        nodes {
          __typename
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
      items(first: 100, after: $cursor) {
        nodes {
          id
          content {
            __typename
            ... on Issue { number repository { nameWithOwner } }
          }
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name optionId }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""".strip()


UPDATE_MUTATION = """
mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) {
  updateProjectV2ItemFieldValue(input: {
    projectId: $project,
    itemId: $item,
    fieldId: $field,
    value: { singleSelectOptionId: $option }
  }) { projectV2Item { id } }
}
""".strip()


ADD_ITEM_MUTATION = """
mutation($project: ID!, $content: ID!) {
  addProjectV2ItemById(input: { projectId: $project, contentId: $content }) { item { id } }
}
""".strip()


ISSUE_ID_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) { issue(number: $number) { id } }
}
""".strip()


ISSUE_ITEMS_QUERY = """
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issue(number: $number) {
      projectItems(first: 100, after: $cursor) {
        nodes {
          id
          isArchived
          project { id }
          content {
            __typename
            ... on Issue { number repository { nameWithOwner } }
          }
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name optionId }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
""".strip()


def parse_source_issue(reference: str) -> SourceIssue:
    match = SOURCE_ISSUE_RE.fullmatch(reference.strip())
    if not match:
        raise ManagedProjectStatusError(f"invalid managed source issue reference: {reference!r}")
    return SourceIssue(match.group(1), int(match.group(2)))


def _provenance_source(path: Path, root: Path | None = None) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedProjectStatusError(f"managed task provenance is unreadable: {path}") from exc
    source = payload.get("source_issue")
    if source is None and root is not None and "private_lineage_handle" in payload:
        import managed_task

        try:
            source = managed_task.source_issue_for_provenance(root, path.parent)
        except managed_task.ManagedTaskError as exc:
            raise ManagedProjectStatusError("private managed task provenance cannot be authorized") from exc
    if not isinstance(source, str):
        raise ManagedProjectStatusError(f"managed task provenance has no source_issue: {path}")
    return source


def discover_source_issue(root: Path, config: dict[str, Any] | None = None) -> SourceIssue | None:
    """Resolve only the managed package belonging to the current task checkout."""
    # This task-level identity remains after OpenSpec archival and lets the
    # delivery guard distinguish a broken managed task from an ordinary quick
    # task whose branch happens not to carry managed provenance.
    state = root / ".managed-task-state.json"
    if state.is_file():
        return parse_source_issue(_provenance_source(state))
    active = sorted((root / "openspec" / "changes").glob("*/.managed-task.json"))
    if len(active) > 1:
        raise ManagedProjectStatusError("multiple active managed OpenSpec packages make task identity ambiguous")
    if active:
        return parse_source_issue(_provenance_source(active[0], root))

    cfg = config or read_platform_config(root)
    main_branch = str(cfg.get("main_branch", "main"))
    changed = run_git(
        [
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"origin/{main_branch}...HEAD",
            "--",
            "openspec/changes",
        ],
        cwd=root,
        check=False,
    )
    if changed.returncode != 0:
        return None
    candidates = []
    for relative in changed.stdout.splitlines():
        if relative.endswith("/.managed-task.json"):
            path = root / relative
            if path.is_file():
                candidates.append(path)
    sources = sorted({_provenance_source(path, root) for path in candidates})
    if len(sources) > 1:
        raise ManagedProjectStatusError("current branch contains multiple managed task provenance records")
    return parse_source_issue(sources[0]) if sources else None


def project_locator(config: dict[str, Any], source: SourceIssue) -> ProjectLocator:
    backlog = config.get("development_backlog")
    if not isinstance(backlog, dict):
        raise ManagedProjectStatusError("managed Project status requires [development_backlog] configuration")
    if backlog.get("repository") != source.repository:
        raise ManagedProjectStatusError(
            f"managed source {source.repository} does not match development_backlog.repository={backlog.get('repository')!r}"
        )
    owner = backlog.get("project_owner")
    number = backlog.get("project_number")
    if not isinstance(owner, str) or not OWNER_RE.fullmatch(owner):
        raise ManagedProjectStatusError("development_backlog.project_owner must be a GitHub login")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ManagedProjectStatusError("development_backlog.project_number must be a positive integer")
    return ProjectLocator(owner, number)


def _graphql(root: Path, env: dict[str, str], query: str, variables: dict[str, object]) -> dict[str, Any]:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        if value is not None:
            # `gh api -F` performs magic type conversion. That is required for
            # GraphQL Int variables, but a numeric-looking single-select option
            # ID (for example "98236657") must remain a String.
            flag = "-F" if isinstance(value, int) and not isinstance(value, bool) else "-f"
            command += [flag, f"{key}={value}"]
    from _platform_common import run_github_with_retry

    # Queries are reads and retry classified transient failures; mutations run once.
    is_query = not query.lstrip().startswith("mutation")
    result = run_github_with_retry(command, cwd=root, env=env, read=is_query)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        if "scope" in detail.lower() or "resource not accessible" in detail.lower():
            detail += "; run `gh auth refresh -s project` (or provide a token with Projects read/write permission)"
        raise ManagedProjectStatusError(f"GitHub Project API request failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ManagedProjectStatusError("GitHub Project API returned unreadable JSON") from exc
    if payload.get("errors"):
        raise ManagedProjectStatusError(f"GitHub Project API returned errors: {payload['errors']}")
    return payload


def _project_items(
    root: Path,
    env: dict[str, str],
    source: SourceIssue,
    locator: ProjectLocator,
) -> tuple[str, str, str, dict[str, str], list[dict[str, Any]]]:
    """Return project identity, Status field/options and every item for the source issue."""
    cursor: str | None = None
    matching_items: list[dict[str, Any]] = []
    project_id = project_title = status_field_id = ""
    options: dict[str, str] = {}
    while True:
        payload = _graphql(
            root,
            env,
            PROJECT_QUERY,
            {"login": locator.owner, "number": locator.number, "cursor": cursor},
        )
        user = payload.get("data", {}).get("user")
        project = user.get("projectV2") if isinstance(user, dict) else None
        if not isinstance(project, dict):
            raise ManagedProjectStatusError(
                f"GitHub Project {locator.owner}/{locator.number} was not found or is not readable"
            )
        project_id = str(project.get("id", ""))
        project_title = str(project.get("title", ""))
        fields = project.get("fields", {}).get("nodes", [])
        status_fields = [field for field in fields if isinstance(field, dict) and field.get("name") == "Status"]
        if len(status_fields) != 1 or status_fields[0].get("__typename") != "ProjectV2SingleSelectField":
            raise ManagedProjectStatusError("configured Project must contain exactly one single-select Status field")
        status_field_id = str(status_fields[0].get("id", ""))
        options = {
            str(option.get("name")): str(option.get("id"))
            for option in status_fields[0].get("options", [])
            if isinstance(option, dict)
        }
        missing = [name for name in EXPECTED_STATUSES if name not in options]
        if missing:
            raise ManagedProjectStatusError("configured Project Status field is missing options: " + ", ".join(missing))
        items = project.get("items", {})
        for item in items.get("nodes", []):
            content = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content, dict) or content.get("__typename") != "Issue":
                continue
            repository = content.get("repository")
            if (
                isinstance(repository, dict)
                and repository.get("nameWithOwner") == source.repository
                and content.get("number") == source.number
            ):
                matching_items.append(item)
        page = items.get("pageInfo", {})
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise ManagedProjectStatusError("GitHub Project item pagination returned no continuation cursor")

    if not matching_items:
        # GitHub can expose a newly added item through Issue.projectItems before
        # it appears in ProjectV2.items. Resolve the exact source issue, then
        # retain the same project identity and uniqueness checks.
        owner, repo = source.repository.split("/", 1)
        issue_cursor: str | None = None
        while True:
            payload = _graphql(
                root,
                env,
                ISSUE_ITEMS_QUERY,
                {"owner": owner, "repo": repo, "number": source.number, "cursor": issue_cursor},
            )
            repository = payload.get("data", {}).get("repository")
            issue = repository.get("issue") if isinstance(repository, dict) else None
            if not isinstance(issue, dict):
                raise ManagedProjectStatusError(f"managed issue {source.reference} was not found or is not readable")
            items = issue.get("projectItems", {})
            for item in items.get("nodes", []):
                if not isinstance(item, dict) or item.get("isArchived"):
                    continue
                content = item.get("content")
                item_project = item.get("project")
                if (
                    isinstance(item_project, dict)
                    and item_project.get("id") == project_id
                    and isinstance(content, dict)
                    and content.get("__typename") == "Issue"
                    and content.get("number") == source.number
                    and isinstance(content.get("repository"), dict)
                    and content["repository"].get("nameWithOwner") == source.repository
                ):
                    matching_items.append(item)
            page = items.get("pageInfo", {})
            if not page.get("hasNextPage"):
                break
            issue_cursor = page.get("endCursor")
            if not isinstance(issue_cursor, str) or not issue_cursor:
                raise ManagedProjectStatusError("GitHub Issue project item pagination returned no continuation cursor")

    return project_id, project_title, status_field_id, options, matching_items


def _project_state(
    root: Path,
    env: dict[str, str],
    source: SourceIssue,
    locator: ProjectLocator,
) -> tuple[str, str, str, dict[str, str], str, str | None]:
    project_id, project_title, status_field_id, options, matching_items = _project_items(root, env, source, locator)
    if len(matching_items) != 1:
        raise ManagedProjectStatusError(
            f"managed issue {source.reference} maps to {len(matching_items)} items in Project {locator.owner}/{locator.number}; expected exactly one"
        )
    item = matching_items[0]
    value = item.get("fieldValueByName")
    current = value.get("name") if isinstance(value, dict) and isinstance(value.get("name"), str) else None
    return project_id, project_title, status_field_id, options, str(item.get("id", "")), current


@dataclass(frozen=True)
class MembershipReceipt:
    source_issue: str
    project_owner: str
    project_number: int
    item_id: str
    status: str
    added: bool
    status_initialized: bool


def _item_status(item: dict[str, Any]) -> str | None:
    value = item.get("fieldValueByName")
    return value.get("name") if isinstance(value, dict) and isinstance(value.get("name"), str) else None


def ensure_item(root: Path, *, source_issue: str, initial_status: str = "Backlog") -> MembershipReceipt:
    """Make the configured Project hold exactly one item for the issue, then read it back.

    GitHub's built-in auto-add is only a fast path: a missing item is added here
    through the same Project authorization (``addProjectV2ItemById`` returns the
    existing item when one already exists, so repeats and races cannot
    duplicate). An unset Status is initialized; an existing Status is never
    overwritten. The result is accepted only after a read-back shows exactly one
    item with a Status.
    """
    if initial_status not in EXPECTED_STATUSES:
        raise ManagedProjectStatusError(f"unsupported initial Project status: {initial_status!r}")
    config = read_platform_config(root)
    source = parse_source_issue(source_issue)
    locator = project_locator(config, source)
    env = github_cli_env(root)
    if env is None:
        raise ManagedProjectStatusError(
            "GitHub authentication is unavailable; run `gh auth login` and `gh auth refresh -s project`, or provide a Projects-capable token"
        )
    project_id, _, field_id, options, items = _project_items(root, env, source, locator)
    if len(items) > 1:
        raise ManagedProjectStatusError(
            f"managed issue {source.reference} maps to {len(items)} items in Project {locator.owner}/{locator.number}; expected exactly one"
        )
    if items and _item_status(items[0]) is not None:
        # Nothing to add or initialize; the single read above is the confirmation.
        return MembershipReceipt(
            source.reference, locator.owner, locator.number, str(items[0].get("id", "")),
            str(_item_status(items[0])), False, False,
        )
    added = False
    if not items:
        owner, repo = source.repository.split("/", 1)
        payload = _graphql(root, env, ISSUE_ID_QUERY, {"owner": owner, "repo": repo, "number": source.number})
        repository = payload.get("data", {}).get("repository")
        issue = repository.get("issue") if isinstance(repository, dict) else None
        content_id = issue.get("id") if isinstance(issue, dict) else None
        if not isinstance(content_id, str) or not content_id:
            raise ManagedProjectStatusError(f"issue {source.reference} was not found or is not readable")
        _graphql(root, env, ADD_ITEM_MUTATION, {"project": project_id, "content": content_id})
        added = True
    # Re-read immediately before writing so a Status claimed meanwhile is never
    # overwritten. GitHub offers no compare-and-set; this narrows the window.
    _, _, _, _, item_id, current = _project_state(root, env, source, locator)
    initialized = False
    if current is None:
        _graphql(
            root,
            env,
            UPDATE_MUTATION,
            {"project": project_id, "item": item_id, "field": field_id, "option": options[initial_status]},
        )
        initialized = True
    _, _, _, _, final_item, final_status = _project_state(root, env, source, locator)
    if final_status is None or (initialized and final_status != initial_status):
        raise ManagedProjectStatusError(
            f"read-back of {source.reference} in Project {locator.owner}/{locator.number} shows Status "
            f"{final_status!r}, expected {initial_status!r}"
        )
    return MembershipReceipt(
        source.reference, locator.owner, locator.number, final_item, final_status, added, initialized,
    )


def observe(
    root: Path,
    *,
    source_issue: str | None = None,
    desired_status: str | None = None,
) -> ProjectObservation | None:
    config = read_platform_config(root)
    source = parse_source_issue(source_issue) if source_issue else discover_source_issue(root, config)
    if source is None:
        return None
    locator = project_locator(config, source)
    env = github_cli_env(root)
    if env is None:
        raise ManagedProjectStatusError(
            "GitHub authentication is unavailable; run `gh auth login` and `gh auth refresh -s project`, or provide a Projects-capable token"
        )
    _, title, _, _, _, current = _project_state(root, env, source, locator)
    return ProjectObservation(source.reference, locator.owner, locator.number, title, current, desired_status, False)


def reconcile(
    root: Path,
    desired_status: str,
    *,
    source_issue: str | None = None,
) -> ProjectObservation | None:
    if desired_status not in AUTOMATED_STATUSES:
        raise ManagedProjectStatusError(f"unsupported automated Project status: {desired_status!r}")
    config = read_platform_config(root)
    source = parse_source_issue(source_issue) if source_issue else discover_source_issue(root, config)
    if source is None:
        return None
    locator = project_locator(config, source)
    env = github_cli_env(root)
    if env is None:
        raise ManagedProjectStatusError(
            "GitHub authentication is unavailable; run `gh auth login` and `gh auth refresh -s project`, or provide a Projects-capable token"
        )
    project_id, title, field_id, options, item_id, current = _project_state(root, env, source, locator)
    if current == desired_status:
        return ProjectObservation(source.reference, locator.owner, locator.number, title, current, desired_status, False)
    _graphql(
        root,
        env,
        UPDATE_MUTATION,
        {"project": project_id, "item": item_id, "field": field_id, "option": options[desired_status]},
    )
    return ProjectObservation(source.reference, locator.owner, locator.number, title, desired_status, desired_status, True)


def block_for_scope_conflict(root: Path, reason: str) -> ProjectObservation | None:
    """Best-effort: reflect a genuine scope-coordination WAIT as Blocked.

    Silently a no-op for a quick/non-managed task (no discoverable source
    issue) or when GitHub Project access is unavailable -- the actual block
    is the caller's raised error, not this reflection.
    """
    try:
        observation = reconcile(root, "Blocked")
    except ManagedProjectStatusError:
        return None
    if observation is not None:
        action = "updated" if observation.changed else "already current"
        print(f"Managed Project status {action}: {observation.source_issue} -> Blocked ({reason})")
    return observation


def resume_from_scope_conflict(root: Path) -> ProjectObservation | None:
    """Best-effort: return a scope-coordination Blocked to its truthful state."""
    try:
        current = observe(root)
        if current is None or current.current_status != "Blocked":
            return None
        observation = reconcile(root, derive_resume_status(root), source_issue=current.source_issue)
    except ManagedProjectStatusError:
        return None
    if observation is not None:
        action = "updated" if observation.changed else "already current"
        print(f"Managed Project status {action}: {observation.source_issue} -> {observation.current_status}")
    return observation


def derive_resume_status(root: Path) -> str:
    """Return the truthful nonterminal state for a resumable managed task."""
    import publication_state

    config = read_platform_config(root)
    main_branch = str(config.get("main_branch", "main"))
    branch = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
    head = run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    env = github_cli_env(root)
    if env is None:
        raise ManagedProjectStatusError("GitHub authentication is unavailable while deriving managed task state")
    lookup = publication_state.find_exact_head_pr(root, env, branch, main_branch, head)
    if not lookup.available:
        raise ManagedProjectStatusError("GitHub PR state is unavailable while deriving managed task state")
    if lookup.exact_merged is not None:
        raise ManagedProjectStatusError("the exact task PR is merged; rerun finish_task so local and Project terminal reconciliation stay ordered")
    return "In review" if lookup.exact_open is not None else "In progress"


def _print_observation(observation: ProjectObservation | None, *, as_json: bool) -> None:
    if observation is None:
        payload = {"managed": False, "detail": "current task has no managed Development Backlog source"}
    else:
        payload = {"managed": True, **asdict(observation)}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    if not payload["managed"]:
        print(payload["detail"])
    elif observation is not None:
        action = "updated" if observation.changed else "already current"
        print(f"Managed Project status {action}: {observation.source_issue} -> {observation.current_status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe or reconcile the Development Backlog status for this managed task.")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Read current Project status without mutation.")
    status.add_argument("--json", action="store_true")
    set_status = sub.add_parser("set", help="Set one supported lifecycle status idempotently.")
    set_status.add_argument("status", choices=AUTOMATED_STATUSES)
    set_status.add_argument("--json", action="store_true")
    block = sub.add_parser("block", help="Record a genuine external/human blocker.")
    block.add_argument("--reason", required=True)
    block.add_argument("--json", action="store_true")
    ensure = sub.add_parser("ensure", help="Ensure exactly one Project item for a source issue (idempotent).")
    ensure.add_argument("--issue", required=True)
    ensure.add_argument("--json", action="store_true")
    resume = sub.add_parser("resume", help="Restore In progress or In review from current PR evidence.")
    resume.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
        if args.command == "ensure":
            receipt = ensure_item(root, source_issue=args.issue)
            if args.json:
                print(json.dumps(asdict(receipt), ensure_ascii=False, sort_keys=True))
            else:
                print(f"Project membership confirmed: {receipt.source_issue} -> {receipt.status} (added={receipt.added})")
            return 0
        if args.command == "status":
            observation = observe(root)
        elif args.command == "block":
            observation = reconcile(root, "Blocked")
            if observation is not None and not args.json:
                print(f"Blocker: {args.reason}")
        elif args.command == "resume":
            observation = reconcile(root, derive_resume_status(root))
        else:
            observation = reconcile(root, args.status)
    except ManagedProjectStatusError as exc:
        raise SystemExit(f"Managed Project status reconciliation blocked: {exc}") from exc
    _print_observation(observation, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
