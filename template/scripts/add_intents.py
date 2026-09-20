#!/usr/bin/env python3
"""Deterministic scaffolding and gates for the ADD -> Intents pre-authoring pipeline.

Architecture Design Delta (ADD) and Intent documents are bounded, machine-local
pre-authoring evidence -- not a second backlog, implementation contract, or
current-system registry (see ``dev-platform/capabilities/add-intents.md``).
This module only proves *structural* properties: schema validity, provenance,
freshness, dependency-graph integrity, ADD-element coverage, and -- for the
hardened pipeline -- exact content-digest binding between each stage and the
upstream evidence/content it reviewed. It deliberately never claims that an
ADD is the right design, that a decomposition is the best possible partition,
or that a split candidate must actually be split -- that judgment stays with
the human/agent review the capability instructions describe.

Snapshot/projection identity and freshness are never recomputed here: every
check that needs them calls into ``project_evidence.py`` (see
``_snapshot_evidence_freshness_errors``) instead of duplicating its source
inventory, digesting, or staleness logic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import project_evidence
from _platform_common import atomic_write_text, current_worktree_root, run_git, utc_now

ADD_SCHEMA_VERSION = 1
INTENTS_SCHEMA_VERSION = 1
HANDOFF_SCHEMA_VERSION = 1

ID_RE = re.compile(r"[a-z][a-z0-9-]{1,63}")
SHA_RE = re.compile(r"[0-9a-f]{40}")

ELEMENT_CATEGORIES = (
    "capability",
    "boundary",
    "integration",
    "data",
    "invariant",
    "security",
    "nfr",
    "preserved-constraint",
)
ELEMENT_STATUSES = ("new", "changed", "preserved")
# Only these statuses represent a true design delta that intents must cover.
COVERAGE_REQUIRED_STATUSES = ("new", "changed")

# An evidence entry of this kind is a digest-bound reference into a Project
# Evidence Snapshot (see project_evidence.py `reference`), not free-form
# prose. Because it is machine-checkable, it is treated as load-bearing:
# decomposition and intent validation re-prove it is still fresh rather than
# merely warning when it is not.
EVIDENCE_KIND_SNAPSHOT = "project-evidence-snapshot"
PROJECTION_STATUSES = ("fresh", "escalation-required", "requires-extraction")

# Fields excluded from the ADD's canonical content digest: the approval
# receipt records that digest (so it cannot include itself), and the
# `approved` flag toggles what the digest activates rather than being part of
# the reviewed design content.
_ADD_DIGEST_EXCLUDED_KEYS = frozenset({"approval", "approved"})


class AddIntentsError(RuntimeError):
    """A structural ADD/Intents authoring or validation failure."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AddIntentsError(f"{label} is not readable: {path}") from exc
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AddIntentsError(f"{label} is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise AddIntentsError(f"{label} must be a JSON object")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_digest(value: Any) -> str:
    """Canonical-JSON content digest used to bind a document/envelope to exact content."""
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def add_content_digest(document: dict[str, Any]) -> str:
    """Canonical content digest over the ADD's normatively-approved fields.

    Excludes the approval receipt and the `approved` flag (see
    ``_ADD_DIGEST_EXCLUDED_KEYS``), so the digest changes exactly when the
    material design content of the ADD changes -- never merely because it was
    approved or unapproved.
    """
    material = {key: value for key, value in document.items() if key not in _ADD_DIGEST_EXCLUDED_KEYS}
    return _content_digest(material)


def current_revision(root: Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=root).stdout.strip().lower()


# --- ADD -----------------------------------------------------------------


def new_add(
    root: Path,
    *,
    add_id: str,
    requirement_file: Path,
    target_repository: str,
    out: Path,
    prepared_against: str | None = None,
) -> dict[str, Any]:
    """Scaffold a versioned ADD document bound to an exact revision.

    The requirement text is digested, never copied verbatim, so the ADD stays
    a bounded delta record rather than a second copy of the business
    requirement.
    """
    if not ID_RE.fullmatch(add_id):
        raise AddIntentsError(f"add_id must match {ID_RE.pattern!r}: {add_id!r}")
    if not requirement_file.is_file():
        raise AddIntentsError(f"requirement file is missing: {requirement_file}")
    requirement_text = requirement_file.read_text(encoding="utf-8")
    if not requirement_text.strip():
        raise AddIntentsError("requirement file must not be empty")
    revision = (prepared_against or current_revision(root)).lower()
    if not SHA_RE.fullmatch(revision):
        raise AddIntentsError(f"prepared_against must be a 40-character git SHA, got {revision!r}")
    payload: dict[str, Any] = {
        "version": ADD_SCHEMA_VERSION,
        "add_id": add_id,
        "requirement": {"digest": _digest(requirement_text), "summary": ""},
        "target_repository": target_repository,
        "prepared_against": revision,
        "created_at": utc_now(),
        "evidence": [],
        "reused_constraints": [],
        "elements": [],
        "assumptions": [],
        "contradictions": [],
        "unresolved_choices": [],
        "approved": False,
        "approval": None,
    }
    _write_json(out, payload)
    return payload


def _require_str(entry: dict[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AddIntentsError(f"{where}: {key!r} must be a non-empty string")
    return value


def _require_string_list(entry: dict[str, Any], key: str, where: str, errors: list[str]) -> list[str]:
    """Validate `entry[key]` is present and a list of strings; bounded-empty is valid."""
    value = entry.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{where}: {key!r} must be a list of strings")
        return []
    return value


def _validate_snapshot_evidence_entry(item: dict[str, Any], where: str) -> list[str]:
    """Structural checks for a `project-evidence-snapshot` evidence/snapshot-ref entry.

    This proves only shape and internal self-consistency; whether the
    referenced snapshot/projection is *currently* provably fresh is a
    separate, filesystem-touching concern handled by
    ``_snapshot_evidence_freshness_errors``.
    """
    errors: list[str] = []
    for key in ("snapshot_digest", "projection", "projection_digest", "projection_status"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: snapshot evidence must set a non-empty {key!r}")
    status = item.get("projection_status")
    if isinstance(status, str) and status not in PROJECTION_STATUSES:
        errors.append(f"{where}: projection_status must be one of {', '.join(PROJECTION_STATUSES)}")
    revision = item.get("snapshot_revision")
    if revision is not None and not isinstance(revision, str):
        errors.append(f"{where}: snapshot_revision must be a string or null")
    projection_digest = item.get("projection_digest")
    if isinstance(projection_digest, str) and item.get("digest") != projection_digest:
        errors.append(f"{where}: digest must equal projection_digest for snapshot evidence")
    return errors


def _snapshot_evidence_freshness_errors(root: Path, evidence: list[Any]) -> list[str]:
    """Re-prove each `project-evidence-snapshot` entry against project_evidence.py.

    Delegates entirely to ``project_evidence.validate_snapshot`` for source
    identity and freshness logic; this module only compares the recorded
    evidence-ref digests to what that call currently proves, so stale or
    tampered evidence is caught rather than trusted.
    """
    errors: list[str] = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict) or item.get("kind") != EVIDENCE_KIND_SNAPSHOT:
            continue
        source = item.get("source")
        where = f"snapshot evidence [{index}] ({source!r})"
        if not isinstance(source, str) or not source:
            errors.append(f"{where}: snapshot evidence source is not a usable path")
            continue
        snapshot_path = Path(source)
        if not snapshot_path.is_absolute():
            snapshot_path = root / source
        try:
            snapshot = _load_json(snapshot_path, f"snapshot evidence source {source}")
            report = project_evidence.validate_snapshot(root, snapshot, check_freshness=True)
        except (AddIntentsError, project_evidence.ProjectEvidenceError) as exc:
            errors.append(f"{where}: snapshot evidence cannot be proven current: {exc}")
            continue
        if snapshot.get("digest") != item.get("snapshot_digest"):
            errors.append(f"{where}: recorded snapshot_digest no longer matches the snapshot file (it was rebuilt or changed)")
            continue
        if report["freshness"] != "fresh":
            errors.append(f"{where}: snapshot is {report['freshness']}, not fresh; refresh it before relying on this evidence")
            continue
        concern = item.get("projection")
        projections = snapshot.get("projections")
        projection = projections.get(concern) if isinstance(projections, dict) and isinstance(concern, str) else None
        if not isinstance(projection, dict) or projection.get("digest") != item.get("projection_digest"):
            errors.append(f"{where}: recorded projection_digest for {concern!r} no longer matches the snapshot")
            continue
        if projection.get("status") != "fresh":
            errors.append(f"{where}: projection {concern!r} is {projection.get('status')!r}, not fresh")
    return errors


@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    freshness: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok, "errors": list(self.errors), "warnings": list(self.warnings)}
        if self.freshness is not None:
            payload["freshness"] = self.freshness
        return payload


def _validate_add_document(root: Path, document: dict[str, Any], *, check_freshness: bool) -> ValidationReport:
    """Structural/provenance/freshness/approval-binding checks on an in-memory ADD document.

    Kept separate from ``validate_add`` (which loads from disk) so an
    in-memory candidate -- for example one about to be written by
    ``approve_add`` -- can be validated before it is persisted.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if document.get("version") != ADD_SCHEMA_VERSION:
        errors.append(f"unsupported ADD schema version: {document.get('version')!r}")
    add_id = document.get("add_id")
    if not isinstance(add_id, str) or not ID_RE.fullmatch(add_id):
        errors.append(f"add_id must match {ID_RE.pattern!r}")
    requirement = document.get("requirement")
    if not isinstance(requirement, dict) or not isinstance(requirement.get("digest"), str) or not requirement.get("digest"):
        errors.append("requirement.digest must be a non-empty string")
    try:
        _require_str(document, "target_repository", "ADD document")
    except AddIntentsError as exc:
        errors.append(str(exc))
    prepared_against = document.get("prepared_against")
    if not isinstance(prepared_against, str) or not SHA_RE.fullmatch(prepared_against.lower()):
        errors.append("prepared_against must be a 40-character git SHA")

    freshness: str | None = None
    if check_freshness and isinstance(prepared_against, str) and SHA_RE.fullmatch(prepared_against.lower()):
        try:
            freshness = "fresh" if current_revision(root) == prepared_against.lower() else "stale-needs-semantic-preflight"
        except Exception:  # pragma: no cover - defensive: git must remain advisory here
            freshness = "unknown"

    evidence = document.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []
    for index, item in enumerate(evidence):
        where = f"evidence[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            _require_str(item, "source", where)
            kind = _require_str(item, "kind", where)
            _require_str(item, "digest", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
            continue
        if kind == EVIDENCE_KIND_SNAPSHOT:
            errors.extend(_validate_snapshot_evidence_entry(item, where))

    reused_constraints = document.get("reused_constraints", [])
    if not isinstance(reused_constraints, list):
        errors.append("reused_constraints must be a list")
        reused_constraints = []
    for index, item in enumerate(reused_constraints):
        where = f"reused_constraints[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            _require_str(item, "source", where)
            _require_str(item, "statement", where)
        except AddIntentsError as exc:
            errors.append(str(exc))

    assumptions = document.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(isinstance(item, str) and item.strip() for item in assumptions):
        errors.append("assumptions must be a list of non-empty strings")

    element_ids: set[str] = set()
    elements = document.get("elements", [])
    if not isinstance(elements, list):
        errors.append("elements must be a list")
        elements = []
    for index, item in enumerate(elements):
        where = f"elements[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            element_id = _require_str(item, "id", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
            continue
        if element_id in element_ids:
            errors.append(f"{where}: duplicate element id {element_id!r}")
        element_ids.add(element_id)
        category = item.get("category")
        if category not in ELEMENT_CATEGORIES:
            errors.append(f"{where}: category must be one of {', '.join(ELEMENT_CATEGORIES)}")
        status = item.get("status")
        if status not in ELEMENT_STATUSES:
            errors.append(f"{where}: status must be one of {', '.join(ELEMENT_STATUSES)}")
        try:
            _require_str(item, "statement", where)
        except AddIntentsError as exc:
            errors.append(str(exc))

    unresolved = document.get("unresolved_choices", [])
    if not isinstance(unresolved, list):
        errors.append("unresolved_choices must be a list")
        unresolved = []
    open_choices = 0
    for index, item in enumerate(unresolved):
        where = f"unresolved_choices[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            _require_str(item, "question", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
        status = item.get("status")
        if status not in ("open", "resolved"):
            errors.append(f"{where}: status must be 'open' or 'resolved'")
        elif status == "open":
            open_choices += 1
        elif status == "resolved" and not isinstance(item.get("resolution"), str):
            errors.append(f"{where}: resolved choice must record a non-empty resolution")

    contradictions = document.get("contradictions", [])
    if not isinstance(contradictions, list):
        errors.append("contradictions must be a list")
        contradictions = []
    unresolved_contradictions = 0
    for index, item in enumerate(contradictions):
        where = f"contradictions[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            _require_str(item, "statement", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
        if not isinstance(item.get("resolved"), bool):
            errors.append(f"{where}: resolved must be a boolean")
        elif item["resolved"] is False:
            unresolved_contradictions += 1

    approval = document.get("approval")
    if approval is not None and not isinstance(approval, dict):
        errors.append("approval must be an object or null")

    if document.get("approved") is True:
        if open_choices:
            errors.append(f"ADD cannot be approved while {open_choices} unresolved consequential choice(s) remain")
        if unresolved_contradictions:
            errors.append(f"ADD cannot be approved while {unresolved_contradictions} unresolved contradiction(s) remain")
        if not elements:
            warnings.append("ADD is approved but records no design elements; confirm a bounded delta was actually needed")
        if not isinstance(approval, dict):
            errors.append("ADD is approved but records no approval receipt bound to its content digest")
        else:
            approved_digest = approval.get("digest")
            if not isinstance(approved_digest, str) or not approved_digest:
                errors.append("ADD approval receipt must record a non-empty content digest")
            elif approved_digest != add_content_digest(document):
                errors.append(
                    "ADD approval is stale: the approval's recorded content digest no longer matches the current "
                    "ADD content (the ADD was mutated after it was approved); re-run approve-add"
                )
            if not isinstance(approval.get("approved_at"), str) or not approval.get("approved_at"):
                errors.append("ADD approval receipt must record a non-empty approved_at timestamp")
    elif document.get("approved") is not False:
        errors.append("approved must be a boolean")

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings), freshness=freshness)


def validate_add(root: Path, path: Path, *, check_freshness: bool = True) -> ValidationReport:
    document = _load_json(path, "ADD document")
    return _validate_add_document(root, document, check_freshness=check_freshness)


def approve_add(root: Path, path: Path, *, approved_by: str | None = None) -> dict[str, Any]:
    """Bind human approval to the ADD's exact current content digest.

    Refuses to approve while a structural gate (schema, open unresolved
    choice, unresolved contradiction) is not yet satisfied. A human cannot
    hand-compute the digest, so this is the only supported way to produce a
    valid approval receipt; hand-editing `approved: true` without a matching
    `approval` object is rejected by `validate_add`.
    """
    document = _load_json(path, "ADD document")
    digest = add_content_digest(document)
    approval: dict[str, Any] = {"digest": digest, "approved_at": utc_now()}
    if isinstance(approved_by, str) and approved_by.strip():
        approval["approved_by"] = approved_by.strip()
    candidate = dict(document)
    candidate["approved"] = True
    candidate["approval"] = approval
    report = _validate_add_document(root, candidate, check_freshness=False)
    if not report.ok:
        raise AddIntentsError("cannot approve ADD: " + "; ".join(report.errors))
    _write_json(path, candidate)
    return candidate


# --- Intents ---------------------------------------------------------------


def decompose(root: Path, *, add_path: Path, out: Path, business_context: str = "") -> dict[str, Any]:
    add_document = _load_json(add_path, "ADD document")
    report = validate_add(root, add_path, check_freshness=True)
    if not report.ok:
        raise AddIntentsError("cannot decompose an ADD that fails structural validation: " + "; ".join(report.errors))
    if add_document.get("approved") is not True:
        raise AddIntentsError("cannot decompose an ADD that is not approved yet")
    if report.freshness not in (None, "fresh"):
        raise AddIntentsError(
            f"cannot decompose a {report.freshness} ADD; the ADD's prepared_against revision no longer matches "
            "the current worktree HEAD -- refresh/semantic-preflight it first"
        )
    evidence = add_document.get("evidence", []) or []
    snapshot_errors = _snapshot_evidence_freshness_errors(root, evidence)
    if snapshot_errors:
        raise AddIntentsError(
            "cannot decompose: required snapshot/projection evidence is stale or unproven: " + "; ".join(snapshot_errors)
        )
    approval = add_document.get("approval") if isinstance(add_document.get("approval"), dict) else {}
    snapshot_refs = [item for item in evidence if isinstance(item, dict) and item.get("kind") == EVIDENCE_KIND_SNAPSHOT]
    payload: dict[str, Any] = {
        "version": INTENTS_SCHEMA_VERSION,
        "add_id": add_document["add_id"],
        "approved_add_digest": approval.get("digest"),
        "business_context": business_context,
        "created_at": utc_now(),
        "intents": [],
        "non_implementation": [],
        "snapshot_refs": snapshot_refs,
    }
    _write_json(out, payload)
    return payload


def _dependency_cycle(intents: dict[str, dict[str, Any]]) -> list[str] | None:
    """Return one offending cycle path, or None. DFS with an explicit stack."""
    state: dict[str, int] = {}  # 0=unvisited, 1=in-progress, 2=done
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        path.append(node)
        for dependency in intents.get(node, {}).get("dependencies", []) or []:
            if not isinstance(dependency, str) or dependency not in intents:
                continue  # reported separately as a dangling reference
            if state.get(dependency, 0) == 1:
                return path[path.index(dependency):] + [dependency]
            if state.get(dependency, 0) == 0:
                found = visit(dependency)
                if found is not None:
                    return found
        path.pop()
        state[node] = 2
        return None

    for intent_id in intents:
        if state.get(intent_id, 0) == 0:
            found = visit(intent_id)
            if found is not None:
                return found
    return None


def validate_intents(root: Path, path: Path, *, add_path: Path) -> ValidationReport:
    document = _load_json(path, "intent-set document")
    add_document = _load_json(add_path, "ADD document")
    errors: list[str] = []
    warnings: list[str] = []

    if document.get("version") != INTENTS_SCHEMA_VERSION:
        errors.append(f"unsupported intent-set schema version: {document.get('version')!r}")
    if document.get("add_id") != add_document.get("add_id"):
        errors.append(
            f"intent-set add_id {document.get('add_id')!r} does not match ADD add_id {add_document.get('add_id')!r}"
        )

    # The intent set must be bound to the exact ADD content that was approved,
    # not merely to a matching add_id, and that binding must still be current.
    add_report = validate_add(root, add_path, check_freshness=True)
    if not add_report.ok:
        errors.append("parent ADD fails structural validation: " + "; ".join(add_report.errors))
    elif add_document.get("approved") is not True:
        errors.append("parent ADD is not approved")
    elif add_report.freshness not in (None, "fresh"):
        errors.append(f"parent ADD is {add_report.freshness}; refresh it before trusting this intent set")

    approval = add_document.get("approval") if isinstance(add_document.get("approval"), dict) else {}
    approved_add_digest = document.get("approved_add_digest")
    if not isinstance(approved_add_digest, str) or not approved_add_digest:
        errors.append("intent-set approved_add_digest must be a non-empty string")
    elif approved_add_digest != approval.get("digest"):
        errors.append(
            "intent-set approved_add_digest does not match the parent ADD's current approval digest "
            "(this intent set is bound to a stale or different ADD approval)"
        )

    required_element_ids = {
        item.get("id")
        for item in add_document.get("elements", [])
        if isinstance(item, dict) and item.get("status") in COVERAGE_REQUIRED_STATUSES and isinstance(item.get("id"), str)
    }
    known_element_ids = {
        item.get("id") for item in add_document.get("elements", []) if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    known_reference_sources = {
        item.get("source")
        for item in (add_document.get("evidence", []) or []) + (add_document.get("reused_constraints", []) or [])
        if isinstance(item, dict) and isinstance(item.get("source"), str)
    }

    intents_raw = document.get("intents", [])
    if not isinstance(intents_raw, list):
        errors.append("intents must be a list")
        intents_raw = []

    by_id: dict[str, dict[str, Any]] = {}
    covers_owner: dict[str, list[str]] = {}
    for index, item in enumerate(intents_raw):
        where = f"intents[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            intent_id = _require_str(item, "id", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
            continue
        if intent_id in by_id:
            errors.append(f"{where}: duplicate intent id {intent_id!r}")
            continue
        by_id[intent_id] = item
        try:
            _require_str(item, "goal", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
        covers = item.get("covers", [])
        if not isinstance(covers, list) or not all(isinstance(entry, str) for entry in covers):
            errors.append(f"{where}: covers must be a list of ADD element ids")
            covers = []
        for element_id in covers:
            covers_owner.setdefault(element_id, []).append(intent_id)
        dependencies = item.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(isinstance(entry, str) for entry in dependencies):
            errors.append(f"{where}: dependencies must be a list of intent ids")
        # Bounded-empty is valid for all of these; only presence/type is enforced.
        _require_string_list(item, "scope", where, errors)
        _require_string_list(item, "non_goals", where, errors)
        _require_string_list(item, "evidence_refs", where, errors)
        if item.get("blocker") is not None and not isinstance(item.get("blocker"), str):
            errors.append(f"{where}: blocker must be a string or null")
        if not isinstance(item.get("ready"), bool):
            errors.append(f"{where}: ready must be a boolean")

    # Dangling references: dependency, covers, or evidence_refs pointing at an id/source that does not exist.
    for intent_id, item in by_id.items():
        for dependency in item.get("dependencies", []) or []:
            if isinstance(dependency, str) and dependency not in by_id:
                errors.append(f"intent {intent_id!r} depends on unknown intent {dependency!r}")
        for element_id in item.get("covers", []) or []:
            if isinstance(element_id, str) and element_id not in known_element_ids:
                errors.append(f"intent {intent_id!r} covers unknown ADD element {element_id!r}")
        for ref in item.get("evidence_refs", []) or []:
            if isinstance(ref, str) and ref not in known_reference_sources:
                errors.append(f"intent {intent_id!r} references unknown evidence/constraint source {ref!r}")

    cycle = _dependency_cycle(by_id)
    if cycle is not None:
        errors.append("intent dependency graph has a cycle: " + " -> ".join(cycle))

    for element_id, owners in covers_owner.items():
        if len(owners) <= 1:
            continue
        reasons = [by_id[owner].get("overlap_reason") for owner in owners]
        if not all(isinstance(reason, str) and reason.strip() for reason in reasons):
            errors.append(
                f"ADD element {element_id!r} is covered by multiple intents ({', '.join(sorted(owners))}) "
                "without an explicit overlap_reason on each"
            )

    non_implementation = document.get("non_implementation", [])
    if not isinstance(non_implementation, list):
        errors.append("non_implementation must be a list")
        non_implementation = []
    disposed_ids: set[str] = set()
    for index, item in enumerate(non_implementation):
        where = f"non_implementation[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        try:
            element_id = _require_str(item, "element_id", where)
            _require_str(item, "reason", where)
        except AddIntentsError as exc:
            errors.append(str(exc))
            continue
        if element_id not in known_element_ids:
            errors.append(f"{where}: element_id {element_id!r} is not a known ADD element")
        disposed_ids.add(element_id)

    covered_ids = set(covers_owner) | disposed_ids
    missing = sorted(required_element_ids - covered_ids)
    if missing:
        errors.append(
            "material ADD element(s) have no intent coverage and no explicit non-implementation disposition: "
            + ", ".join(missing)
        )

    for intent_id, item in by_id.items():
        if item.get("ready") is not True:
            continue
        blocker = item.get("blocker")
        if blocker is not None:
            errors.append(f"intent {intent_id!r} cannot be ready while a blocker is recorded: {blocker!r}")
        if not item.get("covers") and not item.get("scope"):
            warnings.append(f"intent {intent_id!r} is ready but declares neither scope nor covered ADD elements")

    # Snapshot/projection digests the intent set carries forward from the ADD
    # must actually be entries the ADD recorded, and must still be provably
    # fresh -- a stale or fabricated snapshot_refs entry blocks readiness.
    snapshot_refs = document.get("snapshot_refs", [])
    if not isinstance(snapshot_refs, list):
        errors.append("snapshot_refs must be a list")
        snapshot_refs = []
    else:
        add_snapshot_entries = {
            (item.get("source"), item.get("projection")): item
            for item in (add_document.get("evidence", []) or [])
            if isinstance(item, dict) and item.get("kind") == EVIDENCE_KIND_SNAPSHOT
        }
        for index, item in enumerate(snapshot_refs):
            where = f"snapshot_refs[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            errors.extend(_validate_snapshot_evidence_entry(item, where))
            matching = add_snapshot_entries.get((item.get("source"), item.get("projection")))
            if (
                matching is None
                or matching.get("snapshot_digest") != item.get("snapshot_digest")
                or matching.get("projection_digest") != item.get("projection_digest")
            ):
                errors.append(f"{where}: does not match a snapshot evidence entry recorded on the approved ADD")
        if snapshot_refs and not any(
            error.startswith("snapshot_refs[") for error in errors
        ):
            errors.extend(_snapshot_evidence_freshness_errors(root, snapshot_refs))

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


# --- Intent -> OpenSpec handoff --------------------------------------------


def prepare_handoff(
    root: Path,
    *,
    add_path: Path,
    intents_path: Path,
    intent_ids: list[str],
    out: Path,
    group_reason: str | None = None,
) -> dict[str, Any]:
    """Produce a bounded OpenSpec authoring-input envelope for selected ready intent(s).

    This is a thin, deterministic packaging step: it never invents outcome
    prose, never talks to GitHub/OpenSpec authoring itself, and only carries
    forward already-approved ADD/intent content plus evidence references so
    OpenSpec authoring does not have to rediscover them. Grouping more than
    one intent into a single envelope requires an explicit `group_reason`
    (the ordinary OpenSpec split test still governs whether that grouping is
    actually justified).
    """
    if not intent_ids:
        raise AddIntentsError("prepare-handoff requires at least one intent id")
    if len(intent_ids) > 1 and not (isinstance(group_reason, str) and group_reason.strip()):
        raise AddIntentsError(
            "handing off more than one intent requires an explicit group_reason justifying why they are "
            "inseparable (see the OpenSpec split test in openspec/specs/openspec-authoring/spec.md)"
        )

    add_document = _load_json(add_path, "ADD document")
    add_report = validate_add(root, add_path, check_freshness=True)
    if not add_report.ok:
        raise AddIntentsError("cannot prepare a handoff from an ADD that fails validation: " + "; ".join(add_report.errors))
    if add_document.get("approved") is not True:
        raise AddIntentsError("cannot prepare a handoff from an ADD that is not approved")
    if add_report.freshness not in (None, "fresh"):
        raise AddIntentsError(f"cannot prepare a handoff from a {add_report.freshness} ADD")

    intents_report = validate_intents(root, intents_path, add_path=add_path)
    if not intents_report.ok:
        raise AddIntentsError(
            "cannot prepare a handoff from an intent set that fails validation: " + "; ".join(intents_report.errors)
        )

    intents_document = _load_json(intents_path, "intent-set document")
    by_id = {
        item["id"]: item
        for item in intents_document.get("intents", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    selected: list[dict[str, Any]] = []
    for intent_id in intent_ids:
        item = by_id.get(intent_id)
        if item is None:
            raise AddIntentsError(f"intent {intent_id!r} is not present in {intents_path}")
        if item.get("ready") is not True:
            raise AddIntentsError(f"intent {intent_id!r} is not ready (blocker={item.get('blocker')!r})")
        selected.append(item)

    covered_element_ids = sorted(
        {element_id for item in selected for element_id in (item.get("covers") or []) if isinstance(element_id, str)}
    )
    material_elements = [
        element
        for element in add_document.get("elements", [])
        if isinstance(element, dict) and element.get("id") in covered_element_ids
    ]
    evidence_sources = sorted(
        {ref for item in selected for ref in (item.get("evidence_refs") or []) if isinstance(ref, str)}
    )
    referenced_evidence = [
        item for item in add_document.get("evidence", []) or [] if isinstance(item, dict) and item.get("source") in evidence_sources
    ]

    approval = add_document.get("approval") if isinstance(add_document.get("approval"), dict) else {}
    envelope: dict[str, Any] = {
        "version": HANDOFF_SCHEMA_VERSION,
        "created_at": utc_now(),
        "add_id": add_document.get("add_id"),
        "business_context": intents_document.get("business_context", ""),
        "intent_ids": list(intent_ids),
        "group_reason": group_reason.strip() if isinstance(group_reason, str) and group_reason.strip() else None,
        "intents": [
            {
                "id": item["id"],
                "goal": item.get("goal"),
                "scope": item.get("scope", []),
                "non_goals": item.get("non_goals", []),
                "covers": item.get("covers", []),
                "dependencies": item.get("dependencies", []),
                "evidence_refs": item.get("evidence_refs", []),
            }
            for item in selected
        ],
        "approved_add_digest": approval.get("digest"),
        "add_target_repository": add_document.get("target_repository"),
        "add_prepared_against": add_document.get("prepared_against"),
        "material_elements": material_elements,
        "reused_constraints": add_document.get("reused_constraints", []),
        "evidence": referenced_evidence,
        "snapshot_refs": intents_document.get("snapshot_refs", []),
        # Bindings used only to detect staleness later; never trusted on their
        # own without recomputation against the then-current ADD/intents.
        "source_bindings": {
            "add_digest": add_content_digest(add_document),
            "intents_digest": _content_digest(intents_document),
        },
    }
    envelope["digest"] = _content_digest({key: value for key, value in envelope.items() if key != "digest"})
    _write_json(out, envelope)
    return envelope


def check_handoff_staleness(root: Path, *, envelope_path: Path, add_path: Path, intents_path: Path) -> ValidationReport:
    """Re-prove a previously prepared handoff envelope against current ADD/intents/snapshot state.

    Never trusts the envelope's own recorded digests as proof of anything
    beyond internal consistency; recomputes each binding from the current ADD
    and intent-set files, plus any snapshot evidence they carry, and reports
    `freshness="stale-needs-regeneration"` rather than silently letting a
    consumer rely on a stale authoring input.
    """
    envelope = _load_json(envelope_path, "handoff envelope")
    errors: list[str] = []
    warnings: list[str] = []

    if envelope.get("version") != HANDOFF_SCHEMA_VERSION:
        errors.append(f"unsupported handoff schema version: {envelope.get('version')!r}")

    recomputed_envelope_digest = _content_digest({key: value for key, value in envelope.items() if key != "digest"})
    if envelope.get("digest") != recomputed_envelope_digest:
        errors.append("handoff envelope digest does not match its own content (the file was hand-edited or corrupted)")

    bindings = envelope.get("source_bindings") if isinstance(envelope.get("source_bindings"), dict) else {}

    add_document = _load_json(add_path, "ADD document")
    add_report = validate_add(root, add_path, check_freshness=True)
    if not add_report.ok or add_document.get("approved") is not True:
        errors.append("handoff is stale: the parent ADD is no longer validly approved")
    elif add_report.freshness not in (None, "fresh"):
        errors.append(f"handoff is stale: the parent ADD is {add_report.freshness}")
    elif add_content_digest(add_document) != bindings.get("add_digest"):
        errors.append("handoff is stale: the ADD content has changed since this handoff was prepared")

    intents_document = _load_json(intents_path, "intent-set document")
    intents_report = validate_intents(root, intents_path, add_path=add_path)
    if not intents_report.ok:
        errors.append("handoff is stale: the intent set no longer passes validation")
    elif _content_digest(intents_document) != bindings.get("intents_digest"):
        errors.append("handoff is stale: the intent set has changed since this handoff was prepared")

    by_id = {
        item["id"]: item
        for item in intents_document.get("intents", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for intent_id in envelope.get("intent_ids", []) or []:
        item = by_id.get(intent_id)
        if item is None:
            errors.append(f"handoff is stale: intent {intent_id!r} no longer exists in the intent set")
        elif item.get("ready") is not True:
            errors.append(f"handoff is stale: intent {intent_id!r} is no longer ready")

    snapshot_refs = envelope.get("snapshot_refs")
    if isinstance(snapshot_refs, list) and snapshot_refs:
        errors.extend(_snapshot_evidence_freshness_errors(root, snapshot_refs))

    return ValidationReport(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        freshness="fresh" if not errors else "stale-needs-regeneration",
    )


# --- CLI ---------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="ADD -> Intents pre-authoring pipeline: scaffold and validate.")
    sub = parser.add_subparsers(dest="command", required=True)

    new_add_parser = sub.add_parser("new-add", help="scaffold a new ADD document bound to an exact revision")
    new_add_parser.add_argument("--add-id", required=True)
    new_add_parser.add_argument("--requirement-file", required=True, type=Path)
    new_add_parser.add_argument("--target-repository", required=True)
    new_add_parser.add_argument("--out", required=True, type=Path)
    new_add_parser.add_argument("--prepared-against", help="defaults to the current worktree HEAD")

    validate_add_parser = sub.add_parser("validate-add", help="run deterministic structural/provenance/freshness/approval checks on an ADD")
    validate_add_parser.add_argument("path", type=Path)
    validate_add_parser.add_argument("--no-freshness-check", action="store_true")

    approve_add_parser = sub.add_parser("approve-add", help="bind human approval to the ADD's exact current content digest")
    approve_add_parser.add_argument("path", type=Path)
    approve_add_parser.add_argument("--approved-by", default=None)

    decompose_parser = sub.add_parser("decompose", help="scaffold an intent-set document from an approved, fresh ADD")
    decompose_parser.add_argument("--add", required=True, type=Path, dest="add_path")
    decompose_parser.add_argument("--out", required=True, type=Path)
    decompose_parser.add_argument("--business-context", default="")

    validate_intents_parser = sub.add_parser("validate-intents", help="run deterministic structural/binding gates on an intent set")
    validate_intents_parser.add_argument("path", type=Path)
    validate_intents_parser.add_argument("--add", required=True, type=Path, dest="add_path")

    prepare_handoff_parser = sub.add_parser(
        "prepare-handoff", help="produce a bounded OpenSpec authoring-input envelope for ready intent(s)"
    )
    prepare_handoff_parser.add_argument("--add", required=True, type=Path, dest="add_path")
    prepare_handoff_parser.add_argument("--intents", required=True, type=Path, dest="intents_path")
    prepare_handoff_parser.add_argument("--intent-id", required=True, action="append", dest="intent_ids")
    prepare_handoff_parser.add_argument("--group-reason", default=None)
    prepare_handoff_parser.add_argument("--out", required=True, type=Path)

    validate_handoff_parser = sub.add_parser(
        "validate-handoff", help="re-prove a previously prepared handoff envelope against current ADD/intents/snapshot state"
    )
    validate_handoff_parser.add_argument("path", type=Path)
    validate_handoff_parser.add_argument("--add", required=True, type=Path, dest="add_path")
    validate_handoff_parser.add_argument("--intents", required=True, type=Path, dest="intents_path")

    args = parser.parse_args()
    root = current_worktree_root()

    try:
        if args.command == "new-add":
            payload = new_add(
                root,
                add_id=args.add_id,
                requirement_file=args.requirement_file,
                target_repository=args.target_repository,
                out=args.out,
                prepared_against=args.prepared_against,
            )
            print(f"ADD scaffolded: {payload['add_id']} -> {args.out}")
            return 0
        if args.command == "approve-add":
            payload = approve_add(root, args.path, approved_by=args.approved_by)
            print(json.dumps(
                {"ok": True, "add_id": payload["add_id"], "content_digest": payload["approval"]["digest"]},
                ensure_ascii=False, indent=2,
            ))
            return 0
        if args.command == "validate-add":
            document = _load_json(args.path, "ADD document")
            report = validate_add(root, args.path, check_freshness=not args.no_freshness_check)
            payload = report.to_dict()
            payload["content_digest"] = add_content_digest(document)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0 if report.ok else 2
        if args.command == "decompose":
            payload = decompose(root, add_path=args.add_path, out=args.out, business_context=args.business_context)
            print(f"Intent set scaffolded for {payload['add_id']} -> {args.out}")
            return 0
        if args.command == "validate-intents":
            report = validate_intents(root, args.path, add_path=args.add_path)
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            return 0 if report.ok else 2
        if args.command == "prepare-handoff":
            payload = prepare_handoff(
                root,
                add_path=args.add_path,
                intents_path=args.intents_path,
                intent_ids=args.intent_ids,
                out=args.out,
                group_reason=args.group_reason,
            )
            print(f"Handoff envelope scaffolded for {', '.join(args.intent_ids)} -> {args.out}")
            return 0
        if args.command == "validate-handoff":
            report = check_handoff_staleness(
                root, envelope_path=args.path, add_path=args.add_path, intents_path=args.intents_path
            )
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            return 0 if report.ok else 2
        raise AddIntentsError(f"unsupported command: {args.command}")  # pragma: no cover - argparse enforces the choice set
    except AddIntentsError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
