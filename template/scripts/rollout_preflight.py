from __future__ import annotations

"""Read-only Dev Platform rollout observations for task start and the doctor.

Task start merges nothing here: an open rollout PR is merged only by an explicit
rollout. `agent_doctor.py` reports a pending rollout PR and task start reports
how far the installed platform lags behind the latest release.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from publication_state import github_repo_name, required_check_state_for_ref
from rollout_identity import RolloutPR, authoritative_pending_rollout, candidate_rollout_prs, gh_api, list_open_prs, parse_version

# Observed pending-rollout states.
NONE = "none"
PENDING_CHECKS = "pending_checks"
BLOCKED = "blocked"
GREEN = "green"


@dataclass(frozen=True)
class RolloutObservation:
    state: str
    detail: str = ""
    pr: RolloutPR | None = None


def rollout_bot_login(config: dict[str, Any]) -> str:
    tools = config.get("tools") if isinstance(config.get("tools"), dict) else {}
    rollout = tools.get("rollout") if isinstance(tools.get("rollout"), dict) else {}
    return str(rollout.get("bot_login") or "")


def observe_pending_rollout(root: Path, config: dict[str, Any], env: dict[str, str]) -> RolloutObservation:
    """Read-only: report an open rollout PR without merging or syncing anything."""
    main_branch = config["main_branch"]
    repository = github_repo_name(root, env)
    if repository is None:
        return RolloutObservation(NONE, detail="could not resolve the current GitHub repository from `gh repo view`; skipped the pending-rollout check")

    open_prs = list_open_prs(repository, main_branch, env=env)
    candidates = candidate_rollout_prs(open_prs, base_branch=main_branch)
    if not candidates:
        return RolloutObservation(NONE)

    bot_login = rollout_bot_login(config)
    if not bot_login:
        return RolloutObservation(
            BLOCKED,
            detail=(
                f"{len(candidates)} open PR(s) match the reserved rollout branch/base contract, but "
                "tools.rollout.bot_login is not configured in .dev-platform.toml, so the expected automation "
                "identity cannot be confirmed; resolve manually or update the platform config"
            ),
        )

    authoritative = authoritative_pending_rollout(open_prs, repository=repository, base_branch=main_branch, expected_bot=bot_login)
    if authoritative is None:
        return RolloutObservation(
            BLOCKED,
            detail=(
                f"{len(candidates)} open PR(s) match the reserved rollout branch/base contract for {repository}, but "
                f"none match the expected automation identity {bot_login!r}; refusing to guess ownership"
            ),
        )

    check_state = required_check_state_for_ref(root, env, str(authoritative.number), authoritative.head_sha)
    if check_state.kind == "failed":
        return RolloutObservation(
            BLOCKED, detail=f"rollout PR #{authoritative.number} required checks failed: {check_state.detail}", pr=authoritative,
        )
    if check_state.kind == "passed":
        return RolloutObservation(
            GREEN, detail=f"rollout PR #{authoritative.number} ({authoritative.version}) is green", pr=authoritative,
        )
    if check_state.kind in ("pending", "not_registered"):
        return RolloutObservation(
            PENDING_CHECKS,
            detail=f"rollout PR #{authoritative.number} ({authoritative.version}) required checks are not yet complete ({check_state.kind})",
            pr=authoritative,
        )
    return RolloutObservation(
        BLOCKED, detail=f"rollout PR #{authoritative.number} required-check state is unknown ({check_state.cause}): {check_state.detail}", pr=authoritative,
    )


# Platform release lag at task start (BR-843). A lagging project is reported and the start
# continues; anything that cannot be determined fails the start with its cause.
LAG_CURRENT = "current"
LAG_BEHIND = "behind"
LAG_NOT_APPLICABLE = "not-applicable"
ROLLOUT_COMMAND = "gh workflow run rollout.yml --repo {source} -f version={latest} -f repository={project}"
_SOURCE_RE = re.compile(r"^(?:gh:|https://github\.com/|git@github\.com:)([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$")


class PlatformLagError(RuntimeError):
    """The project's platform release lag cannot be determined."""


@dataclass(frozen=True)
class PlatformLag:
    state: str
    detail: str
    project_version: str = ""
    latest_version: str = ""
    command: str = ""


def platform_source_repository(root: Path) -> str:
    """``owner/name`` of the platform source recorded as ``_src_path`` in ``.copier-answers.yml``."""
    answers = root / ".copier-answers.yml"
    if not answers.is_file():
        raise PlatformLagError(f"{answers.name} is missing, so the platform source repository is unknown")
    for line in answers.read_text(encoding="utf-8").splitlines():
        if line.startswith("_src_path:"):
            source = line.split(":", 1)[1].strip().strip("'\"")
            match = _SOURCE_RE.fullmatch(source)
            if match is None:
                raise PlatformLagError(f"{answers.name} _src_path {source!r} is not a GitHub repository this check can read")
            return match.group(1)
    raise PlatformLagError(f"{answers.name} has no _src_path, so the platform source repository is unknown")


def latest_platform_release(source: str, env: dict[str, str]) -> str:
    """Tag of the latest published release of ``source``; it must be a stable ``vX.Y.Z``."""
    try:
        release = gh_api([f"repos/{source}/releases/latest"], env=env)
    except ValueError as exc:
        raise PlatformLagError(f"cannot read the latest release of {source}: {exc}") from exc
    tag = release.get("tag_name") if isinstance(release, dict) else None
    if not isinstance(tag, str):
        raise PlatformLagError(f"the latest release of {source} has no tag_name")
    try:
        parse_version(tag)
    except ValueError as exc:
        raise PlatformLagError(f"the latest release of {source} is not a stable version: {exc}") from exc
    return tag


def observe_platform_lag(root: Path, config: dict[str, Any], env: dict[str, str] | None) -> PlatformLag:
    """Compare the project's ``platform_version`` with its platform source's latest release.

    ``not-applicable`` only for the platform source checkout itself (``platform_version = "source"``).
    ``behind`` carries the exact Roll Out Platform command that opens this project's update PR.
    """
    installed = config["platform_version"]
    if installed == "source":
        return PlatformLag(LAG_NOT_APPLICABLE, "the platform source repository is not a managed downstream project")
    try:
        project_version = parse_version(f"v{installed}")
    except ValueError as exc:
        raise PlatformLagError(f".dev-platform.toml platform_version {installed!r} is not a stable version: {exc}") from exc
    source = platform_source_repository(root)
    if env is None:
        raise PlatformLagError(f"GitHub CLI authentication is unavailable, so the latest release of {source} cannot be read")
    latest = latest_platform_release(source, env)
    if project_version >= parse_version(latest):
        return PlatformLag(LAG_CURRENT, f"platform {installed} is the latest release {latest}", f"v{installed}", latest)
    project = github_repo_name(root, env)
    if project is None:
        raise PlatformLagError("cannot resolve this project's GitHub repository from `gh repo view` for the update command")
    command = ROLLOUT_COMMAND.format(source=source, latest=latest, project=project)
    return PlatformLag(
        LAG_BEHIND,
        f"this project runs Dev Platform v{installed}; the latest release is {latest}. "
        f"Open the update pull request for {project} with: {command}",
        f"v{installed}", latest, command,
    )
