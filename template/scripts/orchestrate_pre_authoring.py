#!/usr/bin/env python3
"""Thin resumable pre-authoring orchestrator.

Composes project_evidence.py (Project Evidence Snapshots) and add_intents.py
(ADD -> Intents -> OpenSpec handoff) into one status/decision surface that a
main agent can call repeatedly to find the next bounded step. It owns no
semantic authority and duplicates none of either module's freshness/gate
logic: it never drafts ADD content, decomposes intents, resolves a
consequential choice, or recomputes snapshot/ADD/intent identity itself. Each
call re-validates the actual artifact files with project_evidence.py's and
add_intents.py's own functions, so a stale upstream artifact is detected the
same way those modules already detect it -- this module only sequences that
detection into one resumable, human-mediated flow and records a small
machine-local, non-authoritative navigation receipt.

Directory layout per requirement id (default root: .claude/pre-authoring/<id>/):
    state.json      -- requirement identity + artifact paths (written once by init)
    snapshot.json   -- a Project Evidence Snapshot (project_evidence.py)
    add.json        -- an ADD document (add_intents.py)
    intents.json    -- an intent-set document (add_intents.py)
    handoff/<intent-or-group>.json -- OpenSpec authoring-input envelopes
    receipt.json    -- last computed status(), written for external inspection only

Nothing here is a second backlog or implementation-state machine: OpenSpec
authoring/lifecycle remains the only source of truth once a handoff envelope
exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import add_intents
import project_evidence
from _platform_common import atomic_write_text, current_worktree_root, utc_now

STATE_VERSION = 1
RECEIPT_VERSION = 1


class OrchestratorError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OrchestratorError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OrchestratorError(f"{label} is not valid JSON: {path}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def requirement_dir(base_dir: Path, requirement_id: str) -> Path:
    return base_dir / requirement_id


def default_base_dir(root: Path) -> Path:
    return root / ".claude" / "pre-authoring"


def state_path(directory: Path) -> Path:
    return directory / "state.json"


def snapshot_path(directory: Path) -> Path:
    return directory / "snapshot.json"


def add_path(directory: Path) -> Path:
    return directory / "add.json"


def intents_path(directory: Path) -> Path:
    return directory / "intents.json"


def handoff_dir(directory: Path) -> Path:
    return directory / "handoff"


def receipt_path(directory: Path) -> Path:
    return directory / "receipt.json"


def load_state(directory: Path) -> dict[str, Any]:
    return _load_json(state_path(directory), "pre-authoring state")


def init(
    root: Path,
    *,
    requirement_id: str,
    requirement_file: Path,
    target_repository: str,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Bind a requirement identity and scaffold its ADD. Safe to call once per requirement.

    Refuses to re-init over an existing state bound to different requirement
    content: a requirement id names one requirement, not a slot to overwrite.
    """
    base_dir = base_dir or default_base_dir(root)
    directory = requirement_dir(base_dir, requirement_id)
    if not requirement_file.is_file():
        raise OrchestratorError(f"requirement file is missing: {requirement_file}")
    requirement_digest = _digest(requirement_file.read_text(encoding="utf-8"))
    existing_state_path = state_path(directory)
    if existing_state_path.is_file():
        existing = load_state(directory)
        if existing.get("requirement_digest") != requirement_digest or existing.get("target_repository") != target_repository:
            raise OrchestratorError(
                f"pre-authoring state for {requirement_id!r} already exists and is bound to different "
                "requirement content/target; use a different --id for a different requirement"
            )
        return existing
    directory.mkdir(parents=True, exist_ok=True)
    state = {
        "version": STATE_VERSION,
        "id": requirement_id,
        "requirement_file": str(requirement_file),
        "requirement_digest": requirement_digest,
        "target_repository": target_repository,
        "created_at": utc_now(),
    }
    _write_json(existing_state_path, state)
    add_intents.new_add(
        root,
        add_id=requirement_id,
        requirement_file=requirement_file,
        target_repository=target_repository,
        out=add_path(directory),
    )
    return state


def _snapshot_status(root: Path, directory: Path) -> dict[str, Any]:
    path = snapshot_path(directory)
    if not path.is_file():
        return {"stage": "snapshot", "state": "missing", "action": f"project_evidence.py build --out {path}"}
    snapshot = _load_json(path, "snapshot")
    try:
        report = project_evidence.validate_snapshot(root, snapshot, check_freshness=True)
    except project_evidence.ProjectEvidenceError as exc:
        return {"stage": "snapshot", "state": "invalid", "errors": [str(exc)]}
    needs_extraction = [
        concern
        for concern, projection in snapshot.get("projections", {}).items()
        if isinstance(projection, dict) and projection.get("status") == "requires-extraction"
    ]
    if needs_extraction:
        worker_requests = {
            concern: snapshot["projections"][concern]["worker_request"] for concern in needs_extraction
        }
        return {
            "stage": "snapshot",
            "state": "needs-worker",
            "worker_requests": worker_requests,
            "action": (
                f"run each worker_request, write results to files, then "
                f"project_evidence.py build --out {path} --prior {path} "
                + " ".join(f"--worker-result {concern}=<path>" for concern in needs_extraction)
            ),
        }
    if report["freshness"] not in ("fresh",):
        return {
            "stage": "snapshot",
            "state": "stale",
            "freshness": report["freshness"],
            "changed_sources": report["changed_sources"],
            "action": f"project_evidence.py build --out {path} --prior {path} [--worker-result ...]",
        }
    return {"stage": "snapshot", "state": "ready", "digest": snapshot["digest"]}


