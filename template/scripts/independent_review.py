"""Prepare and validate provider-neutral independent review evidence.

This module deliberately does not launch a model or publish anything.  A
runtime adapter consumes the generated request in a fresh read-only context and
returns a report through ``record``.  Keeping the boundary file-backed makes
the provider replaceable and lets the completion lifecycle verify exactly what
was reviewed without inventing independence when no reviewer was available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, read_platform_config, run_git, utc_now


SCHEMA_VERSION = 1
PERSPECTIVES = ("spec-fidelity", "engineering-quality")
FINDING_SEVERITIES = {"material", "advisory"}
MATERIAL_DISPOSITIONS = {"fixed", "rejected", "blocker"}
REQUEST_FILE = "independent-review-request.json"
REPORTS_DIR = "independent-reviews"


class IndependentReviewError(RuntimeError):
    """A review request or report cannot be trusted as lifecycle evidence."""


def request_path(change: Path) -> Path:
    return change / REQUEST_FILE


def reports_dir(change: Path) -> Path:
    return change / REPORTS_DIR


def report_path(change: Path, perspective: str) -> Path:
    return reports_dir(change) / f"{perspective}.json"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IndependentReviewError(f"missing {label}: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise IndependentReviewError(f"unreadable {label}: {path}") from exc
    if not isinstance(value, dict):
        raise IndependentReviewError(f"{label} must contain a JSON object: {path}")
    return value


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _candidate_field(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    required = ("base_ref", "base_head", "candidate_head", "diff_sha256")
    if any(not _nonempty_string(value.get(field)) for field in required):
        return None
    return {field: value[field].strip() for field in required}


def candidate_identity(root: Path, base_ref: str) -> dict[str, str]:
    """Return the committed candidate identity a reviewer must bind to."""
    base = run_git(["rev-parse", "--verify", base_ref], cwd=root, check=False)
    if base.returncode:
        raise IndependentReviewError(f"cannot resolve independent-review base {base_ref!r}")
    candidate = run_git(["rev-parse", "--verify", "HEAD"], cwd=root, check=False)
    if candidate.returncode:
        raise IndependentReviewError("cannot resolve independent-review candidate HEAD")
    diff = run_git(["diff", "--binary", "--no-ext-diff", f"{base_ref}...HEAD"], cwd=root, check=False)
    if diff.returncode:
        raise IndependentReviewError(f"cannot calculate independent-review diff for {base_ref!r}...HEAD")
    return {
        "base_ref": base_ref,
        "base_head": base.stdout.strip(),
        "candidate_head": candidate.stdout.strip(),
        "diff_sha256": hashlib.sha256(diff.stdout.encode("utf-8")).hexdigest(),
    }


def _existing_paths(root: Path, paths: list[Path]) -> list[str]:
    return [str(path.relative_to(root)) for path in paths if path.is_file()]


def review_inputs(root: Path, change: Path, perspective: str) -> dict[str, Any]:
    contract_paths = _existing_paths(
        root,
        [change / name for name in ("proposal.md", "design.md", "tasks.md")]
        + sorted((change / "specs").glob("**/*.md")),
    )
    if perspective == "spec-fidelity":
        return {
            "paths": contract_paths,
            "objective": "Compare the exact candidate with the accepted current specs and active delta. Report missing, incorrect, or contradictory contract behavior.",
        }
    guidance_paths = _existing_paths(
        root,
        [root / "AGENTS.md", root / "docs" / "engineering" / "agent-workflow.md", root / "docs" / "engineering" / "openspec-workflow.md", root / "docs" / "engineering" / "project-rules.md"],
    )
    return {
        "paths": sorted(set(contract_paths + guidance_paths)),
        "objective": "Review correctness, maintainability, safety, and architecture risks that are not necessarily expressed by the active delta.",
    }


def prepare_request(root: Path, change: Path, base_ref: str) -> dict[str, Any]:
    if not change.is_dir():
        raise IndependentReviewError(f"active OpenSpec change not found: {change}")
    candidate = candidate_identity(root, base_ref)
    request = {
        "schema_version": SCHEMA_VERSION,
        "request_id": str(uuid.uuid4()),
        "prepared_at": utc_now(),
        "change": str(change.relative_to(root)),
        "candidate": candidate,
        "fresh_context_required": True,
        "reviewer_constraints": {
            "write_access": False,
            "forbidden_actions": ["publish code", "mutate Development Backlog or Project state", "archive the change", "set completion state"],
        },
        "perspectives": {perspective: review_inputs(root, change, perspective) for perspective in PERSPECTIVES},
        "report_contract": {
            "schema_version": SCHEMA_VERSION,
            "output_directory": str(reports_dir(change).relative_to(root)),
            "required_perspectives": list(PERSPECTIVES),
        },
    }
    atomic_write_text(request_path(change), json.dumps(request, indent=2, sort_keys=True) + "\n")
    return request


def _validate_request(request: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if request.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"request schema_version must be {SCHEMA_VERSION}")
    if not _nonempty_string(request.get("request_id")):
        errors.append("request_id is required")
    if _candidate_field(request.get("candidate")) is None:
        errors.append("request candidate identity is incomplete")
    if request.get("fresh_context_required") is not True:
        errors.append("request must require a fresh review context")
    perspectives = request.get("perspectives")
    if not isinstance(perspectives, dict) or set(perspectives) != set(PERSPECTIVES):
        errors.append("request must define exactly spec-fidelity and engineering-quality perspectives")
    return errors


def _validate_report(report: dict[str, Any], request: dict[str, Any], perspective: str) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{perspective}: report schema_version must be {SCHEMA_VERSION}")
    if report.get("perspective") != perspective:
        errors.append(f"{perspective}: report perspective does not match its destination")
    if report.get("request_id") != request.get("request_id"):
        errors.append(f"{perspective}: report is not bound to the prepared request")
    if report.get("candidate") != request.get("candidate"):
        errors.append(f"{perspective}: report candidate identity does not match the prepared request")

    reviewer = report.get("reviewer")
    if not isinstance(reviewer, dict):
        errors.append(f"{perspective}: reviewer metadata is required")
    else:
        if not _nonempty_string(reviewer.get("runtime")):
            errors.append(f"{perspective}: reviewer runtime is required")
        if not _nonempty_string(reviewer.get("context_id")):
            errors.append(f"{perspective}: reviewer context_id is required")
        if reviewer.get("fresh_context") is not True:
            errors.append(f"{perspective}: reviewer must attest to a fresh context")
        if reviewer.get("write_access") is not False:
            errors.append(f"{perspective}: reviewer must attest to read-only execution")

    availability = report.get("availability")
    findings = report.get("findings")
    if availability not in {"available", "unavailable"}:
        errors.append(f"{perspective}: availability must be available or unavailable")
        return errors
    if availability == "unavailable":
        if not _nonempty_string(report.get("limitation")):
            errors.append(f"{perspective}: unavailable review must record a limitation")
        if findings != []:
            errors.append(f"{perspective}: unavailable review must record an empty findings list")
        return errors
    if not isinstance(findings, list):
        errors.append(f"{perspective}: available review findings must be a list")
        return errors

    for index, finding in enumerate(findings):
        prefix = f"{perspective}: finding {index + 1}"
        if not isinstance(finding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _nonempty_string(finding.get("id")):
            errors.append(f"{prefix} id is required")
        if finding.get("severity") not in FINDING_SEVERITIES:
            errors.append(f"{prefix} severity must be material or advisory")
        if not _nonempty_string(finding.get("summary")):
            errors.append(f"{prefix} summary is required")
        if not _nonempty_string(finding.get("evidence")):
            errors.append(f"{prefix} evidence is required")
        if finding.get("severity") == "material":
            disposition = finding.get("disposition")
            if not isinstance(disposition, dict) or disposition.get("status") not in MATERIAL_DISPOSITIONS:
                errors.append(f"{prefix} material finding needs a fixed, rejected, or blocker disposition")
            elif not _nonempty_string(disposition.get("rationale")):
                errors.append(f"{prefix} material finding disposition needs a rationale")
    return errors


def validate_evidence(root: Path, change: Path) -> dict[str, Any]:
    request = _read_json(request_path(change), "independent review request")
    errors = _validate_request(request)
    candidate = _candidate_field(request.get("candidate"))
    if candidate is not None:
        try:
            current = candidate_identity(root, candidate["base_ref"])
        except IndependentReviewError as exc:
            errors.append(str(exc))
        else:
            if current != candidate:
                errors.append("independent review request is stale for the current candidate/base identity; prepare a fresh request")

    unavailable: list[str] = []
    material_blockers: list[str] = []
    for perspective in PERSPECTIVES:
        try:
            report = _read_json(report_path(change, perspective), f"{perspective} review report")
        except IndependentReviewError as exc:
            errors.append(str(exc))
            continue
        errors.extend(_validate_report(report, request, perspective))
        if report.get("availability") == "unavailable":
            unavailable.append(f"{perspective}: {report.get('limitation', 'no limitation recorded')}")
        findings = report.get("findings")
        if isinstance(findings, list):
            for finding in findings:
                if not isinstance(finding, dict) or finding.get("severity") != "material":
                    continue
                disposition = finding.get("disposition")
                if not isinstance(disposition, dict) or disposition.get("status") == "blocker":
                    material_blockers.append(f"{perspective}:{finding.get('id', 'unnamed finding')}")
    if unavailable:
        errors.append("independent review unavailable: " + "; ".join(unavailable))
    if material_blockers:
        errors.append("unresolved material independent-review findings: " + ", ".join(material_blockers))
    if errors:
        raise IndependentReviewError("; ".join(errors))
    return {"request_id": request["request_id"], "candidate": request["candidate"], "perspectives": list(PERSPECTIVES)}


def review_is_required(root: Path, change: Path) -> bool:
    settings = read_platform_config(root).get("independent_review", {})
    return isinstance(settings, dict) and settings.get("enabled") is True and (change / ".managed-task.json").is_file()


def require_review_evidence(root: Path, change: Path) -> None:
    """Enforce enabled material-change review evidence at archive readiness."""
    if review_is_required(root, change):
        try:
            validate_evidence(root, change)
        except IndependentReviewError as exc:
            raise SystemExit(f"{change.name}: independent review is required but not ready: {exc}") from exc


def record_report(root: Path, change: Path, source: Path) -> Path:
    request = _read_json(request_path(change), "independent review request")
    request_errors = _validate_request(request)
    if request_errors:
        raise IndependentReviewError("; ".join(request_errors))
    candidate = _candidate_field(request.get("candidate"))
    assert candidate is not None  # _validate_request above established this.
    if candidate_identity(root, candidate["base_ref"]) != candidate:
        raise IndependentReviewError("independent review request is stale for the current candidate/base identity; prepare a fresh request")
    report = _read_json(source, "independent review report")
    perspective = report.get("perspective")
    if perspective not in PERSPECTIVES:
        raise IndependentReviewError("independent review report must name a supported perspective")
    errors = _validate_report(report, request, perspective)
    if errors:
        raise IndependentReviewError("; ".join(errors))
    destination = report_path(change, perspective)
    atomic_write_text(destination, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate independent OpenSpec review evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "check", "record"):
        command = subparsers.add_parser(name)
        command.add_argument("change", help="active OpenSpec change name")
        if name == "prepare":
            command.add_argument("--base", default="origin/main", help="immutable base ref to review against (default: origin/main)")
        if name == "record":
            command.add_argument("--report", required=True, type=Path, help="runtime-produced report JSON")
    args = parser.parse_args()
    root = current_worktree_root()
    change = root / "openspec" / "changes" / args.change
    try:
        if args.command == "prepare":
            request = prepare_request(root, change, args.base)
            print(f"Prepared independent review request {request['request_id']} for {args.change}.")
        elif args.command == "record":
            destination = record_report(root, change, args.report)
            print(f"Recorded independent review report: {destination.relative_to(root)}")
        else:
            result = validate_evidence(root, change)
            print(f"Independent review evidence is ready for {args.change}: {result['request_id']}")
    except IndependentReviewError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
