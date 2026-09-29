#!/usr/bin/env python3
"""Bounded, machine-local retrospective receipt for one Business Requirement."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import agent_friction
import requirement_intake
from _platform_common import atomic_write_text, current_worktree_root, main_root, utc_now


class RequirementRetrospectiveError(RuntimeError):
    pass


def _identity(requirement: str, parent: dict[str, Any]) -> dict[str, Any]:
    number = requirement_intake.issue_ref(requirement)[1]
    body = str(parent.get("body") or "")
    children = requirement_intake.parse_requirement_body(body)["children"]
    if not children or len(children) != len(set(children)):
        raise RequirementRetrospectiveError("Requirement retrospective needs an unambiguous, nonempty child set")
    return {
        "requirement": requirement,
        "number": number,
        "parent_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "children": children,
    }


def _receipt_path(root: Path, number: int) -> Path:
    return root / ".claude" / "requirement-retrospective" / f"requirement-{number}.json"


def _check_events(requirement: str, event_ids: list[str]) -> None:
    known = {str(event.get("id")): event for event in agent_friction.read_events()}
    for event_id in event_ids:
        event = known.get(event_id)
        if event is None:
            raise RequirementRetrospectiveError(f"unknown friction event {event_id}; record the finding first")
        if event.get("task") != requirement:
            raise RequirementRetrospectiveError(
                f"friction event {event_id} is not attributed to {requirement}; record it with --task {requirement}"
            )


def checkpoint(root: Path, *, requirement: str, result: str, event_ids: list[str], review_note: str) -> dict[str, Any]:
    if result not in ("none", "findings"):
        raise RequirementRetrospectiveError("result must be none or findings")
    if (result == "none") != (not event_ids):
        raise RequirementRetrospectiveError("none requires no events; findings requires at least one event")
    if len(event_ids) != len(set(event_ids)):
        raise RequirementRetrospectiveError("duplicate friction event id")
    review_note = agent_friction.normalize_text(review_note, "review note", 500)
    parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
    identity = _identity(requirement, parent)
    _check_events(requirement, event_ids)
    unlinked = agent_friction.unlinked_retrospective_signals(requirement, event_ids)
    if unlinked:
        raise RequirementRetrospectiveError(agent_friction.retrospective_signal_instruction(unlinked))
    receipt = {"version": 1, **identity, "result": result, "event_ids": event_ids, "review_note": review_note, "recorded_at": utc_now()}
    path = _receipt_path(root, identity["number"])
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"status": "recorded", "requirement": requirement, "result": result, "event_ids": event_ids, "receipt": str(path)}


def require_checkpoint(root: Path, *, requirement: str, parent: dict[str, Any] | None = None) -> dict[str, Any]:
    parent = parent or requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(requirement))
    identity = _identity(requirement, parent)
    path = _receipt_path(root, identity["number"])
    instruction = f"run `python3 scripts/requirement_retrospective.py checkpoint --requirement {requirement} --result none --review-note TEXT` after the full-path review, or record findings and pass their --event ids"
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RequirementRetrospectiveError(f"Requirement retrospective is missing or unreadable; {instruction}") from exc
    if not isinstance(receipt, dict) or receipt.get("version") != 1:
        raise RequirementRetrospectiveError(f"Requirement retrospective receipt is unsupported; {instruction}")
    if any(receipt.get(key) != value for key, value in identity.items()):
        raise RequirementRetrospectiveError(f"Requirement retrospective is stale for current parent/children; {instruction}")
    result = receipt.get("result")
    events = receipt.get("event_ids")
    if result not in ("none", "findings") or not isinstance(events, list) or not all(isinstance(e, str) for e in events):
        raise RequirementRetrospectiveError(f"Requirement retrospective receipt is malformed; {instruction}")
    if (result == "none") != (not events) or len(events) != len(set(events)):
        raise RequirementRetrospectiveError(f"Requirement retrospective result is inconsistent; {instruction}")
    if not isinstance(receipt.get("review_note"), str) or not receipt["review_note"].strip():
        raise RequirementRetrospectiveError(f"Requirement retrospective path review is missing; {instruction}")
    _check_events(requirement, events)
    unlinked = agent_friction.unlinked_retrospective_signals(requirement, events)
    if unlinked:
        raise RequirementRetrospectiveError(agent_friction.retrospective_signal_instruction(unlinked))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a Business Requirement's bounded end-to-end retrospective")
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser("checkpoint")
    write.add_argument("--requirement", required=True)
    write.add_argument("--result", choices=("none", "findings"), required=True)
    write.add_argument("--event", action="append", default=[], dest="events")
    write.add_argument("--review-note", required=True, help="short factual Requirement path reviewed, including workarounds, overrides, recurrences and drift")
    review = sub.add_parser("review-path", help="show bounded full-Requirement review prompts and recorded signals")
    review.add_argument("--requirement", required=True)
    check = sub.add_parser("check")
    check.add_argument("--requirement", required=True)
    args = parser.parse_args()
    root = main_root()
    try:
        if args.command == "checkpoint":
            result = checkpoint(root, requirement=args.requirement, result=args.result, event_ids=args.events, review_note=args.review_note)
        elif args.command == "review-path":
            parent = requirement_intake.fetch_issue(root, *requirement_intake.issue_ref(args.requirement))
            identity = _identity(args.requirement, parent)
            result = {
                "requirement": args.requirement,
                "review": ["accepted intent and intake", "pre-authoring and handoff", "mandatory children",
                           "delivery actions, overrides, workarounds, recurrences and observed drift"],
                "children": identity["children"],
                "recorded_signals": [
                    {"id": str(event.get("id")), "triggers": sorted(agent_friction.RETROSPECTIVE_SIGNALS.intersection(event.get("triggers") or []))}
                    for event in agent_friction.current_retrospective_signals(args.requirement)
                ],
            }
        else:
            receipt = require_checkpoint(root, requirement=args.requirement)
            result = {"status": "ready", "requirement": args.requirement, "result": receipt["result"], "event_ids": receipt["event_ids"]}
    except (RequirementRetrospectiveError, requirement_intake.RequirementIntakeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
