from __future__ import annotations

"""Structured Dev Platform rollout PR identity/eligibility contract.

This is the single source of truth for what counts as a Dev Platform-owned
managed rollout pull request. Central rollout automation
(`scripts/rollout_supersession.py`) and downstream pre-task reconciliation
(`rollout_preflight.py`) both import this module instead of re-deriving their
own notion of ownership. Ownership is always established from GitHub's own
structured PR metadata -- repository/base, the reserved exact-version branch
contract, and the expected automation identity -- and never from a PR title
or body.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote

SEMVER_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ROLLOUT_BRANCH_RE = re.compile(r"^dev-platform/rollout-(v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$")


def parse_version(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError(f"platform version must be an exact stable SemVer tag vX.Y.Z; got {version!r}")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def rollout_branch(version: str) -> str:
    parse_version(version)
    return f"dev-platform/rollout-{version}"


@dataclass(frozen=True)
class RolloutPR:
    number: int
    url: str
    branch: str
    version: str
    head_sha: str = ""


def gh_api(
    arguments: list[str], *, env: dict[str, str] | None = None, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> Any:
    result = runner(["gh", "api", *arguments], text=True, capture_output=True, check=False, env=env)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ValueError(f"GitHub API request failed: {detail}")
    if not result.stdout.strip():
        # GitHub returns 204 No Content for a successful ref deletion.
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub API returned invalid JSON") from exc


def list_open_prs(repository: str, base_branch: str, *, env: dict[str, str] | None = None) -> list[dict[str, Any]]:
    payload = gh_api(
        ["--paginate", "--slurp", f"repos/{repository}/pulls?state=open&base={quote(base_branch, safe='')}&per_page=100"],
        env=env,
    )
    pages = payload if isinstance(payload, list) else [payload]
    return [item for page in pages if isinstance(page, list) for item in page if isinstance(item, dict)]


def candidate_rollout_prs(prs: list[dict[str, Any]], *, base_branch: str) -> list[dict[str, Any]]:
    """Structural-only match: reserved branch pattern and exact base branch.

    Deliberately ignores repository/head-repo and automation identity. Used
    only to detect an *ambiguous* pending rollout (a PR that looks like a
    rollout but whose ownership cannot yet be confirmed) -- never to select a
    PR to merge.
    """
    matches: list[dict[str, Any]] = []
    for pr in prs:
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        branch = head.get("ref")
        if isinstance(branch, str) and ROLLOUT_BRANCH_RE.fullmatch(branch) and base.get("ref") == base_branch:
            matches.append(pr)
    return matches


def eligible_rollout_prs(
    prs: list[dict[str, Any]], *, repository: str, base_branch: str, expected_bot: str
) -> list[RolloutPR]:
    """Return only PRs that cross the complete managed-rollout trust boundary."""
    eligible: list[RolloutPR] = []
    for pr in prs:
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        user = pr.get("user") if isinstance(pr.get("user"), dict) else {}
        branch = head.get("ref")
        match = ROLLOUT_BRANCH_RE.fullmatch(branch) if isinstance(branch, str) else None
        head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
        if not match or base.get("ref") != base_branch:
            continue
        if user.get("login") != expected_bot or head_repo.get("full_name") != repository:
            continue
        number = pr.get("number")
        url = pr.get("html_url")
        if not isinstance(number, int) or not isinstance(url, str):
            continue
        version = match.group(1)
        parse_version(version)
        head_sha = head.get("sha")
        eligible.append(RolloutPR(number=number, url=url, branch=branch, version=version, head_sha=head_sha if isinstance(head_sha, str) else ""))
    return sorted(eligible, key=lambda item: (parse_version(item.version), item.number))


def authoritative_pending_rollout(
    prs: list[dict[str, Any]], *, repository: str, base_branch: str, expected_bot: str
) -> RolloutPR | None:
    """The single newest authoritative eligible pending rollout, if any.

    Mirrors the selection `scripts/rollout_supersession.py` already uses when
    no explicit authoritative PR is supplied: the newest eligible PR is
    authoritative and older eligible PRs are superseded.
    """
    eligible = eligible_rollout_prs(prs, repository=repository, base_branch=base_branch, expected_bot=expected_bot)
    return eligible[-1] if eligible else None


