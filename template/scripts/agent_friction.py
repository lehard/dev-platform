from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _platform_common import machine_path, main_root, read_platform_config, utc_now


def log_path() -> Path:
    return machine_path("friction_log", main_root())


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cmd_record(args: argparse.Namespace) -> int:
    path = log_path(); path.parent.mkdir(parents=True, exist_ok=True)
    event = {"id": uuid.uuid4().hex[:12], "at": utc_now(), "category": args.category, "observation": args.observation, "evidence": args.evidence, "hypothesis": args.hypothesis, "scope": args.scope, "proposal": args.proposal}
    with path.open("a", encoding="utf-8") as fh: fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"Recorded friction candidate {event['id']}: {args.scope}/{args.category}"); return 0


def read_events(days: int | None = None) -> list[dict]:
    path = log_path()
    if not path.exists(): return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days is not None else None
    events = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip(): continue
        try:
            event = json.loads(line); event.setdefault("id", f"legacy-{index}")
            if cutoff is None or parse_time(event["at"]) >= cutoff: events.append(event)
        except (json.JSONDecodeError, KeyError, ValueError): continue
    return events


def cmd_review(args: argparse.Namespace) -> int:
    events = read_events(args.days)
    if not events:
        print(f"No friction events in the last {args.days} days."); return 0
    scope_counts = Counter(event.get("scope", "unknown") for event in events); category_counts = Counter(event.get("category", "unknown") for event in events)
    print(f"# Agent friction review — last {args.days} days\n"); print(f"Events: {len(events)}")
    print("Scopes: " + ", ".join(f"{k}={v}" for k, v in sorted(scope_counts.items()))); print("Categories: " + ", ".join(f"{k}={v}" for k, v in sorted(category_counts.items()))); print()
    for event in events:
        print(f"## {event.get('id')} [{event.get('scope')}] {event.get('category')}")
        print(f"- Observation: {event.get('observation')}"); print(f"- Evidence: {event.get('evidence')}"); print(f"- Hypothesis: {event.get('hypothesis')}"); print(f"- Proposal: {event.get('proposal')}\n")
    return 0


def sanitize(value: str) -> str:
    value = re.sub(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    value = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[REDACTED]@", value)
    return value[:4000]


def choose_event(selector: str) -> dict:
    events = read_events(None)
    for event in events:
        if event.get("id") == selector: return event
    if selector.isdigit():
        index = int(selector)
        if 1 <= index <= len(events): return events[index - 1]
    raise SystemExit(f"Friction event not found: {selector}")


def cmd_promote(args: argparse.Namespace) -> int:
    event = choose_event(args.event)
    if event.get("scope") != "platform": raise SystemExit("Only scope=platform friction can be promoted to dev-platform.")
    config = read_platform_config(main_root()); inbox_repo = str(config.get("promotion", {}).get("repo", "lehard/dev-platform")); project_slug = str(config.get("project_slug", "unknown-project"))
    title = f"[platform-candidate] {sanitize(str(event.get('proposal', event.get('category', 'friction'))))[:120]}"
    body = "\n".join(["## Sanitized platform candidate", "", f"- Source project: `{project_slug}`", f"- Local event id: `{event.get('id')}`", f"- Category: `{event.get('category')}`", f"- Recorded at: `{event.get('at')}`", "", "### Observation", sanitize(str(event.get("observation", ""))), "", "### Hypothesis", sanitize(str(event.get("hypothesis", ""))), "", "### Proposed reusable change", sanitize(str(event.get("proposal", ""))), "", "> Evidence is intentionally omitted from cross-project promotion to reduce leakage of machine-local, customer, credential, or domain-sensitive context. Review the source event locally if needed."])
    if args.dry_run:
        print(title); print(body); return 0
    if not shutil.which("gh"): raise SystemExit("Promotion requires GitHub CLI (gh). Nothing was uploaded.")
    auth = subprocess.run(["gh", "auth", "status"], text=True, capture_output=True)
    if auth.returncode != 0: raise SystemExit("GitHub CLI is not authenticated. Nothing was uploaded.")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(body); body_path = fh.name
    try:
        result = subprocess.run(["gh", "issue", "create", "--repo", inbox_repo, "--title", title, "--body-file", body_path], text=True, capture_output=True, check=True)
    finally:
        Path(body_path).unlink(missing_ok=True)
    print(result.stdout.strip()); return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Record high-signal agent friction and deliberately promote reusable candidates."); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("record"); p.add_argument("--category", required=True); p.add_argument("--observation", required=True); p.add_argument("--evidence", required=True); p.add_argument("--hypothesis", required=True); p.add_argument("--scope", choices=["project", "platform"], required=True); p.add_argument("--proposal", required=True); p.set_defaults(func=cmd_record)
    p = sub.add_parser("review"); p.add_argument("--days", type=int, default=7); p.set_defaults(func=cmd_review)
    p = sub.add_parser("promote"); p.add_argument("event", help="event id or 1-based log index"); p.add_argument("--dry-run", action="store_true"); p.set_defaults(func=cmd_promote)
    args = parser.parse_args(); return args.func(args)


if __name__ == "__main__": raise SystemExit(main())
