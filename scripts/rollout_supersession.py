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
from pathlib import Path
from typing import Any
from urllib.parse import quote

import managed_projects

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "template" / "scripts"))

from rollout_identity import (  # noqa: E402
    ROLLOUT_BRANCH_RE,
    SEMVER_RE,
    RolloutPR,
    eligible_rollout_prs,
    gh_api,
    list_open_prs,
    parse_version,
    rollout_branch,
)

COPIER_COMMIT_RE = re.compile(r"^_commit:\s*['\"]?([^\s'\"]+)", re.MULTILINE)
PLATFORM_VERSION_RE = re.compile(r"^platform_version\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def find_exact_pending_rollout_pr(
    repository: str, base_branch: str, expected_bot: str, version: str,
) -> RolloutPR | None:
    """Find the trusted open rollout PR for an exact target version, if any.

    Reuses the same structured trust boundary as supersession (exact reserved
    branch, base branch, and automation identity from the GitHub API's own
    JSON) instead of parsing human-readable `gh` output or matching by title.
    """
    parse_version(version)
    eligible = eligible_rollout_prs(
        list_open_prs(repository, base_branch), repository=repository, base_branch=base_branch, expected_bot=expected_bot
    )
    return next((pr for pr in eligible if pr.version == version), None)


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
    # Maintenance has no just-created target PR.  The newest eligible open PR
    # was created only after this automation's validation path, so it is the
    # safely available replacement allowed by the OpenSpec contract.  Keeping
    # it while closing only strictly older eligible PRs prevents accumulated
    # pending rollouts from remaining actionable.
    if authoritative_version is None and eligible:
        newest = eligible[-1]
        authoritative_version = newest.version
        authoritative_pr = newest.number
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


def _cmd_reconcile(args: argparse.Namespace) -> int:
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


def _cmd_find_pending(args: argparse.Namespace) -> int:
    try:
        pr = find_exact_pending_rollout_pr(args.repository, args.base_branch, args.expected_bot, args.version)
        payload = (
            {"found": True, "url": pr.url, "number": pr.number, "branch": pr.branch}
            if pr is not None
            else {"found": False, "url": None, "number": None, "branch": None}
        )
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0
    except ValueError as exc:
        print(f"Managed rollout pending-PR detection: BLOCKED: {exc}", file=sys.stderr)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Structured helpers for the managed rollout control plane.")
    sub = parser.add_subparsers(dest="command", required=True)

    reconcile_parser = sub.add_parser("reconcile", help="Reconcile stale exact-version managed rollout PRs.")
    reconcile_parser.add_argument("--repository", required=True)
    reconcile_parser.add_argument("--base-branch", required=True)
    reconcile_parser.add_argument("--expected-bot", required=True, help="Expected GitHub App login, for example dev-platform-bot[bot].")
    reconcile_parser.add_argument("--registry", type=Path, default=ROOT / "managed-projects.json")
    reconcile_parser.add_argument("--authoritative-version")
    reconcile_parser.add_argument("--authoritative-pr", type=int)
    reconcile_parser.add_argument("--apply", action="store_true", help="Close only PRs shown by the dry-run plan.")
    reconcile_parser.add_argument("--output", type=Path)
    reconcile_parser.set_defaults(func=_cmd_reconcile)

    pending_parser = sub.add_parser("find-pending", help="Find the trusted open rollout PR for an exact target version.")
    pending_parser.add_argument("--repository", required=True)
    pending_parser.add_argument("--base-branch", required=True)
    pending_parser.add_argument("--expected-bot", required=True, help="Expected GitHub App login, for example dev-platform-bot[bot].")
    pending_parser.add_argument("--version", required=True)
    pending_parser.add_argument("--output", type=Path)
    pending_parser.set_defaults(func=_cmd_find_pending)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
