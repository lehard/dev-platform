from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _platform_common import machine_path, main_root, utc_now


def log_path() -> Path:
    return machine_path("friction_log", main_root())


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def cmd_record(args: argparse.Namespace) -> int:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": utc_now(), "category": args.category, "observation": args.observation, "evidence": args.evidence, "hypothesis": args.hypothesis, "scope": args.scope, "proposal": args.proposal}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    print(f"Recorded friction candidate: {args.scope}/{args.category}")
    return 0


def read_events(days: int) -> list[dict]:
    path = log_path()
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if parse_time(event["at"]) >= cutoff:
                events.append(event)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return events


def cmd_review(args: argparse.Namespace) -> int:
    events = read_events(args.days)
    if not events:
        print(f"No friction events in the last {args.days} days.")
        return 0

    scope_counts = Counter(event.get("scope", "unknown") for event in events)
    category_counts = Counter(event.get("category", "unknown") for event in events)
    print(f"# Agent friction review — last {args.days} days\n")
    print(f"Events: {len(events)}")
    print("Scopes: " + ", ".join(f"{k}={v}" for k, v in sorted(scope_counts.items())))
    print("Categories: " + ", ".join(f"{k}={v}" for k, v in sorted(category_counts.items())))
    print()
    for index, event in enumerate(events, start=1):
        print(f"## {index}. [{event.get('scope')}] {event.get('category')}")
        print(f"- Observation: {event.get('observation')}")
        print(f"- Evidence: {event.get('evidence')}")
        print(f"- Hypothesis: {event.get('hypothesis')}")
        print(f"- Proposal: {event.get('proposal')}")
        print()
    platform = [event for event in events if event.get("scope") == "platform"]
    if platform:
        print("## Platform candidates")
        print("Review these against multiple projects before creating a dev-platform OpenSpec change:")
        for event in platform:
            print(f"- {event.get('proposal')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Record high-signal agent friction without creating a second backlog.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("record")
    p.add_argument("--category", required=True)
    p.add_argument("--observation", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--scope", choices=["project", "platform"], required=True)
    p.add_argument("--proposal", required=True)
    p.set_defaults(func=cmd_record)
    p = sub.add_parser("review")
    p.add_argument("--days", type=int, default=7)
    p.set_defaults(func=cmd_review)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
