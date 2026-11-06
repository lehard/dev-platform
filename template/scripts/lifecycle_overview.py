#!/usr/bin/env python3
"""Read-only overview for the chat coordinator: open Requirements, owner decisions and sessions.

Projects what GitHub and the machine-local registries already record. It writes nothing to GitHub,
keeps no state store and, besides GitHub, only an optional disposable local read cache
(``github_read_cache``). It reports ``unknown`` for any source it cannot read instead of presenting
it as healthy. See ``docs/engineering/chat-coordinator.md``.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from _platform_common import current_worktree_root, read_platform_config

READ_PARALLELISM = 8
PROJECT_LABEL = re.compile(r"project:[A-Za-z0-9_.-]+")


class OverviewError(RuntimeError):
    pass


def assess_requirement(requirement: str, aggregate: dict | None, error: str | None) -> dict:
    """Requirement-level stage from its read-through progress."""
    if error is not None or aggregate is None:
        return {"requirement": requirement, "stage": "unknown", "status": None, "progress": None,
                "findings": [{"kind": "unknown-source", "detail": error or "Requirement progress is unavailable",
                              "evidence": requirement}]}
    status, progress = aggregate.get("status"), aggregate.get("progress") or {}
    note = None
    sources = {d.get("source") for d in progress.get("diagnostics") or []}
    if status == "pre-authoring" and progress.get("stage") == "unknown" and sources == {"orchestrator"}:
        # No linked child and no pre-authoring state in this checkout (that state is machine-local):
        # the Requirement has not produced a technical child that this view can see.
        stage, note = "not-started", "no linked child; pre-authoring state is machine-local and not visible from this checkout"
    elif status == "Done":
        stage = "closed"
    elif progress.get("stage") == "unknown" or status == "unknown":
        stage = "unknown"
    elif progress.get("stage") == "blocked" or status == "Blocked":
        stage = "needs-intervention"
    else:
        stage = "in-development"
    return {"requirement": requirement, "stage": stage, "status": status, "progress": progress, "note": note, "findings": []}


def owner_acceptance(requirement: str, items: list[dict], open_ids: list[str]) -> list[dict]:
    """Open operator acceptance items with their check and the exact owner decision command (BR-943)."""
    return [{**item, "command": f"python3 scripts/requirement_terminal.py accept --requirement {requirement} "
                                f"--item {item['id']} --decision confirmed --via chat-coordinator --reason \"<why>\""}
            for item in items if item["id"] in open_ids]


def _observe_requirement(root: Path, requirement: str) -> dict:
    import managed_task
    import requirement_intake as intake
    import requirement_terminal as terminal

    try:
        aggregate = intake.aggregate(root, requirement=requirement)
        assessment = assess_requirement(requirement, aggregate, None)
    except (intake.RequirementIntakeError, OSError) as exc:
        return assess_requirement(requirement, None, str(exc))
    if assessment["stage"] == "closed":
        return assessment
    try:
        parent = intake.fetch_issue(root, *intake.issue_ref(requirement))
        items = terminal.operator_items(str(parent.get("body") or ""))
        pending = owner_acceptance(requirement, items, terminal.open_acceptance_items(root, requirement, parent))
    except (terminal.RequirementTerminalError, managed_task.ManagedTaskError, intake.RequirementIntakeError) as exc:
        return {**assessment, "findings": [*assessment["findings"], {
            "kind": "unknown-source", "detail": f"operator acceptance of {requirement} is unreadable: {exc}",
            "evidence": requirement}]}
    if not pending:
        return assessment
    return {**assessment, "owner_acceptance": pending, "findings": [*assessment["findings"], {
        "kind": "awaits-owner-acceptance",
        "detail": "ждёт владельца: " + ", ".join(item["id"] for item in pending), "evidence": requirement}]}


def _backlog_binding(root: Path) -> tuple[str, str]:
    section = read_platform_config(root).get("development_backlog")
    section = section if isinstance(section, dict) else {}
    value, label = section.get("repository"), section.get("project_label")
    if not isinstance(value, str) or "/" not in value:
        raise OverviewError("[development_backlog] repository in .dev-platform.toml must name the Backlog repository (owner/name)")
    if not isinstance(label, str) or not PROJECT_LABEL.fullmatch(label):
        raise OverviewError("[development_backlog] project_label in .dev-platform.toml must name this project's Backlog label (project:<slug>)")
    return value, label


def _open_requirements(root: Path, backlog: str, project_label: str) -> list[str]:
    """Open Requirements of this project only: the shared Backlog also holds other projects' Requirements."""
    import github_read_cache

    labels = quote(f"type:requirement,{project_label}", safe=",")
    try:
        rows = github_read_cache.cached_gh_json(root, "api", "--paginate", f"repos/{backlog}/issues?state=open&labels={labels}&per_page=100")
    except github_read_cache.GithubReadError as exc:
        raise OverviewError(str(exc)) from exc
    if not isinstance(rows, list):
        raise OverviewError(f"open Requirements of {backlog} labeled {project_label} could not be listed")
    return [f"{backlog}#{row['number']}" for row in rows if isinstance(row, dict) and "pull_request" not in row]


