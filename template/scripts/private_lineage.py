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
