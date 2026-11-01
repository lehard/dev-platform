"""Map a public opaque lineage handle to its exact private Backlog Issue.

The mapping is a comment on that same private Issue. No public file or second
storage service contains the reverse lookup.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
from pathlib import Path

from _platform_common import read_platform_config


HANDLE_RE = re.compile(r"^pln_[0-9a-f]{32}$")
MARKER_RE = re.compile(r"<!-- dev-platform-private-lineage:v1:(pln_[0-9a-f]{32}):([a-z0-9][a-z0-9-]*) -->")
ISSUE_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)$")


class PrivateLineageError(RuntimeError):
    pass


def enabled(root: Path) -> bool:
    value = read_platform_config(root).get("private_lineage", {})
    return isinstance(value, dict) and value.get("enabled") is True


GUARD_SCRIPT = "scripts/check_private_backlog_refs.py"
GUARD_NOT_APPLICABLE = "private-reference guard: not applicable by configuration (private_lineage not enabled)"


def guard_script(root: Path) -> Path | None:
    """Return the private-reference guard where private lineage is enabled, else ``None``.

    The guard is mandatory where private lineage is enabled: a missing script
    raises naming it. ``None`` means the guard does not apply by configuration;
    callers report ``GUARD_NOT_APPLICABLE``.
    """
    if not enabled(root):
        return None
    guard = root / GUARD_SCRIPT
    if not guard.is_file():
        raise PrivateLineageError(f"private lineage is enabled but {GUARD_SCRIPT} is missing")
    return guard


def require_clean_candidate(root: Path) -> None:
    """Run the existing private-reference guard over the current candidate.

    Enforced only where private lineage is enabled; a missing guard or a
    non-zero result stops explicitly. The guard's own diagnostics are opaque.
    """
    guard = guard_script(root)
    if guard is None:
        print(GUARD_NOT_APPLICABLE, flush=True)
        return
    result = subprocess.run(["python3", str(guard), "--root", str(root)], cwd=root, capture_output=True,
                            text=True, check=False, stdin=subprocess.DEVNULL)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[:2000] or "private-reference guard failed without a diagnostic"
        raise PrivateLineageError("private-reference guard blocked the candidate: " + detail)


def _comments(root: Path, repository: str, number: str) -> list[dict]:
    result = subprocess.run(
        ["gh", "api", f"repos/{repository}/issues/{number}/comments?per_page=100", "--paginate", "--slurp"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise PrivateLineageError("authorized private Issue comments cannot be read")
    try:
        pages = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PrivateLineageError("private Issue comments returned invalid JSON") from exc
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise PrivateLineageError("private Issue comments returned an unexpected shape")
    return [comment for page in pages for comment in page if isinstance(comment, dict)]


def handle_for_issue(root: Path, source_issue: str, change: str, *, create: bool = False) -> str:
    """Read or establish exactly one mapping; never infer it from a public slug."""
    match = ISSUE_RE.fullmatch(source_issue)
    if not match or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", change):
        raise PrivateLineageError("invalid private lineage identity")
    repository, number = match.groups()
    configured = read_platform_config(root).get("development_backlog", {})
    if not isinstance(configured, dict) or configured.get("repository", "").lower() != repository.lower():
        raise PrivateLineageError("private lineage source is outside the configured Backlog")

    def observed() -> list[tuple[str, str]]:
        values: list[tuple[str, str]] = []
        for comment in _comments(root, repository, number):
            for found in MARKER_RE.finditer(str(comment.get("body") or "")):
                values.append(found.groups())
        return values

    mappings = observed()
    if not mappings and create:
        handle = "pln_" + secrets.token_hex(16)
        body = f"<!-- dev-platform-private-lineage:v1:{handle}:{change} -->\nPrivate lineage mapping for `{change}`.\n"
        result = subprocess.run(
            ["gh", "api", "--method", "POST", f"repos/{repository}/issues/{number}/comments", "--input", "-"],
            input=json.dumps({"body": body}), cwd=root, capture_output=True, text=True, check=False,
        )
        if result.returncode:
            raise PrivateLineageError("private lineage mapping could not be written")
        mappings = observed()
    if len(mappings) != 1 or mappings[0][1] != change:
        raise PrivateLineageError("private lineage mapping is missing, ambiguous, or assigned to another change")
    return mappings[0][0]


def require_handle(root: Path, source_issue: str, change: str, public_handle: str) -> None:
    if not HANDLE_RE.fullmatch(public_handle) or handle_for_issue(root, source_issue, change) != public_handle:
        raise PrivateLineageError("public lineage handle does not match the private Issue")


# A bounded walk of open Backlog Issues; exceeding it is an explicit error, never a partial answer (BR-975).
LINEAGE_WALK_MAX_PAGES = 20
_OPEN_ISSUES_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 50, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { number comments(first: 100) { pageInfo { hasNextPage } nodes { body } } }
    }
  }
}
""".strip()