def read_sessions(root: Path, *, now: datetime) -> dict:
    """The platform session registry as ``agent_sessions`` computed it; never inferred here (BR-887)."""
    import agent_sessions

    section = read_platform_config(root).get("agent_sessions")
    if not isinstance(section, dict):
        return {"configured": False, "sessions": []}
    for key in ("directory", "stale_after_seconds", "ended_keep_seconds"):
        if key not in section:
            raise OverviewError(f"[agent_sessions] {key} must be set in the platform configuration")
    try:
        items = agent_sessions.list_sessions(Path(str(section["directory"])).expanduser(), now=now,
                                             stale_after=int(section["stale_after_seconds"]),
                                             ended_keep=int(section["ended_keep_seconds"]))
    except (agent_sessions.SessionError, ValueError) as exc:
        return {"configured": True, "error": str(exc), "sessions": []}
    return {"configured": True, "sessions": items}


def read_owner_needed(root: Path, now: datetime) -> dict:
    """Open owner-needed signals from the agent board, exactly as ``agent_signal`` stores them (BR-888)."""
    import agent_signal

    return agent_signal.open_signals(root, now=now)


def _session_line(item: dict) -> str:
    detail = item.get("detail") or {}
    note = f" ({', '.join(f'{k}={v}' for k, v in detail.items() if v)})" if detail else ""
    return (f"{item['provider']} session {item['session_id'][:8]} pid {item.get('pid')} [{item['state']}]{note} "
            f"since {item['state_since']}; liveness {item.get('liveness')}")


def overview(root: Path, *, now: datetime) -> dict:
    """Every open Requirement of this project, open owner signals and live sessions."""
    backlog, project_label = _backlog_binding(root)
    listed = _open_requirements(root, backlog, project_label)
    with ThreadPoolExecutor(max_workers=READ_PARALLELISM) as pool:  # independent read-only GitHub observations
        requirements = list(pool.map(lambda requirement: _observe_requirement(root, requirement), listed))
    return {"agent_sessions": read_sessions(root, now=now), "owner_needed": read_owner_needed(root, now),
            "backlog": backlog, "generated_at": now.isoformat(timespec="seconds"), "requirements": requirements}


def show_requirement(root: Path, requirement: str, *, now: datetime) -> dict:
    return {"generated_at": now.isoformat(timespec="seconds"), "requirement": _observe_requirement(root, requirement),
            "agent_sessions": read_sessions(root, now=now)}


def _registry_status(registry: dict) -> str | None:
    """The explicit line for an unconfigured or unreadable registry; sessions are never silently shown as absent."""
    if not registry["configured"]:
        return "Sessions: not configured ([agent_sessions] directory in the platform configuration)"
    if registry.get("error"):
        return f"Sessions: registry unreadable: {registry['error']}"
    return None


def _owner_needed_lines(owner_needed: dict) -> list[str]:
    if not owner_needed["configured"]:
        return ["\nOwner needed: not shown (agent board capability is not enabled in the platform configuration)"]
    if owner_needed.get("error"):
        return [f"\nOwner needed: cannot be shown: {owner_needed['error']}"]
    lines = ["\nOwner needed:"]
    lines += [f"  [{s['project']}] {s['task']}: {s['question']} (id {s['id']}, {s['age_minutes']} min ago)"
              for s in owner_needed["signals"]] or ["  none"]
    return lines


def _owner_acceptance_lines(req: dict) -> list[str]:
    return [line for item in req.get("owner_acceptance") or [] for line in (
        f"  owner acceptance {item['id']}: {item['action']}", f"    check: {item['check']}", f"    decide: {item['command']}")]


def _requirement_lines(req: dict) -> list[str]:
    note = f" ({req['note']})" if req.get("note") else ""
    return ([f"Requirement {req['requirement']} [{req['stage']}] status={req.get('status')}{note}"]
            + [f"  ! {finding['kind']}: {finding['detail']}" for finding in req["findings"]] + _owner_acceptance_lines(req))


def _session_lines(registry: dict) -> list[str]:
    status = _registry_status(registry)
    if status:
        return [f"\n{status}"]
    return ["\nSessions:"] + ([f"  {_session_line(item)} branch={item.get('branch') or '-'} project={item.get('project') or '-'}"
                               for item in registry["sessions"]] or ["  none"])


def render(result: dict) -> str:
    if "requirement" in result:
        return "\n".join(_requirement_lines(result["requirement"]) + _session_lines(result["agent_sessions"]))
    lines = [f"Dev Platform overview {result['generated_at']} (Backlog {result['backlog']})"]
    for req in result["requirements"]:
        lines += _requirement_lines(req)
    lines += _owner_needed_lines(result["owner_needed"]) + _session_lines(result["agent_sessions"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only overview for the chat coordinator (writes nothing)")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("summary", help="open Requirements, owner decisions and sessions (default)")
    show = sub.add_parser("show", help="drill down into one Requirement")
    show.add_argument("--requirement", required=True)
    args = parser.parse_args(argv)
    from github_read_cache import GithubReadCacheError

    root = current_worktree_root()
    now = datetime.now(timezone.utc)
    try:
        result = show_requirement(root, args.requirement, now=now) if args.command == "show" else overview(root, now=now)
    except (OverviewError, GithubReadCacheError) as exc:
        print(f"lifecycle overview: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
