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


def parse_source_issue(reference: str) -> SourceIssue:
    match = SOURCE_ISSUE_RE.fullmatch(reference.strip())
    if not match:
        raise ManagedProjectStatusError(f"invalid managed source issue reference: {reference!r}")
    return SourceIssue(match.group(1), int(match.group(2)))


def _provenance_source(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedProjectStatusError(f"managed task provenance is unreadable: {path}") from exc
    source = payload.get("source_issue")
    if not isinstance(source, str):
        raise ManagedProjectStatusError(f"managed task provenance has no source_issue: {path}")
    return source


def discover_source_issue(root: Path, config: dict[str, Any] | None = None) -> SourceIssue | None:
    """Resolve only the managed package belonging to the current task checkout."""
    active = sorted((root / "openspec" / "changes").glob("*/.managed-task.json"))
    if len(active) > 1:
        raise ManagedProjectStatusError("multiple active managed OpenSpec packages make task identity ambiguous")
    if active:
        return parse_source_issue(_provenance_source(active[0]))

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
    sources = sorted({_provenance_source(path) for path in candidates})
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
    result = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, check=False)
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


def _project_state(
    root: Path,
    env: dict[str, str],
    source: SourceIssue,
    locator: ProjectLocator,
) -> tuple[str, str, str, dict[str, str], str, str | None]:
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

    if len(matching_items) != 1:
        raise ManagedProjectStatusError(
            f"managed issue {source.reference} maps to {len(matching_items)} items in Project {locator.owner}/{locator.number}; expected exactly one"
        )
    item = matching_items[0]
    value = item.get("fieldValueByName")
    current = value.get("name") if isinstance(value, dict) and isinstance(value.get("name"), str) else None
    return project_id, project_title, status_field_id, options, str(item.get("id", "")), current


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
    resume = sub.add_parser("resume", help="Restore In progress or In review from current PR evidence.")
    resume.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    try:
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
