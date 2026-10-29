#!/usr/bin/env python3
"""Owner-needed signals: an agent states that it needs the owner, with the question (BR-888).

A signal lives on the agent-board entry of the task that raised it and ends with that entry.
This script only records a question; it decides and answers nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from _platform_common import (
    current_worktree_root,
    locked_json,
    main_root,
    PlatformConfigError,
    read_platform_config,
    run_git,
    utc_now,
)
from agent_board import _find_item, board_path, scope_gate_required


class SignalError(RuntimeError):
    """A signal cannot be raised, resolved or read; the message names the cause."""


def normalise(question: str) -> str:
    return " ".join(question.split())


def signal_id(task_key: str, question: str) -> str:
    return hashlib.sha256(f"{task_key}\0{normalise(question)}".encode("utf-8")).hexdigest()[:12]


def _board_enabled(root: Path) -> bool:
    """``[capabilities] agent_board`` as a bool; an unclassifiable config is a named error, never an exit."""
    try:
        return scope_gate_required(read_platform_config(root))
    except PlatformConfigError as exc:
        raise SignalError(f"platform config unreadable: {exc}") from exc
    except SystemExit as exc:
        raise SignalError(f"agent_board is not classified in .dev-platform.toml: {exc}") from exc


def _require_board(root: Path) -> Path:
    if not _board_enabled(root):
        raise SignalError("owner-needed signals need the agent board: set [capabilities] agent_board = true in .dev-platform.toml")
    try:
        path = board_path(root)
    except (KeyError, PlatformConfigError) as exc:
        raise SignalError(f"agent_board is enabled but its path is unavailable: {exc}") from exc
    if not path.exists():
        raise SignalError(f"the agent board file {path} does not exist")
    return path


def _own_entry(items: list[dict], worktree: Path) -> dict:
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree).stdout.strip()
    entry = _find_item(items, worktree, branch)
    if entry is None:
        raise SignalError(f"no active agent-board entry for worktree {worktree} on branch {branch}; "
                          "a signal can only be raised from the worktree of a registered task")
    return entry


def _entry_signals(entry: object) -> list[dict]:
    """The signals of one board entry; a malformed entry or signal is a named error, never skipped."""
    if not isinstance(entry, dict):
        raise SignalError(f"agent board has a malformed entry: {entry!r}")
    if "signals" not in entry:
        return []
    signals = entry["signals"]
    if not isinstance(signals, list):
        raise SignalError(f"agent board entry {entry.get('id')!r} has a malformed signals value: {signals!r}")
    for item in signals:
        if not isinstance(item, dict) or "id" not in item:
            raise SignalError(f"agent board entry {entry.get('id')!r} has a malformed signal: {item!r}")
    return signals


def raise_signal(question: str, *, root: Path, worktree: Path, now: str | None = None) -> dict:
    text = normalise(question)
    if not text:
        raise SignalError("the question is empty")
    path = _require_board(root)
    stamp = now or utc_now()
    with locked_json(path) as data:
        items = data.get("items")
        if not isinstance(items, list):
            raise SignalError(f"the agent board {path} has no valid 'items' list")
        entry = _own_entry(items, worktree)
        sid = signal_id(str(entry.get("id", "")), text)
        signals = _entry_signals(entry)
        existing = next((s for s in signals if s["id"] == sid and not s.get("resolved_at")), None)
        if existing is not None:
            if "count" not in existing:
                raise SignalError(f"agent board signal {sid} has no count: {existing!r}")
            existing["last_raised_at"] = stamp
            existing["count"] += 1
            return {**existing, "repeat": True}
        signal = {"id": sid, "question": text, "project": root.name, "task": entry.get("task", ""),
                  "branch": entry.get("branch", ""), "raised_at": stamp, "last_raised_at": stamp, "count": 1}
        entry["signals"] = [*signals, signal]
        return {**signal, "repeat": False}


def resolve_signal(signal: str, resolved_by: str, *, root: Path, now: str | None = None) -> dict:
    if not resolved_by.strip():
        raise SignalError("--by must name who resolved the question")
    path = _require_board(root)
    with locked_json(path) as data:
        items = data.get("items")
        if not isinstance(items, list):
            raise SignalError(f"the agent board {path} has no valid 'items' list")
        for entry in items:
            for item in _entry_signals(entry):
                if item["id"] == signal and not item.get("resolved_at"):
                    item["resolved_at"] = now or utc_now()
                    item["resolved_by"] = resolved_by.strip()
                    return dict(item)
    raise SignalError(f"no open signal {signal} on the agent board")


def open_signals(root: Path, *, now: datetime) -> dict:
    """Open signals for viewers: ``configured`` False, ``error`` text or the sorted ``signals`` list; never writes."""
    try:
        if not _board_enabled(root):
            return {"configured": False, "signals": []}
        path = board_path(root)
        data = json.loads(path.read_text(encoding="utf-8"))
    except SignalError as exc:
        return {"configured": True, "error": f"agent board cannot be shown: {exc}", "signals": []}
    except (KeyError, PlatformConfigError, OSError, ValueError) as exc:
        return {"configured": True, "error": f"agent board unreadable: {exc}", "signals": []}
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {"configured": True, "error": f"agent board {path} has no valid 'items' list", "signals": []}
    signals = []
    try:
        for entry in items:
            for item in _entry_signals(entry):
                if item.get("resolved_at"):
                    continue
                raised = datetime.fromisoformat(item["raised_at"].replace("Z", "+00:00"))
                signals.append({**item, "age_minutes": max(0, int((now - raised).total_seconds() // 60))})
    except SignalError as exc:
        return {"configured": True, "error": str(exc), "signals": []}
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        return {"configured": True, "error": f"agent board has a malformed signal: {exc!r}", "signals": []}
    signals.sort(key=lambda s: s["raised_at"])
    return {"configured": True, "signals": signals}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Raise or resolve an owner-needed signal for the current task.")
    sub = parser.add_subparsers(dest="command", required=True)
    raise_p = sub.add_parser("raise", help="state that the owner is needed, with the question")
    raise_p.add_argument("--question", required=True)
    resolve_p = sub.add_parser("resolve", help="close an open signal")
    resolve_p.add_argument("--id", required=True)
    resolve_p.add_argument("--by", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "raise":
            result = raise_signal(args.question, root=main_root(), worktree=current_worktree_root())
        else:
            result = resolve_signal(args.id, args.by, root=main_root())
    except SignalError as exc:
        print(f"agent_signal: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