def _decision_request(item: dict[str, Any], index: int) -> dict[str, Any]:
    payload = {"index": index, "question": item.get("question")}
    for key in ("alternatives", "evidence", "consequences", "recommendation", "affected_elements"):
        if key in item:
            payload[key] = item[key]
    return payload


def _add_status(root: Path, directory: Path) -> dict[str, Any]:
    path = add_path(directory)
    if not path.is_file():
        return {"stage": "add", "state": "missing", "action": "orchestrate_pre_authoring.py init"}
    document = _load_json(path, "ADD document")
    open_decisions = [
        _decision_request(item, index)
        for index, item in enumerate(document.get("unresolved_choices", []) or [])
        if isinstance(item, dict) and item.get("status") == "open"
    ]
    if open_decisions:
        return {
            "stage": "add",
            "state": "needs-decision",
            "decisions": open_decisions,
            "action": (
                "surface each decision to the human through the main agent; apply the accepted answer with "
                "orchestrate_pre_authoring.py record-decision --index N --resolution TEXT"
            ),
        }
    if document.get("approved") is not True:
        if not document.get("elements"):
            return {
                "stage": "add",
                "state": "needs-drafting",
                "action": (
                    "draft elements/assumptions/evidence/unresolved_choices onto the ADD from the requirement "
                    f"and fresh snapshot projections, then approve: add_intents.py approve-add {path}"
                ),
            }
        report = add_intents.validate_add(root, path, check_freshness=False)
        if not report.ok:
            return {"stage": "add", "state": "invalid", "errors": list(report.errors)}
        return {"stage": "add", "state": "needs-approval", "action": f"add_intents.py approve-add {path}"}
    report = add_intents.validate_add(root, path, check_freshness=True)
    if not report.ok:
        return {"stage": "add", "state": "invalid", "errors": list(report.errors)}
    if report.freshness not in (None, "fresh"):
        return {
            "stage": "add",
            "state": "stale",
            "freshness": report.freshness,
            "action": "the approved ADD's prepared_against revision or snapshot evidence is behind current state",
        }
    return {"stage": "add", "state": "ready", "digest": add_intents.add_content_digest(document)}


def _intents_status(root: Path, directory: Path) -> dict[str, Any]:
    path = intents_path(directory)
    add_file = add_path(directory)
    if not path.is_file():
        return {
            "stage": "intents",
            "state": "missing",
            "action": f"add_intents.py decompose --add {add_file} --out {path}",
        }
    document = _load_json(path, "intent-set document")
    if not document.get("intents"):
        return {
            "stage": "intents",
            "state": "needs-decomposition",
            "action": "decompose the approved ADD's elements into intents covering every new/changed element",
        }
    report = add_intents.validate_intents(root, path, add_path=add_file)
    if not report.ok:
        return {"stage": "intents", "state": "invalid", "errors": list(report.errors)}
    ready_ids = [
        item["id"]
        for item in document.get("intents", [])
        if isinstance(item, dict) and item.get("ready") is True
    ]
    if not ready_ids:
        return {
            "stage": "intents",
            "state": "needs-readiness",
            "action": "mark at least one intent ready (clear its blocker) before it can be handed off",
        }
    return {"stage": "intents", "state": "ready", "ready_intent_ids": ready_ids}


def _handoff_status(root: Path, directory: Path, ready_intent_ids: list[str]) -> dict[str, Any]:
    directory_h = handoff_dir(directory)
    add_file = add_path(directory)
    intents_file = intents_path(directory)
    prepared: dict[str, Any] = {}
    missing: list[str] = []
    stale: dict[str, Any] = {}
    for intent_id in ready_intent_ids:
        envelope_path = directory_h / f"{intent_id}.json"
        if not envelope_path.is_file():
            missing.append(intent_id)
            continue
        report = add_intents.check_handoff_staleness(
            root, envelope_path=envelope_path, add_path=add_file, intents_path=intents_file
        )
        if not report.ok:
            stale[intent_id] = list(report.errors)
        else:
            prepared[intent_id] = str(envelope_path)
    if missing or stale:
        return {
            "stage": "handoff",
            "state": "needs-handoff",
            "missing_intent_ids": missing,
            "stale_intent_ids": stale,
            "action": (
                f"add_intents.py prepare-handoff --add {add_file} --intents {intents_file} "
                f"--intent-id <id> --out {directory_h}/<id>.json"
            ),
        }
    return {"stage": "handoff", "state": "ready", "envelopes": prepared}


