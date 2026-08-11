from __future__ import annotations

"""Safely reconcile stale, bot-owned managed-rollout pull requests.

This helper deliberately treats GitHub's PR metadata as a trust boundary.  It
does not infer rollout ownership from a title or body: an eligible PR must have
the reserved exact-version branch, the configured base branch, and the GitHub
App identity used by the rollout workflow.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import managed_projects

ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
ROLLOUT_BRANCH_RE = re.compile(r"^dev-platform/rollout-(v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$")
COPIER_COMMIT_RE = re.compile(r"^_commit:\s*['\"]?([^\s'\"]+)", re.MULTILINE)
PLATFORM_VERSION_RE = re.compile(r"^platform_version\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


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


def gh_api(arguments: list[str], *, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> Any:
    result = runner(["gh", "api", *arguments], text=True, capture_output=True, check=False)
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


def list_open_prs(repository: str, base_branch: str) -> list[dict[str, Any]]:
    payload = gh_api([
        "--paginate", "--slurp", f"repos/{repository}/pulls?state=open&base={quote(base_branch, safe='')}&per_page=100"
    ])
    pages = payload if isinstance(payload, list) else [payload]
    return [item for page in pages if isinstance(page, list) for item in page if isinstance(item, dict)]


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
        eligible.append(RolloutPR(number=number, url=url, branch=branch, version=version))
    return sorted(eligible, key=lambda item: (parse_version(item.version), item.number))


def platform_version_from_contents(copier_text: str, config_text: str) -> str | None:
    copier = COPIER_COMMIT_RE.search(copier_text)
    config = PLATFORM_VERSION_RE.search(config_text)
    if not copier or not config:
        return None
    tag = copier.group(1)
    try:
        parse_version(tag)
    except ValueError:
        return None
    return tag if config.group(1) == tag[1:] else None


def raw_file(repository: str, path: str, ref: str) -> str:
    encoded_path = quote(path, safe="/")
    payload = gh_api(["-H", "Accept: application/vnd.github+json", f"repos/{repository}/contents/{encoded_path}?ref={quote(ref, safe='')}"])
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), str):
        raise ValueError(f"could not read {path} from {repository}@{ref}")
    try:
        return base64.b64decode(payload["content"], validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"could not decode {path} from {repository}@{ref}") from exc


def committed_platform_version(repository: str, base_branch: str) -> str | None:
    try:
        return platform_version_from_contents(
            raw_file(repository, ".copier-answers.yml", base_branch),
            raw_file(repository, ".dev-platform.toml", base_branch),
        )
    except ValueError as exc:
        print(f"::warning::rollout supersession cannot prove committed platform version for {repository}: {exc}", file=sys.stderr)
        return None


def plan_supersession(
    eligible: list[RolloutPR], *, base_version: str | None, authoritative_version: str | None,
    authoritative_pr: int | None = None,
) -> list[tuple[RolloutPR, str]]:
    """Plan only stale PRs; the newest relevant PR is intentionally retained."""
    if base_version:
        parse_version(base_version)
    if authoritative_version:
        parse_version(authoritative_version)
        if authoritative_pr is None or not any(
            pr.number == authoritative_pr and pr.version == authoritative_version for pr in eligible
        ):
            raise ValueError("authoritative rollout PR is not an eligible exact-version managed rollout PR")
    planned: list[tuple[RolloutPR, str]] = []
    for pr in eligible:
        if base_version and parse_version(pr.version) <= parse_version(base_version):
            planned.append((pr, f"committed downstream base already uses {base_version}"))
        elif authoritative_version and parse_version(pr.version) < parse_version(authoritative_version):
            planned.append((pr, f"superseded by validated rollout {authoritative_version} (PR #{authoritative_pr})"))
    return planned


def close_and_delete(repository: str, pr: RolloutPR, reason: str) -> None:
    gh_api(["-X", "PATCH", f"repos/{repository}/pulls/{pr.number}", "-f", "state=closed"])
    confirmed = gh_api([f"repos/{repository}/pulls/{pr.number}"])
    if not isinstance(confirmed, dict) or confirmed.get("state") != "closed":
        raise ValueError(f"{repository} PR #{pr.number} was not confirmed closed")
    gh_api(["-X", "POST", f"repos/{repository}/issues/{pr.number}/comments", "-f", f"body=Superseded: {reason}."])
    try:
        gh_api(["-X", "DELETE", f"repos/{repository}/git/refs/heads/{quote(pr.branch, safe='')}"])
    except ValueError as exc:
        print(f"::warning::rollout supersession closed {repository} PR #{pr.number}, but could not delete {pr.branch}: {exc}", file=sys.stderr)


def require_managed(repository: str, registry: Path) -> str:
    data = managed_projects.load_registry(registry)
    targets = managed_projects.managed_projects(data, repository)
    return targets[0]["default_branch"]


def reconcile(
    *, repository: str, base_branch: str, expected_bot: str, registry: Path,
    authoritative_version: str | None, authoritative_pr: int | None, apply: bool,
) -> dict[str, Any]:
    configured_base = require_managed(repository, registry)
    if configured_base != base_branch:
        raise ValueError(f"{repository}: requested base {base_branch!r} does not match managed registry")
    eligible = eligible_rollout_prs(
        list_open_prs(repository, base_branch), repository=repository, base_branch=base_branch, expected_bot=expected_bot
    )
    base_version = committed_platform_version(repository, base_branch)
    planned = plan_supersession(
        eligible, base_version=base_version, authoritative_version=authoritative_version,
        authoritative_pr=authoritative_pr,
    )
    report = {
        "repository": repository,
        "base_branch": base_branch,
        "base_version": base_version,
        "authoritative_version": authoritative_version,
        "authoritative_pr": authoritative_pr,
        "mode": "apply" if apply else "dry-run",
        "eligible_open_prs": [pr.__dict__ for pr in eligible],
        "planned_closures": [
            {"number": pr.number, "url": pr.url, "branch": pr.branch, "version": pr.version, "reason": reason}
            for pr, reason in planned
        ],
    }
    if apply:
        failures: list[str] = []
        for pr, reason in planned:
            try:
                close_and_delete(repository, pr, reason)
            except ValueError as exc:
                failures.append(f"{repository} PR #{pr.number}: {exc}")
        if failures:
            raise ValueError("; ".join(failures))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile stale exact-version managed rollout PRs.")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--expected-bot", required=True, help="Expected GitHub App login, for example dev-platform-bot[bot].")
    parser.add_argument("--registry", type=Path, default=ROOT / "managed-projects.json")
    parser.add_argument("--authoritative-version")
    parser.add_argument("--authoritative-pr", type=int)
    parser.add_argument("--apply", action="store_true", help="Close only PRs shown by the dry-run plan.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if bool(args.authoritative_version) != bool(args.authoritative_pr):
            raise ValueError("authoritative version and PR must be supplied together")
        report = reconcile(
            repository=args.repository, base_branch=args.base_branch, expected_bot=args.expected_bot,
            registry=args.registry, authoritative_version=args.authoritative_version,
            authoritative_pr=args.authoritative_pr, apply=args.apply,
        )
        text = json.dumps(report, ensure_ascii=False, sort_keys=True)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    except ValueError as exc:
        print(f"Managed rollout supersession: BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
