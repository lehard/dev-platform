from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from _platform_common import main_root, read_platform_config, utc_now


DEFAULT_MIN_EVENTS = 5
SEVERITIES = ("low", "medium", "high", "critical")
TRIGGERS = (
    "user-correction",
    "repeated-error",
    "unsafe-near-miss",
    "undocumented-invariant",
    "excessive-retry",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S+"),
)


def local_path(key: str, default: str) -> Path:
    root = main_root()
    config = read_platform_config(root)
    relative = str(config.get("paths", {}).get(key, default))
    return (root / relative).resolve()


def log_path() -> Path:
    return local_path("friction_log", ".claude/agent-friction.jsonl")


def state_path() -> Path:
    return local_path("friction_state", ".claude/agent-friction-state.json")


def reports_dir() -> Path:
    return local_path("friction_reports", ".claude/reports/process-improvement")


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def normalize_text(value: str, field: str, max_length: int = 4000) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise SystemExit(f"{field} must not be empty")
    if len(normalized) > max_length:
        raise SystemExit(f"{field} exceeds {max_length} characters")
    for pattern in SECRET_PATTERNS:
        if pattern.search(normalized):
            raise SystemExit(f"{field} appears to contain a secret; redact it before recording friction")
    return normalized


@contextlib.contextmanager
def friction_lock() -> Iterator[None]:
    path = log_path().with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
        temporary = Path(fh.name)
    os.replace(temporary, path)