def status(root: Path, *, requirement_id: str, base_dir: Path | None = None) -> dict[str, Any]:
    """Recompute the current/next pre-authoring stage from the actual artifact files.

    Never trusts a prior receipt: every stage is re-validated with
    project_evidence.py/add_intents.py against the files on disk, so a
    restarted process or a later session resumes correctly, and a mutated
    upstream artifact is caught the same way those modules already catch it.
    """
    base_dir = base_dir or default_base_dir(root)
    directory = requirement_dir(base_dir, requirement_id)
    state = load_state(directory)

    snapshot_report = _snapshot_status(root, directory)
    stages: dict[str, Any] = {"snapshot": snapshot_report}
    result: dict[str, Any] = {
        "id": requirement_id,
        "target_repository": state.get("target_repository"),
        "stages": stages,
    }
    if snapshot_report["state"] != "ready":
        result["current_stage"] = "snapshot"
        result["blocker"] = snapshot_report
        _write_receipt(directory, result)
        return result

    add_report = _add_status(root, directory)
    stages["add"] = add_report
    if add_report["state"] != "ready":
        result["current_stage"] = "add"
        result["blocker"] = add_report
        _write_receipt(directory, result)
        return result

    intents_report = _intents_status(root, directory)
    stages["intents"] = intents_report
    if intents_report["state"] != "ready":
        result["current_stage"] = "intents"
        result["blocker"] = intents_report
        _write_receipt(directory, result)
        return result

    handoff_report = _handoff_status(root, directory, intents_report["ready_intent_ids"])
    stages["handoff"] = handoff_report
    if handoff_report["state"] != "ready":
        result["current_stage"] = "handoff"
        result["blocker"] = handoff_report
        _write_receipt(directory, result)
        return result

    result["current_stage"] = "complete"
    result["blocker"] = None
    result["handoffs"] = handoff_report["envelopes"]
    _write_receipt(directory, result)
    return result


def _write_receipt(directory: Path, result: dict[str, Any]) -> None:
    # Navigation cache only -- status() above never reads this back; it is
    # written purely so an external viewer can inspect the last computed
    # state without re-running validation, and it carries no raw
    # prompt/transcript content, only identities/digests/status strings.
    receipt = {"version": RECEIPT_VERSION, "computed_at": utc_now(), **result}
    _write_json(receipt_path(directory), receipt)


def record_decision(
    root: Path, *, requirement_id: str, index: int, resolution: str, base_dir: Path | None = None
) -> dict[str, Any]:
    """Apply an accepted human answer to exactly one open unresolved choice.

    Deterministic and bounded: it edits only unresolved_choices[index] and
    never approves the ADD itself -- approve-add remains the only supported
    way to bind approval, so an ADD with any other still-open choice stays
    correctly blocked.
    """
    base_dir = base_dir or default_base_dir(root)
    directory = requirement_dir(base_dir, requirement_id)
    path = add_path(directory)
    document = _load_json(path, "ADD document")
    choices = document.get("unresolved_choices")
    if not isinstance(choices, list) or index < 0 or index >= len(choices):
        raise OrchestratorError(f"unresolved_choices[{index}] does not exist")
    item = choices[index]
    if not isinstance(item, dict) or item.get("status") != "open":
        raise OrchestratorError(f"unresolved_choices[{index}] is not an open decision")
    if not resolution.strip():
        raise OrchestratorError("resolution must be a non-empty string")
    item["status"] = "resolved"
    item["resolution"] = resolution.strip()
    original = path.read_text(encoding="utf-8")
    _write_json(path, document)
    report = add_intents.validate_add(root, path, check_freshness=False)
    if not report.ok:
        path.write_text(original, encoding="utf-8")
        raise OrchestratorError("cannot record decision: " + "; ".join(report.errors))
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin resumable pre-authoring orchestrator (snapshot -> ADD -> intents -> handoff).")
    parser.add_argument("--id", required=True, dest="requirement_id", help="stable requirement identity, also used as the ADD id")
    parser.add_argument("--base-dir", type=Path, default=None, help="override the default .claude/pre-authoring directory")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="bind a requirement identity and scaffold its ADD")
    init_parser.add_argument("--requirement-file", required=True, type=Path)
    init_parser.add_argument("--target-repository", required=True)

    sub.add_parser("status", help="recompute the current/next pre-authoring stage from the artifact files")

    decision_parser = sub.add_parser("record-decision", help="apply an accepted human answer to one open ADD decision")
    decision_parser.add_argument("--index", required=True, type=int)
    decision_parser.add_argument("--resolution", required=True)

    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "init":
            payload = init(
                root,
                requirement_id=args.requirement_id,
                requirement_file=args.requirement_file,
                target_repository=args.target_repository,
                base_dir=args.base_dir,
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "status":
            payload = status(root, requirement_id=args.requirement_id, base_dir=args.base_dir)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if payload["current_stage"] == "complete" else 1
        if args.command == "record-decision":
            document = record_decision(
                root,
                requirement_id=args.requirement_id,
                index=args.index,
                resolution=args.resolution,
                base_dir=args.base_dir,
            )
            print(json.dumps({"ok": True, "add_id": document.get("add_id")}, ensure_ascii=False, indent=2))
            return 0
        raise OrchestratorError(f"unsupported command: {args.command}")  # pragma: no cover - argparse enforces the choice set
    except OrchestratorError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
