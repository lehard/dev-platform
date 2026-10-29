#!/usr/bin/env python3
"""Registry of live agent sessions: the platform computes the status, viewers only read it (BR-887).

``hook`` ingests one Claude Code hook event (stdin JSON) or one Codex notification (``--payload-json``) and
updates one JSON file per session in an explicit state directory. ``list`` reads the registry and adds
liveness. ``hooks`` renders, installs or removes the hook block of a settings file the owner names.
Hooks never write to the hook output, never decide anything and never exit with the blocking code 2. Every
missing input or unexpected event is an explicit error; a state that cannot be established is ``unknown``.
See ``docs/engineering/agent-sessions.md``.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

VERSION = 1
PROVIDERS = ("claude", "codex")
SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
CLAUDE_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
                 "Notification", "Stop", "StopFailure", "SessionEnd")
CONTEXT_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "Stop"})  # project/branch/task are refreshed only here
HOOK_MARKER = "agent_sessions.py hook"
ASK_TOOL = "AskUserQuestion"
HOOK_TIMEOUT_SECONDS = 10
PROBE_TIMEOUT_SECONDS = 5


class SessionError(RuntimeError):
    """A required input is missing or invalid, or the registry cannot be read or written; the message names it."""


def _stamp(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(value: Any) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SessionError(f"invalid timestamp {value!r}") from exc


# ---- status rules -----------------------------------------------------------------------------------

def claude_transition(previous: dict | None, event: dict) -> tuple[str, dict]:
    """``(state, detail)`` after a Claude Code hook event. Unknown events are errors, never ignored."""
    name = event.get("hook_event_name")
    tool = event.get("tool_name")
    state = previous.get("state") if previous else None
    waiting_tool = (previous or {}).get("detail", {}).get("tool")
    if name == "SessionStart":
        return "idle", {}
    if name == "UserPromptSubmit":
        return "working", {}
    if name == "PreToolUse":
        if tool == ASK_TOOL:
            return "waiting-input", {"tool": tool}
        return (state, previous["detail"]) if state == "waiting-permission" else ("working", {})
    if name == "PostToolUse":
        if state in ("waiting-permission", "waiting-input") and waiting_tool is not None and tool != waiting_tool:
            return state, previous["detail"]  # another tool's event never clears the wait
        return "working", {}
    if name == "PermissionRequest":
        return "waiting-permission", {"tool": tool}
    if name == "Notification":
        kind = event.get("notification_type")
        if kind == "permission_prompt":
            return "waiting-permission", {"tool": waiting_tool if state == "waiting-permission" else None}
        if kind in ("idle_prompt", "elicitation_dialog"):
            return "waiting-input", {"notification": kind}
        return (state or "unknown"), (previous or {}).get("detail", {})
    if name == "Stop":
        return "idle", {}
    if name == "StopFailure":
        return "limit-or-error", {"error": str(event.get("error") or event.get("error_type") or "unknown")}
    if name == "SessionEnd":
        return "ended", {"reason": str(event.get("reason") or "unknown")}
    raise SessionError(f"unknown Claude Code hook event {name!r}; expected one of {', '.join(CLAUDE_EVENTS)}")


def codex_transition(event: dict) -> tuple[str, dict]:
    if event.get("type") != "agent-turn-complete":
        raise SessionError(f"unsupported Codex notification {event.get('type')!r}: only agent-turn-complete is reported by Codex")
    return "idle", {"codex": "turn-complete"}


# ---- processes and git ------------------------------------------------------------------------------

def process_started(pid: int) -> str | None:
    """The process start time text, ``None`` when no such process exists; an unusable ``ps`` raises."""
    try:
        done = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], text=True, capture_output=True,
                              check=False, timeout=PROBE_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SessionError(f"cannot read the start time of process {pid}: {exc}") from exc
    text = done.stdout.strip()
    if done.returncode and not text and not done.stderr.strip():
        return None
    if done.returncode:
        raise SessionError(f"ps failed for process {pid}: {done.stderr.strip()}")
    return text or None


def liveness(pid: int | None, started: str | None, *, probe: Callable[[int], str | None] = process_started) -> str:
    """``alive``, ``gone`` (verified) or ``unknown`` (the check itself failed). A failed check never ends a session."""
    if not isinstance(pid, int):
        return "unknown"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "gone"
    except PermissionError:
        pass  # exists, owned by another user
    except OSError:
        return "unknown"
    if started is None:
        return "alive"
    try:
        current = probe(pid)
    except SessionError:
        return "unknown"
    if current is None:
        return "gone"
    return "alive" if current == started else "gone"  # another start time: the pid was reused


def git_context(cwd: str | None) -> dict[str, str | None]:
    """Project top level, branch and task name for a working directory; unknown parts are ``None``, never guessed."""
    empty: dict[str, str | None] = {"project": None, "branch": None, "task": None}
    if not cwd or not Path(cwd).is_dir():
        return empty
    try:
        done = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel", "--abbrev-ref", "HEAD"], text=True,
                              capture_output=True, check=False, timeout=PROBE_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return empty
    lines = done.stdout.splitlines()
    if done.returncode or len(lines) != 2:
        return empty
    top, branch = lines
    return {"project": top, "branch": None if branch == "HEAD" else branch, "task": Path(top).name}


# ---- registry ---------------------------------------------------------------------------------------

def session_file(state_dir: Path, provider: str, session_id: str) -> Path:
    if provider not in PROVIDERS:
        raise SessionError(f"unknown provider {provider!r}")
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise SessionError(f"session id {session_id!r} is missing or not a safe file name")
    return state_dir / f"{provider}-{session_id}.json"


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    try:
        handle = open(path.with_suffix(".lock"), "a")
    except OSError as exc:
        raise SessionError(f"session lock {path.with_suffix('.lock')} cannot be opened: {exc}") from exc
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        handle.close()


def read_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"session record {path} is unreadable ({exc}); delete it to reset") from exc
    if not isinstance(value, dict) or value.get("version") != VERSION:
        raise SessionError(f"session record {path} is not a version {VERSION} record; delete it to reset")
    return value


def _write(path: Path, record: dict) -> None:
    try:
        fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except OSError as exc:
        raise SessionError(f"session record {path} cannot be written: {exc}") from exc


def ingest(state_dir: Path, provider: str, event: dict, *, pid: int, now: datetime | None = None,
           started: Callable[[int], str | None] = process_started) -> dict:
    """Apply one event to its session record and return the record."""
    if not state_dir.is_dir():
        raise SessionError(f"--state-dir {state_dir} does not exist")
    if provider == "claude":
        session_id, cwd = event.get("session_id"), event.get("cwd")
    elif provider == "codex":
        session_id, cwd = event.get("thread-id") or event.get("thread_id"), event.get("cwd")
    else:
        raise SessionError(f"unknown provider {provider!r}")
    path = session_file(state_dir, provider, session_id)
    with _locked(path):
        previous = read_record(path)
        state, detail = claude_transition(previous, event) if provider == "claude" else codex_transition(event)
        stamp = _stamp(now)
        record = dict(previous) if previous else {"version": VERSION, "provider": provider, "session_id": session_id,
                                                  "pid": pid, "pid_started": started(pid), "state_since": stamp}
        if previous and previous.get("pid") != pid:
            record.update(pid=pid, pid_started=started(pid))
        event_name = event.get("hook_event_name") or event.get("type")
        if previous is None or event_name in CONTEXT_EVENTS or provider == "codex":
            record.update(cwd=cwd, **git_context(cwd))
        if previous is None or previous.get("state") != state:
            record["state_since"] = stamp
        record.update(state=state, detail=detail, last_event=event_name, updated_at=stamp)
        _write(path, record)
    return record


def view(record: dict, *, now: datetime, stale_after: int, probe: Callable[[int], str | None] = process_started) -> dict:
    """The record as a viewer should show it: liveness applied, silence reported as unknown."""
    shown = {key: record.get(key) for key in ("provider", "session_id", "pid", "project", "branch", "task", "cwd",
                                              "state", "state_since", "updated_at", "last_event", "detail")}
    shown["recorded_state"] = record.get("state")
    if record.get("state") == "ended":
        shown["liveness"] = "ended"
        return shown
    shown["liveness"] = liveness(record.get("pid"), record.get("pid_started"), probe=probe)
    if shown["liveness"] == "gone":
        shown.update(state="ended", detail={"reason": "process-gone"}, state_since=shown["updated_at"])
        return shown
    silent = int((now - _parse(record["updated_at"])).total_seconds())
    if silent > stale_after:
        shown.update(state="unknown", detail={"reason": f"silent for {silent // 60} min", "last_state": record.get("state")})
    return shown


def list_sessions(state_dir: Path, *, now: datetime, stale_after: int, ended_keep: int,
                  probe: Callable[[int], str | None] = process_started) -> list[dict]:
    if not state_dir.is_dir():
        raise SessionError(f"session registry {state_dir} does not exist")
    shown = []
    for path in sorted(state_dir.glob("*.json")):
        record = read_record(path)
        item = view(record, now=now, stale_after=stale_after, probe=probe)
        if item["state"] == "ended" and (now - _parse(item["state_since"])).total_seconds() > ended_keep:
            continue
        shown.append(item)
    return shown


# ---- hook installation ------------------------------------------------------------------------------

def hook_command(script: Path, state_dir: Path, provider: str = "claude") -> str:
    return f"{sys.executable} {script} hook --provider {provider} --state-dir {state_dir}"


def hooks_block(script: Path, state_dir: Path) -> dict[str, list]:
    entry = {"hooks": [{"type": "command", "command": hook_command(script, state_dir), "timeout": HOOK_TIMEOUT_SECONDS}]}
    return {event: [entry] for event in CLAUDE_EVENTS}


def _is_ours(entry: Any) -> bool:
    return isinstance(entry, dict) and any(isinstance(h, dict) and HOOK_MARKER in str(h.get("command", ""))
                                           for h in entry.get("hooks", []) if isinstance(entry.get("hooks"), list))


def edit_settings(path: Path, script: Path, state_dir: Path, *, remove: bool) -> str:
    """Merge (or remove) the session hooks in the named settings file; idempotent, never overwrites a foreign hook."""
    try:
        settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise SessionError(f"settings file {path} is not valid JSON ({exc}); not modified") from exc
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
        raise SessionError(f"settings file {path}: 'hooks' is not an object; not modified")
    hooks = settings.setdefault("hooks", {})
    wanted = hooks_block(script, state_dir)
    changed = False
    for event in CLAUDE_EVENTS:
        entries = hooks.get(event, [])
        if not isinstance(entries, list):
            raise SessionError(f"settings file {path}: hooks.{event} is not a list; not modified")
        ours = [e for e in entries if _is_ours(e)]
        if remove:
            if ours:
                hooks[event] = [e for e in entries if not _is_ours(e)]
                changed = True
            continue
        if ours and ours != wanted[event]:
            raise SessionError(f"settings file {path} already has different session hooks for {event}; remove them first")
        if not ours:
            hooks[event] = [*entries, *wanted[event]]
            changed = True
    if not remove or changed:
        hooks_clean = {k: v for k, v in hooks.items() if v}
        settings["hooks"] = hooks_clean
        if not hooks_clean:
            del settings["hooks"]
    if changed:
        _write_settings(path, settings)
    return "changed" if changed else "unchanged"


def _write_settings(path: Path, settings: dict) -> None:
    try:
        fd, temporary = tempfile.mkstemp(prefix=path.name, dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    except OSError as exc:
        raise SessionError(f"settings file {path} cannot be written: {exc}") from exc


# ---- CLI --------------------------------------------------------------------------------------------

def _read_event(args: argparse.Namespace) -> dict:
    raw = args.payload_json if args.payload_json is not None else sys.stdin.read()
    try:
        event = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SessionError(f"hook payload is not valid JSON: {exc.msg}") from exc
    if not isinstance(event, dict):
        raise SessionError("hook payload must be a JSON object")
    return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent session registry")
    sub = parser.add_subparsers(dest="command", required=True)
    hook = sub.add_parser("hook", help="ingest one hook event (never blocks the session)")
    hook.add_argument("--provider", required=True, choices=PROVIDERS)
    hook.add_argument("--state-dir", required=True, type=Path)
    hook.add_argument("--payload-json", help="event JSON (Codex passes it as an argument); default: stdin")
    show = sub.add_parser("list", help="print the registry with liveness")
    show.add_argument("--state-dir", required=True, type=Path)
    show.add_argument("--stale-after", required=True, type=int, help="seconds without events after which a session is unknown")
    show.add_argument("--ended-keep", required=True, type=int, help="seconds an ended session stays listed")
    show.add_argument("--json", action="store_true")
    install = sub.add_parser("hooks", help="render, install or remove the Claude Code hooks")
    install.add_argument("--state-dir", required=True, type=Path)
    mode = install.add_mutually_exclusive_group(required=True)
    mode.add_argument("--print", action="store_true")
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--remove", action="store_true")
    install.add_argument("--settings", type=Path, help="settings file to edit (required with --install/--remove)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 2 and (argv if argv is not None else sys.argv[1:])[:1] == ["hook"]:
            return 1  # argparse exits 2, the blocking hook code; a broken hook command must not block the session
        raise
    script = Path(__file__).resolve()
    try:
        if args.command == "hook":
            ingest(args.state_dir, args.provider, _read_event(args), pid=os.getppid())
            return 0  # nothing on stdout: a hook never steers the session
        if args.command == "list":
            if args.stale_after < 1 or args.ended_keep < 1:
                raise SessionError("--stale-after and --ended-keep must be positive")
            sessions = list_sessions(args.state_dir, now=datetime.now(timezone.utc), stale_after=args.stale_after,
                                     ended_keep=args.ended_keep)
            if args.json:
                print(json.dumps(sessions, sort_keys=True))
            for item in sessions if not args.json else []:
                print(f"{item['provider']} {item['session_id']} pid {item['pid']} [{item['state']}] "
                      f"{item.get('branch') or '-'} {item.get('project') or '-'} since {item['state_since']}")
            return 0
        if args.print:
            print(json.dumps({"hooks": hooks_block(script, args.state_dir)}, indent=2))
            return 0
        if args.settings is None:
            raise SessionError("--settings PATH is required with --install and --remove")
        print(f"{args.settings}: {edit_settings(args.settings, script, args.state_dir, remove=args.remove)}")
        return 0
    except SessionError as exc:
        print(f"agent sessions: {exc}", file=sys.stderr)
        return 1 if args.command == "hook" else 2  # a hook failure is non-blocking (never exit 2)


if __name__ == "__main__":
    raise SystemExit(main())