def current_branch() -> str:
    result = subprocess.run(["git", "branch", "--show-current"], cwd=main_root(), text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def cmd_record(args: argparse.Namespace) -> int:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    triggers = sorted(set(args.trigger or [args.category]))
    event = {
        "id": uuid.uuid4().hex[:12],
        "at": utc_now(),
        "branch": current_branch(),
        "task": normalize_text(args.task, "task", 300) if args.task else None,
        "category": normalize_text(args.category, "category", 100),
        "triggers": triggers,
        "severity": args.severity,
        "observation": normalize_text(args.observation, "observation"),
        "evidence": normalize_text(args.evidence, "evidence"),
        "hypothesis": normalize_text(args.hypothesis, "hypothesis"),
        "scope": args.scope,
        "proposal": normalize_text(args.proposal, "proposal"),
    }
    encoded = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with friction_lock():
        with path.open("a", encoding="utf-8") as fh:
            fh.write(encoded + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    print(f"Recorded friction candidate {event['id']}: {args.scope}/{args.category} severity={args.severity}")
    return 0


def read_events(days: int | None = None) -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days is not None else None
    events: list[dict] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            event.setdefault("id", f"legacy-{index}")
            event.setdefault("severity", "medium")
            event.setdefault("triggers", [event.get("category", "legacy")])
            if cutoff is None or parse_time(event["at"]) >= cutoff:
                events.append(event)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            continue
    return events


def read_state() -> dict:
    path = state_path()
    if not path.exists():
        return {"version": 1, "reviewed_count": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid friction review state: {exc}") from exc
    reviewed = payload.get("reviewed_count", 0)
    if not isinstance(reviewed, int) or reviewed < 0:
        raise SystemExit("Invalid friction review state: reviewed_count must be a non-negative integer")
    return payload


def pending_batch(min_events: int = DEFAULT_MIN_EVENTS) -> dict:
    if min_events < 1:
        raise SystemExit("--min-events must be at least 1")
    events = read_events(None)
    state = read_state()
    reviewed = int(state.get("reviewed_count", 0))
    if reviewed > len(events):
        raise SystemExit("Friction review state is ahead of the event log")
    pending = events[reviewed:]
    urgent = any(event.get("severity") in {"high", "critical"} for event in pending)
    ready = len(pending) >= min_events or urgent
    return {
        "version": 1,
        "ready": ready,
        "reason": "urgent-event" if urgent else "minimum-events" if ready else "not-ready",
        "minimum_events": min_events,
        "total_events": len(events),
        "reviewed_count": reviewed,
        "pending_count": len(pending),
        "through_id": pending[-1].get("id") if ready and pending else None,
        "events": pending,
    }


def pending_markdown(batch: dict) -> str:
    lines = [
        "# Agent friction review batch",
        "",
        f"- Ready: {'yes' if batch['ready'] else 'no'}",
        f"- Reason: {batch['reason']}",
        f"- Pending: {batch['pending_count']}",
        f"- Minimum: {batch['minimum_events']}",
        f"- Through: {batch['through_id'] or '—'}",
        "",
        "Treat event hypotheses as unverified. Change persistent platform rules only after repeated evidence or one high/critical event with strong evidence.",
        "",
    ]
    for event in batch["events"]:
        lines += [
            f"## {event.get('id')} [{event.get('scope', 'unknown')}] {event.get('category', 'unknown')}",
            f"- Severity: {event.get('severity', 'medium')}",
            f"- Triggers: {', '.join(event.get('triggers', []))}",
            f"- Observation: {event.get('observation', '')}",
            f"- Evidence: {event.get('evidence', '')}",
            f"- Hypothesis: {event.get('hypothesis', '')}",
            f"- Proposal: {event.get('proposal', '')}",
            "",
        ]
    return "\n".join(lines)


def cmd_pending(args: argparse.Namespace) -> int:
    batch = pending_batch(args.min_events)
    print(json.dumps(batch, ensure_ascii=False, indent=2) if args.format == "json" else pending_markdown(batch))
    return 0


def mark_reviewed(through_id: str, report: str) -> dict:
    root = main_root().resolve()
    report_path = Path(report).expanduser()
    if not report_path.is_absolute():
        report_path = root / report_path
    report_path = report_path.resolve()
    if not report_path.is_file():
        raise SystemExit(f"Review report does not exist: {report_path}")
    try:
        report_relative = report_path.relative_to(root)
    except ValueError as exc:
        raise SystemExit("Review report must stay inside the repository root") from exc
    events = read_events(None)
    state = read_state()
    current = int(state.get("reviewed_count", 0))
    index = next((i for i, event in enumerate(events) if event.get("id") == through_id), None)
    if index is None:
        raise SystemExit(f"Unknown friction event id: {through_id}")
    new_count = index + 1
    if new_count < current:
        raise SystemExit("Refusing to move friction review cursor backwards")
    payload = {
        "version": 1,
        "reviewed_count": new_count,
        "last_reviewed_id": through_id,
        "last_reviewed_at": utc_now(),
        "last_report": str(report_relative),
    }
    with friction_lock():
        atomic_write_json(state_path(), payload)
    return payload


def cmd_mark_reviewed(args: argparse.Namespace) -> int:
    payload = mark_reviewed(args.through_id, args.report)
    print(json.dumps({"status": "marked", **payload}, ensure_ascii=False))
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    events = read_events(args.days)
    if not events:
        print(f"No friction events in the last {args.days} days.")
        return 0
    scope_counts = Counter(event.get("scope", "unknown") for event in events)
    category_counts = Counter(event.get("category", "unknown") for event in events)
    severity_counts = Counter(event.get("severity", "medium") for event in events)
    print(f"# Agent friction review — last {args.days} days\n")
    print(f"Events: {len(events)}")
    print("Scopes: " + ", ".join(f"{k}={v}" for k, v in sorted(scope_counts.items())))
    print("Categories: " + ", ".join(f"{k}={v}" for k, v in sorted(category_counts.items())))
    print("Severity: " + ", ".join(f"{k}={v}" for k, v in sorted(severity_counts.items())))
    print()
    for event in events:
        print(f"## {event.get('id')} [{event.get('scope')}] {event.get('category')}")
        print(f"- Severity: {event.get('severity', 'medium')}")
        print(f"- Observation: {event.get('observation')}")
        print(f"- Evidence: {event.get('evidence')}")
        print(f"- Hypothesis: {event.get('hypothesis')}")
        print(f"- Proposal: {event.get('proposal')}\n")
    return 0


def sanitize(value: str) -> str:
    value = re.sub(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    value = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[REDACTED]@", value)
    return value[:4000]


def choose_event(selector: str) -> dict:
    events = read_events(None)
    for event in events:
        if event.get("id") == selector:
            return event
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(events):
            return events[index - 1]
    raise SystemExit(f"Friction event not found: {selector}")


def cmd_promote(args: argparse.Namespace) -> int:
    event = choose_event(args.event)
    if event.get("scope") != "platform":
        raise SystemExit("Only scope=platform friction can be promoted to dev-platform.")
    config = read_platform_config(main_root())
    inbox_repo = str(config.get("promotion", {}).get("repo", "lehard/dev-platform"))
    project_slug = str(config.get("project_slug", "unknown-project"))
    title = f"[platform-candidate] {sanitize(str(event.get('proposal', event.get('category', 'friction'))))[:120]}"
    body = "\n".join(
        [
            "## Sanitized platform candidate",
            "",
            f"- Source project: `{project_slug}`",
            f"- Local event id: `{event.get('id')}`",
            f"- Category: `{event.get('category')}`",
            f"- Severity: `{event.get('severity', 'medium')}`",
            f"- Recorded at: `{event.get('at')}`",
            "",
            "### Observation",
            sanitize(str(event.get("observation", ""))),
            "",
            "### Hypothesis",
            sanitize(str(event.get("hypothesis", ""))),
            "",
            "### Proposed reusable change",
            sanitize(str(event.get("proposal", ""))),
            "",
            "> Evidence is intentionally omitted from cross-project promotion to reduce leakage of machine-local, customer, credential, or domain-sensitive context. Review the source event locally if needed.",
        ]
    )
    if args.dry_run:
        print(title)
        print(body)
        return 0
    if not shutil.which("gh"):
        raise SystemExit("Promotion requires GitHub CLI (gh). Nothing was uploaded.")
    auth = subprocess.run(["gh", "auth", "status"], text=True, capture_output=True)
    if auth.returncode != 0:
        raise SystemExit("GitHub CLI is not authenticated. Nothing was uploaded.")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(body)
        body_path = fh.name
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", inbox_repo, "--title", title, "--body-file", body_path],
            text=True,
            capture_output=True,
            check=True,
        )
    finally:
        Path(body_path).unlink(missing_ok=True)
    print(result.stdout.strip())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Record high-signal agent friction, review evidence in batches, and deliberately promote reusable candidates.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("record")
    p.add_argument("--category", required=True)
    p.add_argument("--trigger", action="append", choices=TRIGGERS)
    p.add_argument("--severity", choices=SEVERITIES, default="medium")
    p.add_argument("--observation", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--scope", choices=["project", "platform"], required=True)
    p.add_argument("--proposal", required=True)
    p.add_argument("--task")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("pending")
    p.add_argument("--min-events", type=int, default=DEFAULT_MIN_EVENTS)
    p.add_argument("--format", choices=["json", "markdown"], default="json")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("mark-reviewed")
    p.add_argument("--through-id", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(func=cmd_mark_reviewed)

    p = sub.add_parser("review")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("promote")
    p.add_argument("event", help="event id or 1-based log index")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_promote)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
