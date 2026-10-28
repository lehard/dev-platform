"""A complete `.dev-platform.toml` for tests that need a valid platform configuration.

`read_platform_config` validates the platform configuration schema, so a test
fixture must carry every required key. Tests override only what they exercise
and append feature tables through ``extra``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

PLATFORM_CONFIG_TOP: dict[str, Any] = {
    "schema_version": 2,
    "platform_version": "1.0.0",
    "platform_ci_ref": "test",
    "project_name": "Test Project",
    "project_slug": "test-project",
    "main_branch": "main",
    "workflow_profile": "multi-agent",
    "harness_mode": "platform",
    "protected_main": True,
    "publish_mode": "pr",
    "pr_merge_mode": "auto",
    "scm_provider": "github",
    "agent_tools": "claude,codex",
}
PLATFORM_CONFIG_CAPABILITIES: dict[str, bool] = {
    "openspec": True,
    "github_sync": True,
    "feature_branches": True,
    "worktrees": True,
    "agent_board": True,
    "platform_git_lifecycle": True,
}
PLATFORM_CONFIG_PATHS: dict[str, str] = {
    "worktrees": ".claude/worktrees",
    "agent_board": ".claude/agents-board.json",
    "main_merge_lock": ".claude/main-merge.lock",
    "pending_worktrees": ".claude/pending-worktrees.md",
    "friction_log": ".claude/agent-friction.jsonl",
    "friction_state": ".claude/agent-friction-state.json",
    "friction_reports": ".claude/reports/process-improvement",
    "checks": "dev-platform/checks.toml",
}


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def platform_config_text(
    *,
    extra: str = "",
    omit: tuple[str, ...] = (),
    capabilities: dict[str, bool] | None = None,
    paths: dict[str, str] | None = None,
    **top: Any,
) -> str:
    """Render a complete configuration; ``omit`` drops top-level keys or ``paths.<key>``."""
    values = {**PLATFORM_CONFIG_TOP, **top}
    lines = [f"{key} = {_value(value)}" for key, value in values.items() if key not in omit]
    lines += ["", "[capabilities]"]
    lines += [f"{key} = {_value(value)}" for key, value in {**PLATFORM_CONFIG_CAPABILITIES, **(capabilities or {})}.items()]
    lines += ["", "[paths]"]
    lines += [
        f"{key} = {_value(value)}"
        for key, value in {**PLATFORM_CONFIG_PATHS, **(paths or {})}.items()
        if f"paths.{key}" not in omit
    ]
    text = "\n".join(lines) + "\n"
    return text + ("\n" + extra.strip() + "\n" if extra.strip() else "")


def write_platform_config(root: Path, **kwargs: Any) -> Path:
    path = root / ".dev-platform.toml"
    path.write_text(platform_config_text(**kwargs), encoding="utf-8")
    return path