def _open_issue_pages(root: Path, repository: str, max_pages: int):
    owner, name = repository.split("/", 1)
    after = None
    for page in range(1, max_pages + 1):
        command = ["gh", "api", "graphql", "-f", f"query={_OPEN_ISSUES_QUERY}", "-F", f"owner={owner}", "-F", f"name={name}"]
        if after is not None:
            command += ["-F", f"after={after}"]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        if result.returncode:
            raise PrivateLineageError("open private Issues cannot be read: " + (result.stderr or result.stdout).strip()[:200])
        try:
            issues = json.loads(result.stdout)["data"]["repository"]["issues"]
            nodes, info = issues["nodes"], issues["pageInfo"]
        except (ValueError, KeyError, TypeError) as exc:
            raise PrivateLineageError("open private Issues returned an unexpected shape") from exc
        yield nodes
        if not info.get("hasNextPage"):
            return
        after = info.get("endCursor")
    raise PrivateLineageError(f"lineage walk exceeded {max_pages} pages of open private Issues")


def issue_for_handle(root: Path, handle: str, change: str, *, max_pages: int = LINEAGE_WALK_MAX_PAGES) -> str:
    """The one open private Issue whose trusted mapping marker names ``handle`` for ``change``.

    Only open Issues are walked: a task's Issue stays open until terminal reconciliation closes it.
    A marker counts only from a proven repository writer or the coordinator App. None, several, or
    a marker for another change raise; messages never name the handle.
    """
    import publication_queue
    from candidate_lifecycle import trusted_marker_comment

    if not HANDLE_RE.fullmatch(handle) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", change):
        raise PrivateLineageError("invalid private lineage identity")
    configured = read_platform_config(root).get("development_backlog", {})
    repository = configured.get("repository") if isinstance(configured, dict) else None
    if not isinstance(repository, str) or not ISSUE_RE.fullmatch(f"{repository}#1"):
        raise PrivateLineageError("private lineage needs the configured Backlog repository")
    candidates: list[str] = []
    for nodes in _open_issue_pages(root, repository, max_pages):
        for node in nodes:
            comments = node.get("comments") or {}
            bodies = [str(item.get("body") or "") for item in comments.get("nodes") or []]
            if (comments.get("pageInfo") or {}).get("hasNextPage") or any(handle in body for body in bodies):
                candidates.append(str(node["number"]))
    apps = publication_queue.trusted_apps(root)
    matches: list[tuple[str, str]] = []
    for number in candidates:
        rows = _comments(root, repository, number)
        writers = publication_queue.trusted_writers(root, rows, ("<!-- dev-platform-private-lineage:",),
                                                    repo=repository)
        for row in rows:
            if not trusted_marker_comment(row, apps, writers):
                continue
            for found_handle, found_change in MARKER_RE.findall(str(row.get("body") or "")):
                if found_handle == handle:
                    matches.append((f"{repository}#{number}", found_change))
    if not matches:
        raise PrivateLineageError("no open Issue carries this handle (already closed or missing)")
    if len({source for source, _ in matches}) != 1 or len(matches) != 1:
        raise PrivateLineageError("the lineage handle is carried by several trusted markers")
    source, found_change = matches[0]
    if found_change != change:
        raise PrivateLineageError(f"the lineage handle on Issue #{source.rsplit('#', 1)[1]} is assigned to another change")
    require_handle(root, source, change, handle)
    return source
