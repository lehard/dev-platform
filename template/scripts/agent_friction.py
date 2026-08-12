from __future__ import annotations

import argparse
import contextlib
import hashlib
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

from _platform_common import atomic_write_text, cooperative_umask, current_worktree_root, ensure_shared_path, main_root, read_platform_config, utc_now


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
FINGERPRINT_PREFIX = "dev-platform-friction"


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
    ensure_shared_path(path.parent)
    with path.open("a+", encoding="utf-8") as lock_file:
        ensure_shared_path(path)
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def atomic_write_json(path: Path, payload: dict) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def current_branch() -> str:
    result = subprocess.run(["git", "branch", "--show-current"], cwd=current_worktree_root(), text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def current_head(root: Path) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _unknown_run_provenance(role: str) -> dict:
    return {"source_issue": None, "change": None, "role": role, "supervisor": None, "participant": None}


def _current_run_provenance(participant_role: str) -> dict:
    """Bounded, truthful execution provenance for one friction event.

    Reuses the existing model-routing record instead of a second run
    database (adopt-gh-aw-process-automation, tasks 6.2/6.6). ``participant_role``
    is the only thing the caller asserts (which participant this finding is
    about); the actual provider/model identity is read back from the
    machine-owned routing record, not trusted as free-form self-identification.
    A missing/unreadable route, or an executor role with no confirmed
    execution yet, degrades to an explicit unknown rather than a guess.
    """
    if participant_role not in ("supervisor", "executor", "unknown"):
        participant_role = "unknown"
    if participant_role == "unknown":
        return _unknown_run_provenance("unknown")
    try:
        import model_routing
    except ImportError:
        return _unknown_run_provenance(participant_role)
    try:
        route, _ = model_routing._read_route(current_worktree_root())
    except Exception:
        return _unknown_run_provenance(participant_role)
    participant = None
    if participant_role == "executor" and isinstance(route.execution, dict):
        participant = route.execution.get("participant")
    return {
        "source_issue": route.source_issue,
        "change": route.change,
        "role": participant_role,
        "supervisor": route.supervisor or None,
        "participant": participant,
    }


def cmd_record(args: argparse.Namespace) -> int:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        ensure_shared_path(path)
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
        "run": _current_run_provenance(args.participant_role),
    }
    encoded = json.dumps(event, ensure_ascii=False, sort_keys=True)
    with friction_lock():
        with path.open("a", encoding="utf-8") as fh:
            ensure_shared_path(path)
            fh.write(encoded + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    print(f"Recorded friction candidate {event['id']}: {args.scope}/{args.category} severity={args.severity}")
    result = route_event(event)
    if result["status"] == "pending":
        print(f"WARNING: friction routing is pending for {event['id']}: {result['detail']}")
    else:
        print(f"Routed friction candidate {event['id']} to {result['repository']}#{result['issue_number']}")
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
            event.setdefault("run", _unknown_run_provenance("unknown"))
            if cutoff is None or parse_time(event["at"]) >= cutoff:
                events.append(event)
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            continue
    return events


def read_state() -> dict:
    path = state_path()
    if not path.exists():
        return {"version": 2, "reviewed_count": 0, "routes": {}, "checkpoints": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid friction review state: {exc}") from exc
    reviewed = payload.get("reviewed_count", 0)
    if not isinstance(reviewed, int) or reviewed < 0:
        raise SystemExit("Invalid friction review state: reviewed_count must be a non-negative integer")
    if not isinstance(payload.get("routes", {}), dict):
        raise SystemExit("Invalid friction routing state: routes must be an object")
    if not isinstance(payload.get("checkpoints", {}), dict):
        raise SystemExit("Invalid friction checkpoint state: checkpoints must be an object")
    payload.setdefault("version", 2)
    payload.setdefault("routes", {})
    payload.setdefault("checkpoints", {})
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


def sanitize_for_route(value: object, max_length: int = 500) -> str:
    """Return a bounded public representation without trusting legacy events."""
    text = " ".join(str(value or "").split())
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        return "[REDACTED]"
    return sanitize(text)[:max_length] or "[not supplied]"


def origin_repository() -> str:
    root = current_worktree_root()
    result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError("current repository has no readable origin remote")
    remote = result.stdout.strip().removesuffix(".git").removesuffix("/")
    match = re.fullmatch(r"(?:[^@]+@)?github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", remote)
    if match:
        return f"{match.group(1)}/{match.group(2)}".lower()
    match = re.fullmatch(r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", remote)
    if match:
        return f"{match.group(1)}/{match.group(2)}".lower()
    raise RuntimeError("origin must be a standard GitHub owner/repository remote")


def destination_for(event: dict) -> str:
    if event.get("scope") == "project":
        return origin_repository()
    if event.get("scope") == "platform":
        config = read_platform_config(main_root())
        return str(config.get("promotion", {}).get("repo", "lehard/dev-platform")).lower()
    raise RuntimeError("friction event has an unsupported scope")


def fingerprint_for(event: dict, repository: str) -> str:
    """Identity intentionally excludes raw observation, evidence and proposal."""
    category = re.sub(r"[^a-z0-9._-]+", "-", str(event.get("category", "unknown")).lower()).strip("-")
    identity = f"v1|{repository.lower()}|{event.get('scope')}|{category or 'unknown'}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def marker_for(fingerprint: str) -> str:
    return f"<!-- {FINGERPRINT_PREFIX}:{fingerprint} -->"


def gh(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *command], cwd=current_worktree_root(), text=True, capture_output=True)


def gh_json(command: list[str]) -> object:
    result = gh(command)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "GitHub CLI request failed").strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub CLI returned invalid JSON") from exc


def _provenance_line(event: dict) -> str | None:
    """One bounded, sanitized line naming the participant a finding concerns.

    Deliberately omits the execution identifier (thread/agent id) and any
    other machine-local detail -- those stay in the local friction log only
    (adopt-gh-aw-process-automation, task 6.7). This is occurrence metadata,
    not part of the dedupe identity (see fingerprint_for).
    """
    run = event.get("run") or {}
    role = run.get("role")
    if role not in ("supervisor", "executor"):
        return None
    who = (run.get("participant") if role == "executor" else run.get("supervisor")) or {}
    model = who.get("model") or {}
    provider = sanitize_for_route(who.get("provider"), 32)
    model_value = sanitize_for_route(model.get("value"), 64)
    model_source = sanitize_for_route(model.get("source"), 32)
    return f"- Participant: `{role}` / provider `{provider}` / model `{model_value}` ({model_source})"


def route_body(event: dict, fingerprint: str, *, occurrence: bool) -> str:
    provenance_line = _provenance_line(event)
    lines = [
        marker_for(fingerprint),
        "## Sanitized process friction occurrence" if occurrence else "## Sanitized process friction",
        "",
        f"- Scope: `{sanitize_for_route(event.get('scope'), 32)}`",
        f"- Category: `{sanitize_for_route(event.get('category'), 100)}`",
        f"- Severity: `{sanitize_for_route(event.get('severity', 'medium'), 20)}`",
        f"- Fingerprint: `{fingerprint}`",
        f"- Recorded at: `{sanitize_for_route(event.get('at'), 64)}`",
        *([provenance_line] if provenance_line else []),
        "",
        "### Observation",
        sanitize_for_route(event.get("observation")),
        "",
        "### Hypothesis",
        sanitize_for_route(event.get("hypothesis")),
        "",
        "### Proposed change",
        sanitize_for_route(event.get("proposal")),
        "",
        "> Raw evidence is deliberately retained only in the machine-local friction log.",
    ]
    return "\n".join(lines)


def route_event(event: dict) -> dict:
    """Upsert one sanitized process issue and leave failures retryable locally."""
    event_id = str(event.get("id") or "")
    if not event_id:
        return {"status": "pending", "detail": "event has no id"}
    try:
        if shutil.which("gh") is None:
            raise RuntimeError("GitHub CLI is unavailable")
        auth = gh(["auth", "status"])
        if auth.returncode:
            raise RuntimeError("GitHub CLI is not authenticated")
        repository = destination_for(event)
        fingerprint = fingerprint_for(event, repository)
        marker = marker_for(fingerprint)
        # HTML comments are intentionally not reliably indexed by GitHub search.
        # Read the bounded open-issue set and inspect the exact marker ourselves.
        listed = gh_json(["api", f"repos/{repository}/issues?state=open&per_page=100"])
        issue_number = None
        if isinstance(listed, list):
            for issue in listed:
                if isinstance(issue, dict) and marker in str(issue.get("body", "")):
                    issue_number = issue.get("number")
                    break
        if isinstance(issue_number, int):
            result = gh([
                "api", "--method", "POST", f"repos/{repository}/issues/{issue_number}/comments",
                "-f", f"body={route_body(event, fingerprint, occurrence=True)}",
            ])
            if result.returncode:
                raise RuntimeError((result.stderr or result.stdout or "GitHub issue update failed").strip())
        else:
            created = gh_json([
                "api", "--method", "POST", f"repos/{repository}/issues",
                "-f", f"title=[process-friction] {sanitize_for_route(event.get('category'), 100)}",
                "-f", f"body={route_body(event, fingerprint, occurrence=False)}",
            ])
            if not isinstance(created, dict) or not isinstance(created.get("number"), int):
                raise RuntimeError("GitHub did not return a created issue number")
            issue_number = created["number"]
        route = {
            "status": "routed", "repository": repository, "issue_number": issue_number,
            "fingerprint": fingerprint, "routed_at": utc_now(),
        }
    except RuntimeError as exc:
        route = {"status": "pending", "detail": sanitize_for_route(str(exc), 240), "last_attempt_at": utc_now()}
    with friction_lock():
        state = read_state()
        state["routes"][event_id] = route
        atomic_write_json(state_path(), state)
    return route


def route_pending() -> dict:
    state = read_state()
    routes = state.get("routes", {})
    pending = [event for event in read_events(None) if routes.get(str(event.get("id")), {}).get("status") != "routed"]
    routed = 0
    failures = 0
    for event in pending:
        result = route_event(event)
        routed += result["status"] == "routed"
        failures += result["status"] != "routed"
    return {"pending": len(pending), "routed": routed, "failures": failures}


def cmd_route_pending(_: argparse.Namespace) -> int:
    result = route_pending()
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Record the post-task retrospective result: zero or more findings.

    ``--result none`` means the retrospective actually ran and found no new
    meaningful unresolved/unrecorded friction. ``--result <id>``/``--event
    <id>`` (repeatable) reference existing recorded friction events this
    retrospective classified as new meaningful findings; already-resolved or
    already-recorded candidates are simply not referenced here.
    """
    branch = current_branch()
    root = current_worktree_root()
    explicit_none = args.result == "none"
    event_ids: list[str] = list(dict.fromkeys([*args.events, *([args.result] if args.result not in (None, "none") else [])]))
    if explicit_none and event_ids:
        raise SystemExit("--result none cannot be combined with recorded findings; a clean retrospective references zero events")
    if not explicit_none and not event_ids:
        raise SystemExit(
            "checkpoint requires --result none for a clean retrospective, or --result/--event with one or more recorded finding ids"
        )
    known_ids = {str(event.get("id")) for event in read_events(None)}
    missing = [event_id for event_id in event_ids if event_id not in known_ids]
    if missing:
        raise SystemExit(f"Friction event not found: {', '.join(missing)}")
    checkpoint = {
        "result": "events" if event_ids else "none",
        "event_ids": event_ids,
        "at": utc_now(),
        "branch": branch,
        "head": current_head(root),
    }
    with friction_lock():
        state = read_state()
        state["checkpoints"][branch] = checkpoint
        atomic_write_json(state_path(), state)
    print(json.dumps({"status": "recorded", "checkpoint": checkpoint}, ensure_ascii=False))
    return 0


def cmd_assert_checkpoint(args: argparse.Namespace) -> int:
    require_checkpoint(args.branch or current_branch(), current_worktree_root())
    return 0


def require_checkpoint(branch: str, root: Path | None = None) -> None:
    """Reject a missing, malformed or stale post-task retrospective receipt.

    Freshness reuses the task's own branch/head instead of a second identity
    system: a retrospective recorded against an earlier head no longer
    satisfies completion once the branch has moved on.
    """
    checkpoint = read_state().get("checkpoints", {}).get(branch)
    if not isinstance(checkpoint, dict) or checkpoint.get("result") not in ("none", "events"):
        raise SystemExit(
            "Completion friction retrospective is required for this non-trivial platform task. "
            "Run `python3 scripts/agent_friction.py checkpoint --result none` after reviewing the task for "
            "unresolved friction, or `--event <id>` (repeatable) for each recorded meaningful finding."
        )
    if checkpoint.get("result") == "events":
        event_ids = checkpoint.get("event_ids") or []
        if not event_ids:
            raise SystemExit("Retrospective checkpoint declares findings but records no event ids; rerun the retrospective.")
        known_ids = {str(event.get("id")) for event in read_events(None)}
        missing = [event_id for event_id in event_ids if event_id not in known_ids]
        if missing:
            raise SystemExit(
                f"Retrospective checkpoint references unknown friction event id(s): {', '.join(missing)}; rerun the retrospective."
            )
    resolved_root = root if root is not None else current_worktree_root()
    current = current_head(resolved_root)
    if current is None:
        raise SystemExit("Could not determine the current task head to verify retrospective freshness.")
    if checkpoint.get("head") != current:
        raise SystemExit(
            "Completion friction retrospective is stale for the current task execution state "
            f"(recorded head {checkpoint.get('head')!r}, current head {current!r}). "
            "Run a fresh `python3 scripts/agent_friction.py checkpoint ...` after reviewing the latest changes."
        )


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
    cooperative_umask()
    parser = argparse.ArgumentParser(description="Record high-signal agent friction and route sanitized process evidence safely.")
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
    p.add_argument(
        "--participant-role", choices=("supervisor", "executor", "unknown"), default="unknown",
        help="which participant this finding concerns; identity is read back from the current routing record, not self-reported",
    )
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("route-pending", help="retry locally retained friction events without failing the caller")
    p.set_defaults(func=cmd_route_pending)

    p = sub.add_parser("checkpoint", help="resolve the required post-task friction retrospective")
    p.add_argument("--result", help="'none' for a clean retrospective, or a recorded friction event id")
    p.add_argument("--event", dest="events", action="append", default=[], help="repeatable: another recorded finding id from this retrospective")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("assert-checkpoint", help="fail unless the current task checkpoint is resolved")
    p.add_argument("--branch")
    p.set_defaults(func=cmd_assert_checkpoint)

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
