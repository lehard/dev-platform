#!/usr/bin/env python3
"""Verify the private Platform Health Review's bounded App-token access.

The private operator workflow invokes this immutable-release helper before an
AI review. It emits only available/degraded state and an evidence category;
tokens and GitHub access errors never enter logs or workflow outputs.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass


DEFAULT_PLATFORM_REPOSITORY = "lehard/dev-platform"
DEFAULT_BACKLOG_REPOSITORY = "lehard/development-backlog"
UNAVAILABLE_CATEGORY = "GitHub App read token or required private repository access"


@dataclass(frozen=True)
class PreflightResult:
    status: str
    unavailable_evidence: str | None = None


def _api(token: str, endpoint: str) -> bool:
    """Perform one read-only API probe without surfacing the API response."""
    completed = subprocess.run(
        ["gh", "api", "--method", "GET", endpoint],
        env={**os.environ, "GH_TOKEN": token},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def preflight(*, token: str, platform_repository: str, backlog_repository: str) -> PreflightResult:
    if not token:
        return PreflightResult("degraded", UNAVAILABLE_CATEGORY)
    probes = (
        f"repos/{platform_repository}/contents/openspec/specs/platform-health-review/spec.md",
        f"repos/{platform_repository}/pulls?state=closed&per_page=1",
        f"repos/{backlog_repository}/issues?state=open&per_page=1",
        f"repos/{backlog_repository}/pulls?state=closed&per_page=1",
    )
    if all(_api(token, endpoint) for endpoint in probes):
        return PreflightResult("available")
    return PreflightResult("degraded", UNAVAILABLE_CATEGORY)


def write_output(path: str, result: PreflightResult) -> None:
    lines = [f"private_evidence_status={result.status}"]
    if result.unavailable_evidence:
        lines.append(f"unavailable_evidence={result.unavailable_evidence}")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-env", default="PLATFORM_HEALTH_READ_TOKEN")
    parser.add_argument("--platform-repository", default=DEFAULT_PLATFORM_REPOSITORY)
    parser.add_argument("--backlog-repository", default=DEFAULT_BACKLOG_REPOSITORY)
    args = parser.parse_args(argv)
    result = preflight(
        token=os.environ.get(args.token_env, ""),
        platform_repository=args.platform_repository,
        backlog_repository=args.backlog_repository,
    )
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        write_output(output_path, result)
    print(f"Private evidence preflight: {result.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
