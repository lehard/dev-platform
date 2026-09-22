#!/usr/bin/env python3
"""Thin resumable, proportional pre-authoring orchestrator.

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
    selection.json  -- explainable pre-authoring depth and evidence bindings
    skip.json       -- derived receipt when ADD/intents are safely bypassed
    direct-handoff.json -- normal OpenSpec authoring input for a skipped path
    add.json        -- an ADD document (add_intents.py; material paths only)
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
import shutil
from pathlib import Path
from typing import Any

import add_intents
import project_evidence
from _platform_common import atomic_write_text, current_worktree_root, utc_now

STATE_VERSION = 3
RECEIPT_VERSION = 1
SELECTION_VERSION = 1
SKIP_RECEIPT_VERSION = 1
DIRECT_HANDOFF_VERSION = 1

DEPTH_DETERMINISTIC = "deterministic"
DEPTH_BOUNDED_EVIDENCE = "bounded-evidence"
DEPTH_MATERIAL_DESIGN = "material-design"
DEPTHS = (DEPTH_DETERMINISTIC, DEPTH_BOUNDED_EVIDENCE, DEPTH_MATERIAL_DESIGN)


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


def selection_path(directory: Path) -> Path:
    return directory / "selection.json"


def skip_path(directory: Path) -> Path:
    return directory / "skip.json"


def direct_handoff_path(directory: Path) -> Path:
    return directory / "direct-handoff.json"


def load_state(directory: Path) -> dict[str, Any]:
    return _load_json(state_path(directory), "pre-authoring state")


def _invalidate_from_selection(directory: Path) -> None:
    """Discard only artifacts derived from a Requirement's business meaning.

    A Project Evidence Snapshot is rooted in the target worktree, rather than
    the Requirement text, so it remains eligible for its own freshness check.
    ADD, intents, handoffs and navigation receipts are all downstream of the
    Requirement and must be rebuilt. No OpenSpec directory is under this
    machine-local pre-authoring root, so materialized OpenSpec is untouched.
    """
    for path in (
        selection_path(directory), skip_path(directory), direct_handoff_path(directory),
        add_path(directory), intents_path(directory), receipt_path(directory),
    ):
        path.unlink(missing_ok=True)
    handoffs = handoff_dir(directory)
    if handoffs.exists():
        shutil.rmtree(handoffs)


def init(
    root: Path,
    *,
    requirement_id: str,
    requirement_file: Path,
    target_repository: str,
    base_dir: Path | None = None,
    refresh_requirement: bool = False,
    business_context_file: Path | None = None,
) -> dict[str, Any]:
    """Bind a Requirement identity. Safe to call repeatedly.

    Refuses to re-init over an existing state bound to a different local
    Requirement identity. Requirement intake supplies ``refresh_requirement``
    after refetching its stable GitHub Issue; a changed complete binding then
    resets ADD-and-later derived artifacts before safely rebinding.
    Depth is deliberately selected after this deterministic binding.  ADD is
    therefore scaffolded only for a recorded material-design selection.
    """
    base_dir = base_dir or default_base_dir(root)
    directory = requirement_dir(base_dir, requirement_id)
    if not requirement_file.is_file():
        raise OrchestratorError(f"requirement file is missing: {requirement_file}")
    if business_context_file is not None and not business_context_file.is_file():
        raise OrchestratorError(f"Requirement context file is missing: {business_context_file}")
    requirement_digest = _digest(requirement_file.read_text(encoding="utf-8"))
    business_context_file_value = str(business_context_file) if business_context_file is not None else None
    existing_state_path = state_path(directory)
    if existing_state_path.is_file():
        existing = load_state(directory)
        legacy_requirement_file = directory / "requirement.md"
        is_legacy_outcome_only_state = (
            existing.get("version") != STATE_VERSION
            and existing.get("requirement_file") == str(legacy_requirement_file)
        )
        if (
            existing.get("id") != requirement_id
            or (
                existing.get("requirement_file") != str(requirement_file)
                and not (refresh_requirement and is_legacy_outcome_only_state)
            )
        ):
            raise OrchestratorError(
                f"pre-authoring state for {requirement_id!r} is bound to a different Requirement identity; "
                "use a different --id for a different requirement"
            )
        binding_changed = (
            existing.get("version") != STATE_VERSION
            or existing.get("requirement_file") != str(requirement_file)
            or existing.get("requirement_digest") != requirement_digest
            or existing.get("target_repository") != target_repository
            or existing.get("business_context_file") != business_context_file_value
        )
        if binding_changed and not refresh_requirement:
            raise OrchestratorError(
                f"pre-authoring state for {requirement_id!r} has a changed or legacy Requirement binding; "
                "restart through requirement_intake.py start to rebuild derived pre-authoring artifacts"
            )
        if not binding_changed:
            return existing
        if binding_changed:
            _invalidate_from_selection(directory)
        created_at = existing.get("created_at") if isinstance(existing.get("created_at"), str) else utc_now()
        # state.json survived a prior failed init (new_add did not complete);
        # fall through and retry the ADD scaffold rather than returning state
        # for a permanently-missing artifact.
    else:
        created_at = utc_now()
    directory.mkdir(parents=True, exist_ok=True)
    state = {
        "version": STATE_VERSION,
        "id": requirement_id,
        "requirement_file": str(requirement_file),
        "requirement_digest": requirement_digest,
        "target_repository": target_repository,
        "business_context_file": business_context_file_value,
        "created_at": created_at,
    }
    _write_json(existing_state_path, state)
    return state


def select_depth(
    root: Path, *, requirement_id: str, depth: str, reason: str,
    concerns: list[str] | None = None, base_dir: Path | None = None,
) -> dict[str, Any]:
    """Record an explicit, reviewable depth decision without a model call.

    The caller supplies the semantic judgment; this function enforces its
    bounded consequences and binds it to the complete Requirement identity.
    """
    directory = requirement_dir(base_dir or default_base_dir(root), requirement_id)
    state = load_state(directory)
    if depth not in DEPTHS or not reason.strip():
        raise OrchestratorError("depth must be supported and reason must be non-empty")
    if depth == DEPTH_BOUNDED_EVIDENCE:
        try:
            selected = list(project_evidence._selected_concerns(concerns))
        except project_evidence.ProjectEvidenceError as exc:
            raise OrchestratorError(str(exc)) from exc
        if concerns is None:
            raise OrchestratorError("bounded evidence requires explicit --concern scope")
    elif concerns:
        if depth == DEPTH_DETERMINISTIC:
            raise OrchestratorError("deterministic depth cannot request worker projections")
        selected = list(project_evidence._selected_concerns(concerns))
    else:
        selected = [] if depth == DEPTH_DETERMINISTIC else list(project_evidence.CONCERNS)
    if _digest(Path(state["requirement_file"]).read_text(encoding="utf-8")) != state["requirement_digest"]:
        raise OrchestratorError("Requirement binding changed; restart through requirement_intake.py start")
    decision = {
        "version": SELECTION_VERSION, "depth": depth, "reason": reason.strip(),
        "requirement_digest": state["requirement_digest"],
        "target_repository": state["target_repository"], "concerns": selected,
        "routing": "routine-read-only" if depth == DEPTH_BOUNDED_EVIDENCE else ("R2-default" if depth == DEPTH_MATERIAL_DESIGN else "none"),
    }
    path = selection_path(directory)
    if path.is_file():
        previous = _load_json(path, "depth selection")
        if previous == decision:
            if depth == DEPTH_MATERIAL_DESIGN and not add_path(directory).is_file():
                add_intents.new_add(
                    root, add_id=requirement_id, requirement_file=Path(state["requirement_file"]),
                    target_repository=state["target_repository"], out=add_path(directory),
                )
            return decision
        _invalidate_from_selection(directory)
    _write_json(path, decision)
    if depth == DEPTH_MATERIAL_DESIGN:
        add_intents.new_add(
            root, add_id=requirement_id, requirement_file=Path(state["requirement_file"]),
            target_repository=state["target_repository"], out=add_path(directory),
        )
    return decision


def _selection_status(root: Path, directory: Path, state: dict[str, Any]) -> dict[str, Any]:
    path = selection_path(directory)
    if not path.is_file():
        return {"stage": "selection", "state": "missing", "action": "orchestrate_pre_authoring.py select-depth --depth <deterministic|bounded-evidence|material-design> --reason TEXT [--concern NAME]"}
    selection = _load_json(path, "depth selection")
    if selection.get("version") != SELECTION_VERSION or selection.get("depth") not in DEPTHS:
        return {"stage": "selection", "state": "invalid", "action": "record a supported depth selection"}
    if (selection.get("requirement_digest") != state.get("requirement_digest")
            or selection.get("target_repository") != state.get("target_repository")
            or not Path(state["requirement_file"]).is_file()
            or _digest(Path(state["requirement_file"]).read_text(encoding="utf-8")) != state["requirement_digest"]):
        return {"stage": "selection", "state": "stale", "action": "requirement_intake.py start --requirement <issue>"}
    return {"stage": "selection", "state": "ready", "decision": selection}


def _snapshot_status(root: Path, directory: Path, concerns: list[str]) -> dict[str, Any]:
    path = snapshot_path(directory)
    scope = " ".join(f"--concern {concern}" for concern in concerns)
    if not path.is_file():
        return {"stage": "snapshot", "state": "missing", "action": f"project_evidence.py build --out {path} {scope}".strip()}
    snapshot = _load_json(path, "snapshot")
    if set(snapshot.get("projections", {})) != set(concerns):
        return {"stage": "snapshot", "state": "scope-mismatch", "action": f"project_evidence.py build --out {path} {scope}".strip()}
    try:
        report = project_evidence.validate_snapshot(root, snapshot, check_freshness=True)
    except project_evidence.ProjectEvidenceError as exc:
        return {"stage": "snapshot", "state": "invalid", "errors": [str(exc)]}
    needs_extraction = [
        concern
        for concern, projection in snapshot.get("projections", {}).items()
        if isinstance(projection, dict) and projection.get("status") == "requires-extraction"
    ]
    escalation = [
        concern for concern, projection in snapshot.get("projections", {}).items()
        if isinstance(projection, dict) and projection.get("status") == "escalation-required"
    ]
    if escalation:
        return {"stage": "snapshot", "state": "needs-escalation", "concerns": escalation,
                "action": "resolve conflicting or low-confidence evidence before continuing"}
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
                + f" {scope}"
            ),
        }
    if report["freshness"] not in ("fresh",):
        return {
            "stage": "snapshot",
            "state": "stale",
            "freshness": report["freshness"],
            "changed_sources": report["changed_sources"],
            "action": f"project_evidence.py build --out {path} --prior {path} {scope} [--worker-result ...]",
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
        return {"stage": "add", "state": "missing", "action": "re-run select-depth --depth material-design with the recorded reason"}
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
    state = load_state(directory)
    business_context_file = state.get("business_context_file")
    context_argument = (
        f" --requirement-context-file {business_context_file}"
        if isinstance(business_context_file, str) and business_context_file else ""
    )
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
                f"--intent-id <id>{context_argument} "
                f"--out {directory_h}/<id>.json"
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

    selection_report = _selection_status(root, directory, state)
    stages: dict[str, Any] = {"selection": selection_report}
    result: dict[str, Any] = {
        "id": requirement_id,
        "target_repository": state.get("target_repository"),
        "stages": stages,
    }
    if selection_report["state"] != "ready":
        result["current_stage"] = "selection"
        result["blocker"] = selection_report
        _write_receipt(directory, result)
        return result

    decision = selection_report["decision"]
    depth = decision["depth"]
    if depth == DEPTH_DETERMINISTIC:
        return _finish_skip(directory, result, state, decision, None)

    snapshot_report = _snapshot_status(root, directory, decision["concerns"])
    stages["snapshot"] = snapshot_report
    if snapshot_report["state"] != "ready":
        result["current_stage"] = "snapshot"
        result["blocker"] = snapshot_report
        _write_receipt(directory, result)
        return result

    if depth == DEPTH_BOUNDED_EVIDENCE:
        return _finish_skip(directory, result, state, decision, snapshot_report["digest"])

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


def _finish_skip(
    directory: Path, result: dict[str, Any], state: dict[str, Any],
    decision: dict[str, Any], evidence_digest: str | None,
) -> dict[str, Any]:
    """Reconcile derived skip/handoff receipts from fresh source bindings."""
    binding = {
        "version": SKIP_RECEIPT_VERSION, "depth": decision["depth"],
        "reason": decision["reason"], "requirement_digest": state["requirement_digest"],
        "target_repository": state["target_repository"],
        "concerns": decision["concerns"], "evidence_digest": evidence_digest,
        "routing": decision["routing"],
    }
    if not skip_path(directory).is_file() or _load_json(skip_path(directory), "skip receipt") != binding:
        _write_json(skip_path(directory), binding)
    context_file = state.get("business_context_file")
    context = _load_json(Path(context_file), "Requirement context") if context_file else None
    handoff = {
        "version": DIRECT_HANDOFF_VERSION, "kind": "direct-requirement-handoff",
        "requirement_id": result["id"], "requirement_context": context,
        "source_binding": binding,
    }
    if not direct_handoff_path(directory).is_file() or _load_json(direct_handoff_path(directory), "direct handoff") != handoff:
        _write_json(direct_handoff_path(directory), handoff)
    result["stages"]["skip"] = {"stage": "skip", "state": "ready", "receipt": str(skip_path(directory))}
    result["current_stage"] = "complete"
    result["blocker"] = None
    result["handoffs"] = {"direct": str(direct_handoff_path(directory))}
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
        atomic_write_text(path, original)
        raise OrchestratorError("cannot record decision: " + "; ".join(report.errors))
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin resumable pre-authoring orchestrator (snapshot -> ADD -> intents -> handoff).")
    parser.add_argument("--id", required=True, dest="requirement_id", help="stable requirement identity, also used as the ADD id")
    parser.add_argument("--base-dir", type=Path, default=None, help="override the default .claude/pre-authoring directory")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="bind a requirement identity")
    init_parser.add_argument("--requirement-file", required=True, type=Path)
    init_parser.add_argument("--target-repository", required=True)

    sub.add_parser("status", help="recompute the current/next pre-authoring stage from the artifact files")

    select_parser = sub.add_parser("select-depth", help="record a reasoned, bounded depth decision")
    select_parser.add_argument("--depth", required=True, choices=DEPTHS)
    select_parser.add_argument("--reason", required=True)
    select_parser.add_argument("--concern", action="append", choices=project_evidence.CONCERNS)

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
        if args.command == "select-depth":
            payload = select_depth(root, requirement_id=args.requirement_id, depth=args.depth,
                                   reason=args.reason, concerns=args.concern, base_dir=args.base_dir)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
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
