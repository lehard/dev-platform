#!/usr/bin/env python3
"""Check cloud-maintenance setup without reading or printing secret values."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


REQUIRED_SECRET = "OPENAI_API_KEY"
PROBE_WORKFLOW = "cloud-maintenance-preflight.yml"
CLOUD_MAINTENANCE_WORKFLOWS = (
    "process-issue-triage.lock.yml",
    "weekly-process-backlog-review.lock.yml",
    "architecture-health-review.lock.yml",
)


class PreflightError(RuntimeError):
    """A GitHub metadata query could not be completed safely."""


@dataclass(frozen=True)
class PreflightResult:
    exit_code: int
    messages: tuple[str, ...]


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def run_gh(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("gh", *arguments), text=True, capture_output=True, check=False
    )


def json_gh(arguments: Sequence[str], runner: Runner) -> list[dict[str, object]]:
    result = runner(arguments)
    if result.returncode:
        raise PreflightError("GitHub metadata is unavailable; run `gh auth status` and try again.")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PreflightError("GitHub returned unusable metadata; try again.") from error
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PreflightError("GitHub returned unusable metadata; try again.")
    return value


def preflight(*, repo: str | None, ref: str, runner: Runner = run_gh) -> PreflightResult:
    repo_args = ("--repo", repo) if repo else ()
    workflows = json_gh(
        ("workflow", "list", "--all", "--limit", "100", "--json", "name,state,path", *repo_args), runner
    )
    states = {
        str(workflow.get("path")): str(workflow.get("state"))
        for workflow in workflows
        if str(workflow.get("path")) in {f".github/workflows/{name}" for name in CLOUD_MAINTENANCE_WORKFLOWS}
    }
    missing_workflows = [name for name in CLOUD_MAINTENANCE_WORKFLOWS if f".github/workflows/{name}" not in states]
    if missing_workflows:
        return PreflightResult(
            2,
            (
                "Cloud maintenance workflow metadata is incomplete: "
                + ", ".join(missing_workflows)
                + ". Deploy the workflow files to the default branch before running this preflight.",
            ),
        )

    enabled = [name.rsplit("/", 1)[-1] for name, state in states.items() if state == "active"]
    disabled = [name.rsplit("/", 1)[-1] for name, state in states.items() if state != "active"]
    messages = [f"Enabled cloud maintenance workflows: {', '.join(enabled) or 'none'}." ]
    if disabled:
        messages.append("Disabled cloud maintenance workflows: " + ", ".join(disabled) + ".")
    if not enabled:
        messages.append("No provider probe was dispatched; disabled cloud maintenance does not block deterministic CI, release, or rollout.")
        return PreflightResult(0, tuple(messages))

    secrets = json_gh(("secret", "list", "--json", "name", *repo_args), runner)
    secret_names = {str(secret.get("name")) for secret in secrets}
    if REQUIRED_SECRET not in secret_names:
        messages.append(
            "Missing required Actions secret OPENAI_API_KEY. Configure it in repository Settings → Secrets and variables → Actions, then rerun this preflight."
        )
        messages.append("No provider probe was dispatched.")
        return PreflightResult(2, tuple(messages))

    dispatched = runner(("workflow", "run", PROBE_WORKFLOW, "--ref", ref, *repo_args))
    if dispatched.returncode:
        return PreflightResult(
            2,
            tuple(messages)
            + ("Provider probe could not be dispatched. Check Actions permissions and try again.",),
        )
    return PreflightResult(
        0,
        tuple(messages)
        + (
            "OPENAI_API_KEY metadata is present; dispatched the secret-safe provider probe.",
            "Inspect the Cloud Maintenance Preflight run for OPENAI_PROVIDER_AUTHENTICATION_OK, OPENAI_PROVIDER_INVALID_CREDENTIAL, OPENAI_PROVIDER_UNREACHABLE, or OPENAI_PROVIDER_REJECTED.",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check enabled cloud-maintenance workflows and dispatch a secret-safe provider probe."
    )
    parser.add_argument("--repo", help="GitHub repository in OWNER/REPO form (defaults to the current repository)")
    parser.add_argument("--ref", default="main", help="Git ref containing the preflight workflow (default: main)")
    args = parser.parse_args()
    try:
        result = preflight(repo=args.repo, ref=args.ref)
    except PreflightError as error:
        print(f"Cloud maintenance preflight unavailable: {error}")
        return 2
    for message in result.messages:
        print(message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
