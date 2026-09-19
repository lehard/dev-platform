#!/usr/bin/env python3
"""Deterministic scaffolding and gates for the ADD -> Intents pre-authoring pipeline.

Architecture Design Delta (ADD) and Intent documents are bounded, machine-local
pre-authoring evidence -- not a second backlog, implementation contract, or
current-system registry (see ``dev-platform/capabilities/add-intents.md``).
This module only proves *structural* properties: schema validity, provenance,
freshness, dependency-graph integrity, and ADD-element coverage. It
deliberately never claims that an ADD is the right design or that a
decomposition is the best possible partition -- that judgment stays with the
human/agent review the capability instructions describe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, run_git, utc_now

ADD_SCHEMA_VERSION = 1
INTENTS_SCHEMA_VERSION = 1

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
    }
    _write_json(out, payload)
    return payload


def _require_str(entry: dict[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AddIntentsError(f"{where}: {key!r} must be a non-empty string")
    return value


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


def validate_add(root: Path, path: Path, *, check_freshness: bool = True) -> ValidationReport:
    document = _load_json(path, "ADD document")
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
            _require_str(item, "kind", where)
            _require_str(item, "digest", where)
        except AddIntentsError as exc:
            errors.append(str(exc))

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

    if document.get("approved") is True:
        if open_choices:
            errors.append(f"ADD cannot be approved while {open_choices} unresolved consequential choice(s) remain")
        if unresolved_contradictions:
            errors.append(f"ADD cannot be approved while {unresolved_contradictions} unresolved contradiction(s) remain")
        if not elements:
            warnings.append("ADD is approved but records no design elements; confirm a bounded delta was actually needed")
    elif document.get("approved") is not False:
        errors.append("approved must be a boolean")

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings), freshness=freshness)


# --- Intents ---------------------------------------------------------------


def decompose(root: Path, *, add_path: Path, out: Path, business_context: str = "") -> dict[str, Any]:
    add_document = _load_json(add_path, "ADD document")
    report = validate_add(root, add_path, check_freshness=False)
    if not report.ok:
        raise AddIntentsError("cannot decompose an ADD that fails structural validation: " + "; ".join(report.errors))
    if add_document.get("approved") is not True:
        raise AddIntentsError("cannot decompose an ADD that is not approved yet")
    payload: dict[str, Any] = {
        "version": INTENTS_SCHEMA_VERSION,
        "add_id": add_document["add_id"],
        "business_context": business_context,
        "created_at": utc_now(),
        "intents": [],
        "non_implementation": [],
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

    required_element_ids = {
        item.get("id")
        for item in add_document.get("elements", [])
        if isinstance(item, dict) and item.get("status") in COVERAGE_REQUIRED_STATUSES and isinstance(item.get("id"), str)
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

    # Dangling references: dependency or covers pointing at an id that does not exist.
    known_element_ids = {
        item.get("id") for item in add_document.get("elements", []) if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for intent_id, item in by_id.items():
        for dependency in item.get("dependencies", []) or []:
            if isinstance(dependency, str) and dependency not in by_id:
                errors.append(f"intent {intent_id!r} depends on unknown intent {dependency!r}")
        for element_id in item.get("covers", []) or []:
            if isinstance(element_id, str) and element_id not in known_element_ids:
                errors.append(f"intent {intent_id!r} covers unknown ADD element {element_id!r}")

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

    return ValidationReport(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


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

    validate_add_parser = sub.add_parser("validate-add", help="run deterministic structural/provenance/freshness checks on an ADD")
    validate_add_parser.add_argument("path", type=Path)
    validate_add_parser.add_argument("--no-freshness-check", action="store_true")

    decompose_parser = sub.add_parser("decompose", help="scaffold an intent-set document from an approved ADD")
    decompose_parser.add_argument("--add", required=True, type=Path, dest="add_path")
    decompose_parser.add_argument("--out", required=True, type=Path)
    decompose_parser.add_argument("--business-context", default="")

    validate_intents_parser = sub.add_parser("validate-intents", help="run deterministic structural gates on an intent set")
    validate_intents_parser.add_argument("path", type=Path)
    validate_intents_parser.add_argument("--add", required=True, type=Path, dest="add_path")

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
        if args.command == "validate-add":
            report = validate_add(root, args.path, check_freshness=not args.no_freshness_check)
        elif args.command == "decompose":
            payload = decompose(root, add_path=args.add_path, out=args.out, business_context=args.business_context)
            print(f"Intent set scaffolded for {payload['add_id']} -> {args.out}")
            return 0
        elif args.command == "validate-intents":
            report = validate_intents(root, args.path, add_path=args.add_path)
        else:  # pragma: no cover - argparse enforces the choice set
            raise AddIntentsError(f"unsupported command: {args.command}")
    except AddIntentsError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
