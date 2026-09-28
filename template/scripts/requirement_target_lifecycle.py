"""Prove that a Requirement target can complete the managed lifecycle."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import tomllib

import managed_task
from _platform_common import read_platform_config


class RequirementTargetLifecycleError(RuntimeError):
    pass


# These are the target-owned primitives a Requirement needs after its human
# intake: a managed child, OpenSpec verification/archive, and protected PR
# publication/terminal reconciliation.
REQUIRED_ENTRYPOINTS = (
    "scripts/requirement_intake.py",
    "scripts/execute_requirement.py",
    "scripts/managed_task.py",
    "scripts/start_managed_task.py",
    "scripts/requirement_terminal.py",
    "scripts/finish_task.py",
    "scripts/openspec_lifecycle.py",
)
REQUIRED_CAPABILITIES = ("openspec", "github_sync", "feature_branches")


def _failure(problems: list[str]) -> RequirementTargetLifecycleError:
    return RequirementTargetLifecycleError(
        "Requirement target lacks managed lifecycle support ("
        + "; ".join(problems)
        + "). Configure/opt the target into the managed lifecycle and retry from its checkout, "
        "or use that target's own supported local workflow outside a Dev Platform Requirement."
    )


def _config_problems(config: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    backlog = config.get("development_backlog")
    if not isinstance(backlog, dict):
        problems.append("missing [development_backlog] routing")
    elif (
        not isinstance(backlog.get("repository"), str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", backlog["repository"])
        or not isinstance(backlog.get("project_label"), str)
        or not re.fullmatch(r"project:[A-Za-z0-9_.-]+", backlog["project_label"])
        or not isinstance(backlog.get("default_priority"), str)
        or not managed_task.PRIORITY_RE.fullmatch(backlog["default_priority"])
    ):
        problems.append("invalid [development_backlog] routing")
    if config.get("protected_main") is not True:
        problems.append("protected_main must be true")
    if config.get("publish_mode") != "pr":
        problems.append("publish_mode must be 'pr'")
    if config.get("scm_provider") != "github":
        problems.append("scm_provider must be 'github'")
    capabilities = config.get("capabilities")
    if not isinstance(capabilities, dict):
        problems.append("missing [capabilities] managed lifecycle configuration")
    else:
        disabled = [name for name in REQUIRED_CAPABILITIES if capabilities.get(name) is not True]
        if disabled:
            problems.append("required managed capabilities are not enabled: " + ", ".join(disabled))
        if config.get("harness_mode") == "platform" and capabilities.get("platform_git_lifecycle") is not True:
            problems.append("platform_git_lifecycle must be enabled for platform harness")
    return problems


def require_local_target_support(root: Path, *, target_repository: str | None = None) -> None:
    """Require committed/local target evidence before Requirement progress."""
    root = root.resolve()
    try:
        config = read_platform_config(root)
    except (RuntimeError, OSError, tomllib.TOMLDecodeError) as exc:
        raise _failure([f"target configuration is unreadable: {exc}"]) from exc
    problems = _config_problems(config)
    if not (root / ".dev-platform.toml").is_file():
        problems.append("missing target .dev-platform.toml")
    missing = [entry for entry in REQUIRED_ENTRYPOINTS if not (root / entry).is_file()]
    if missing:
        problems.append("missing managed entrypoints: " + ", ".join(missing))
    if target_repository is not None:
        try:
            origin = managed_task.origin_repository(root)
        except managed_task.ManagedTaskError as exc:
            problems.append(f"target origin is unreadable: {exc}")
        else:
            if origin != target_repository:
                problems.append(f"target repository {target_repository!r} is not this checkout's origin {origin!r}")
    if problems:
        raise _failure(problems)


def require_connected_target_support(
    *, committed_config: dict[str, Any] | None, lifecycle_evidence: dict[str, Any] | None,
) -> None:
    """Require connected evidence equivalent to the local target predicate.

    A connected surface cannot inspect an untracked operator file.  Such a
    target must therefore provide a target-side ``operator_integration``
    attestation in addition to the same entrypoint/publication evidence.
    """
    evidence = lifecycle_evidence if isinstance(lifecycle_evidence, dict) else {}
    problems: list[str] = []
    if committed_config is None and evidence.get("operator_integration") is not True:
        problems.append("no committed [development_backlog] configuration or explicit target-side operator integration")
    entrypoints = evidence.get("managed_entrypoints")
    if entrypoints is not True:
        problems.append("managed OpenSpec/Requirement entrypoints are not proven")
    if evidence.get("protected_publication") is not True:
        problems.append("protected publication lifecycle is not proven")
    if problems:
        raise _failure(problems)
