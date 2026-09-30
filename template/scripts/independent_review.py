"""Prepare and validate provider-neutral independent review evidence.

This module owns the file-backed evidence contract: the review request, the
immutable per-perspective reports, and the separate disposition record.  It
does not launch a model or publish anything itself.  ``run`` delegates to
``independent_review_runner``, which launches each perspective as a fresh
read-only process and writes platform-observed reports back through this
contract.  Keeping the boundary file-backed makes the provider replaceable and
lets the completion lifecycle verify exactly what was reviewed without
inventing independence when no reviewer was available.
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
# Legacy in-report dispositions stay readable where review is not required.
MATERIAL_DISPOSITIONS = {"fixed", "rejected", "blocker"}
# A fix changes the candidate and therefore needs a fresh review, so it is not
# recordable against the reviewed report.
RECORDABLE_DISPOSITIONS = ("rejected", "blocker")
REQUEST_FILE = "independent-review-request.json"
REPORTS_DIR = "independent-reviews"
DISPOSITIONS_FILE = "independent-review-dispositions.json"
PLATFORM_OBSERVED = "platform-observed"
# The only runtime-local usage fields a report may carry, per reviewer runtime.
RUNTIME_USAGE_FIELDS = {
    "claude-code-print": (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens",
        "num_turns", "duration_ms", "duration_api_ms",
    ),
    "codex-exec": ("input_tokens", "cached_input_tokens", "output_tokens"),
}

STATE_NOT_REQUIRED = "not-required"
STATE_MISSING = "missing"
STATE_STALE = "stale"
STATE_BLOCKED = "blocked"
STATE_READY = "ready"


class IndependentReviewError(RuntimeError):
    """A review request or report cannot be trusted as lifecycle evidence."""


def request_path(change: Path) -> Path:
    return change / REQUEST_FILE


def reports_dir(change: Path) -> Path:
    return change / REPORTS_DIR


def report_path(change: Path, perspective: str) -> Path:
    return reports_dir(change) / f"{perspective}.json"


def dispositions_path(change: Path) -> Path:
    return change / DISPOSITIONS_FILE


def run_command(change_name: str) -> str:
    return f"python3 scripts/independent_review.py run {change_name}"


def preflight_command(change_name: str | None = None) -> str:
    return "python3 scripts/independent_review.py preflight" + (f" {change_name}" if change_name else "")


def dispose_command(change_name: str, perspective: str, finding: str) -> str:
    return (
        f"python3 scripts/independent_review.py dispose {change_name} --perspective {perspective} "
        f"--finding {finding} --status rejected --rationale '<why this finding does not apply>'"
    )


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


def canonical_change_name(change: Path) -> str:
    """The OpenSpec change name, also for a dated archive directory."""
    provenance = change / ".managed-task.json"
    if provenance.is_file():
        try:
            payload = json.loads(provenance.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict) and _nonempty_string(payload.get("change")):
            return payload["change"].strip()
    if change.parent.name == "archive" and len(change.name) > 11 and change.name[10] == "-":
        return change.name[11:]
    return change.name


def resolve_change(root: Path, name: str) -> Path:
    """Locate a change whether it is still active or already archived."""
    active = root / "openspec" / "changes" / name
    if active.is_dir():
        return active
    archive = root / "openspec" / "changes" / "archive"
    matches = sorted(path for path in archive.glob(f"*-{name}") if path.is_dir() and canonical_change_name(path) == name) if archive.is_dir() else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise IndependentReviewError(f"archived OpenSpec change {name!r} is ambiguous: " + ", ".join(str(path) for path in matches))
    return active


def candidate_identity(root: Path, base_ref: str) -> dict[str, str]:
    """Return the committed candidate provenance a reviewer is launched against."""
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


def task_content(root: Path, change: Path, base_ref: str) -> dict[str, Any]:
    """Review-scoped task-content identity for the committed candidate."""
    from task_content_identity import review_content_identity

    proof = review_content_identity(root, canonical_change_name(change), base_ref)
    if proof is None:
        raise IndependentReviewError(f"cannot calculate independent-review task-content identity against {base_ref!r}")
    return proof


def lifecycle_path_partition(root: Path, change: Path, base_ref: str, merge_base: str) -> tuple[list[str], list[str]]:
    """``(reviewed, excluded_lifecycle)`` changed paths for the reviewer context.

    The reviewed paths are exactly those the review task-content identity
    binds; lifecycle receipts, review evidence and archive-derived spec
    materialization are excluded so a reviewer never reviews its own evidence.
    """
    from task_content_identity import review_path_partition

    partition = review_path_partition(root, canonical_change_name(change), base_ref, merge_base)
    if partition is None:
        raise IndependentReviewError(f"cannot list the independent-review candidate paths against {base_ref!r}")
    return partition


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
        raise IndependentReviewError(f"OpenSpec change not found: {change}")
    candidate = candidate_identity(root, base_ref)
    content = task_content(root, change, base_ref)
    _, excluded = lifecycle_path_partition(root, change, base_ref, str(content["base"]))
    request = {
        "schema_version": SCHEMA_VERSION,
        "request_id": str(uuid.uuid4()),
        "prepared_at": utc_now(),
        "change": str(change.relative_to(root)),
        "candidate": candidate,
        "task_content": content,
        # Additive audit field: lifecycle evidence withheld from the reviewer.
        "excluded_lifecycle_paths": excluded,
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


def request_staleness(root: Path, change: Path, request: dict[str, Any]) -> str | None:
    """Return why the request no longer identifies the current candidate, if it does not.

    A content-bound request is accepted across an archive move and a clean,
    irrelevant main merge; any other task-owned change makes it stale.  A
    legacy request without task content keeps the exact identity comparison.
    """
    candidate = _candidate_field(request.get("candidate"))
    if candidate is None:
        return "request candidate identity is incomplete"
    recorded = request.get("task_content")
    if isinstance(recorded, dict):
        from task_content_identity import equivalent_proofs

        try:
            current = task_content(root, change, candidate["base_ref"])
        except IndependentReviewError as exc:
            return str(exc)
        if equivalent_proofs(root, recorded, current):
            return None
        return "independent review request is stale: the task content changed after review"
    try:
        current_candidate = candidate_identity(root, candidate["base_ref"])
    except IndependentReviewError as exc:
        return str(exc)
    if current_candidate != candidate:
        return "independent review request is stale for the current candidate/base identity; prepare a fresh request"
    return None


def report_digest(report: dict[str, Any]) -> str:
    """Canonical digest of an immutable reviewer report."""
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _validate_finding(prefix: str, finding: Any, *, legacy_dispositions: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(finding, dict):
        return [f"{prefix} must be an object"]
    if not _nonempty_string(finding.get("id")):
        errors.append(f"{prefix} id is required")
    if finding.get("severity") not in FINDING_SEVERITIES:
        errors.append(f"{prefix} severity must be material or advisory")
    if not _nonempty_string(finding.get("summary")):
        errors.append(f"{prefix} summary is required")
    if not _nonempty_string(finding.get("evidence")):
        errors.append(f"{prefix} evidence is required")
    if legacy_dispositions and finding.get("severity") == "material":
        disposition = finding.get("disposition")
        if not isinstance(disposition, dict) or disposition.get("status") not in MATERIAL_DISPOSITIONS:
            errors.append(f"{prefix} material finding needs a fixed, rejected, or blocker disposition")
        elif not _nonempty_string(disposition.get("rationale")):
            errors.append(f"{prefix} material finding disposition needs a rationale")
    return errors


def _usage_field(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and value.get("status") == "measured" and value.get("source") == "runtime-confirmed":
        number = value.get("value")
        if isinstance(number, int) and not isinstance(number, bool) and number >= 0:
            return {"value": number, "source": "runtime-confirmed", "status": "measured"}
    return {"value": None, "source": "unknown", "status": "unknown"}


def read_runtime_usage(report: dict[str, Any]) -> dict[str, Any]:
    """Read a report's optional runtime-local usage block leniently.

    Reports written before the block existed, or carrying a malformed block,
    read as unknown rather than zero.  Only a known reviewer runtime and its
    allowlisted fields are read; anything else in the block is dropped.  The
    block is informational: it never
    participates in acceptance, freshness or disposition binding, so report
    validation does not reject a report because of it.
    """
    block = report.get("runtime_usage")
    if not isinstance(block, dict):
        return {"runtime": None, "status": "unknown", "reason": "historical-record-without-field", "fields": {}}
    runtime = block.get("runtime")
    if runtime not in RUNTIME_USAGE_FIELDS:
        return {"runtime": None, "status": "unknown", "reason": "unsupported-runtime", "fields": {}}
    raw = block.get("fields") if isinstance(block.get("fields"), dict) else {}
    fields = {name: _usage_field(raw.get(name)) for name in RUNTIME_USAGE_FIELDS[runtime]}
    if any(field["status"] == "measured" for field in fields.values()):
        return {"runtime": runtime, "status": "measured", "fields": fields}
    return {"runtime": runtime, "status": "unknown", "reason": "unsupported-or-malformed", "fields": fields}


def _validate_report(report: dict[str, Any], request: dict[str, Any], perspective: str, *, required: bool = False) -> list[str]:
    # The optional ``runtime_usage`` block is deliberately not validated here; see read_runtime_usage.
    errors: list[str] = []
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{perspective}: report schema_version must be {SCHEMA_VERSION}")
    if report.get("perspective") != perspective:
        errors.append(f"{perspective}: report perspective does not match its destination")
    if report.get("request_id") != request.get("request_id"):
        errors.append(f"{perspective}: report is not bound to the prepared request")
    if report.get("candidate") != request.get("candidate"):
        errors.append(f"{perspective}: report candidate identity does not match the prepared request")

    availability = report.get("availability")
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
        if required:
            if reviewer.get("launch_evidence") != PLATFORM_OBSERVED:
                errors.append(
                    f"{perspective}: report lacks platform-observed launch evidence; a required review must be launched by the platform"
                )
            elif availability == "available":
                if not _nonempty_string(reviewer.get("read_only_mechanism")):
                    errors.append(f"{perspective}: platform-observed report must name its enforced read-only mechanism")
                model = reviewer.get("model")
                if not isinstance(model, dict) or not _nonempty_string(model.get("value")) or not _nonempty_string(model.get("source")):
                    errors.append(f"{perspective}: platform-observed report must record the resolved reviewer model and its provenance")
                if not _nonempty_string(report.get("output_sha256")):
                    errors.append(f"{perspective}: platform-observed report must record the digest of the raw reviewer output")

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
        errors.extend(_validate_finding(f"{perspective}: finding {index + 1}", finding, legacy_dispositions=not required))
    return errors


def read_dispositions(change: Path) -> list[dict[str, Any]]:
    path = dispositions_path(change)
    if not path.is_file():
        return []
    payload = _read_json(path, "independent review dispositions")
    items = payload.get("dispositions")
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(items, list):
        raise IndependentReviewError(f"independent review dispositions are malformed: {path}")
    return [item for item in items if isinstance(item, dict)]


def _accepted_rejection(dispositions: list[dict[str, Any]], perspective: str, finding_id: str, digest: str) -> bool:
    for item in dispositions:
        if (
            item.get("perspective") == perspective
            and item.get("finding") == finding_id
            and item.get("report_sha256") == digest
        ):
            return item.get("status") == "rejected" and _nonempty_string(item.get("rationale"))
    return False


def evaluate(root: Path, change: Path, *, required: bool) -> dict[str, Any]:
    """Derive the review state from the files in the change directory.

    ``missing`` and ``stale`` evidence is rerunnable; ``blocked`` evidence is
    current but has an unavailable perspective or an undisposed material
    finding; ``ready`` evidence satisfies the gate.
    """
    name = canonical_change_name(change)
    result: dict[str, Any] = {
        "state": STATE_READY, "errors": [], "unavailable": [], "blockers": [], "request_id": None, "candidate": None,
    }

    def finish(state: str) -> dict[str, Any]:
        result["state"] = state
        return result

    if not request_path(change).is_file():
        result["errors"].append(f"missing independent review request: {request_path(change)}")
        return finish(STATE_MISSING)
    try:
        request = _read_json(request_path(change), "independent review request")
    except IndependentReviewError as exc:
        result["errors"].append(str(exc))
        return finish(STATE_STALE)
    request_errors = _validate_request(request)
    if required and not isinstance(request.get("task_content"), dict):
        request_errors.append("request is not bound to task-content identity")
    if request_errors:
        result["errors"].extend(request_errors)
        return finish(STATE_STALE)
    stale = request_staleness(root, change, request)
    if stale:
        result["errors"].append(stale)
        return finish(STATE_STALE)
    result["request_id"] = request["request_id"]
    result["candidate"] = request["candidate"]

    try:
        dispositions = read_dispositions(change)
    except IndependentReviewError as exc:
        result["errors"].append(str(exc))
        return finish(STATE_BLOCKED)
    missing = False
    invalid = False
    for perspective in PERSPECTIVES:
        path = report_path(change, perspective)
        if not path.is_file():
            result["errors"].append(f"missing {perspective} review report: {path}")
            missing = True
            continue
        try:
            report = _read_json(path, f"{perspective} review report")
        except IndependentReviewError as exc:
            result["errors"].append(str(exc))
            invalid = True
            continue
        errors = _validate_report(report, request, perspective, required=required)
        if errors:
            result["errors"].extend(errors)
            invalid = True
            continue
        if report.get("availability") == "unavailable":
            result["unavailable"].append(f"{perspective}: {report.get('limitation')}")
            continue
        digest = report_digest(report)
        for finding in report.get("findings", []):
            if finding.get("severity") != "material":
                continue
            finding_id = finding.get("id")
            if required:
                resolved = _accepted_rejection(dispositions, perspective, finding_id, digest)
            else:
                disposition = finding.get("disposition")
                resolved = (
                    isinstance(disposition, dict) and disposition.get("status") in {"fixed", "rejected"}
                ) or _accepted_rejection(dispositions, perspective, finding_id, digest)
            if not resolved:
                result["blockers"].append({
                    "perspective": perspective, "id": finding_id, "summary": finding.get("summary"),
                    "next": dispose_command(name, perspective, str(finding_id)),
                })
    if invalid:
        return finish(STATE_STALE)
    if missing:
        return finish(STATE_MISSING)
    if result["unavailable"]:
        result["errors"].append("independent review unavailable: " + "; ".join(result["unavailable"]))
    if result["blockers"]:
        result["errors"].append(
            "unresolved material independent-review findings: "
            + ", ".join(f"{item['perspective']}:{item['id']}" for item in result["blockers"])
        )
    if result["unavailable"] or result["blockers"]:
        return finish(STATE_BLOCKED)
    return finish(STATE_READY)


def validate_evidence(root: Path, change: Path, *, required: bool | None = None) -> dict[str, Any]:
    if required is None:
        required = review_is_required(root, change)
    result = evaluate(root, change, required=required)
    if result["state"] != STATE_READY:
        raise IndependentReviewError("; ".join(result["errors"]) or f"independent review is {result['state']}")
    return {"request_id": result["request_id"], "candidate": result["candidate"], "perspectives": list(PERSPECTIVES)}


def review_is_required(root: Path, change: Path) -> bool:
    settings = read_platform_config(root).get("independent_review", {})
    return isinstance(settings, dict) and settings.get("enabled") is True and (change / ".managed-task.json").is_file()


def _next_command(change: Path, result: dict[str, Any]) -> str | None:
    name = canonical_change_name(change)
    state = result["state"]
    if state in {STATE_MISSING, STATE_STALE}:
        return run_command(name)
    if state == STATE_BLOCKED:
        if result["blockers"]:
            return result["blockers"][0]["next"]
        return run_command(name)
    return None


def review_state(root: Path, change: Path | None) -> dict[str, Any]:
    """Derived, file-backed review state and next command for status surfaces."""
    if change is None or not change.is_dir() or not review_is_required(root, change):
        return {"state": STATE_NOT_REQUIRED, "next": None, "detail": None}
    try:
        result = evaluate(root, change, required=True)
    except Exception as exc:  # A status view must never fail on unreadable evidence.
        return {"state": STATE_STALE, "next": run_command(canonical_change_name(change)), "detail": str(exc)}
    payload: dict[str, Any] = {
        "state": result["state"],
        "next": _next_command(change, result),
        "detail": "; ".join(result["errors"]) or None,
    }
    if result["state"] in {STATE_MISSING, STATE_STALE} and change.parent.name != "archive":
        payload["note"] = (
            "the archive helper runs a missing or stale review automatically before expensive validation; "
            f"check reviewer runtime readiness first with {preflight_command(canonical_change_name(change))}"
        )
    if result["blockers"]:
        payload["blockers"] = [{key: item[key] for key in ("perspective", "id", "summary", "next")} for item in result["blockers"]]
    if result["unavailable"]:
        payload["unavailable"] = list(result["unavailable"])
    return payload


def _blocking_message(change: Path, result: dict[str, Any]) -> str:
    name = canonical_change_name(change)
    lines = [f"{name}: independent review is required but {result['state']}: " + ("; ".join(result["errors"]) or result["state"])]
    for item in result["blockers"]:
        lines.append(f"- material finding {item['perspective']}:{item['id']}: {item.get('summary')}")
    for limitation in result["unavailable"]:
        lines.append(f"- unavailable {limitation}")
    lines.append("Next commands:")
    for item in result["blockers"]:
        lines.append(f"  reject with rationale: {item['next']}")
    if result["blockers"]:
        lines.append(f"  or fix the candidate, commit, and rerun: {run_command(name)}")
    else:
        if result["unavailable"]:
            lines.append(f"  check reviewer runtime readiness: {preflight_command(name)}")
        lines.append(f"  rerun the platform-launched review: {run_command(name)}")
    return "\n".join(lines)


def require_review_evidence(root: Path, change: Path) -> None:
    """Enforce required, current, platform-observed review evidence."""
    if not review_is_required(root, change):
        return
    result = evaluate(root, change, required=True)
    if result["state"] != STATE_READY:
        raise SystemExit(_blocking_message(change, result))


def ensure_review_evidence(root: Path, change: Path, *, launcher: Any = None) -> None:
    """Archive preflight: run a missing/stale/unavailable review, then enforce it."""
    if not review_is_required(root, change):
        return
    result = evaluate(root, change, required=True)
    if result["state"] in {STATE_MISSING, STATE_STALE} or (result["state"] == STATE_BLOCKED and result["unavailable"] and not result["blockers"]):
        import independent_review_runner

        print(f"Running platform-launched independent review for {canonical_change_name(change)} ({result['state']} evidence).", flush=True)
        try:
            independent_review_runner.run_review(root, change, launcher=launcher)
        except IndependentReviewError as exc:
            raise SystemExit(
                f"{canonical_change_name(change)}: independent review could not run: {exc}\n"
                f"Next command after resolving it: {run_command(canonical_change_name(change))}"
            ) from exc
    require_review_evidence(root, change)


def dispose(root: Path, change: Path, *, perspective: str, finding: str, status: str, rationale: str) -> Path:
    """Record a disposition bound to the immutable report's digest."""
    if perspective not in PERSPECTIVES:
        raise IndependentReviewError(f"unsupported perspective {perspective!r}")
    if status == "fixed":
        raise IndependentReviewError(
            "a fix changes the candidate: commit it and rerun the review with "
            f"{run_command(canonical_change_name(change))}; 'fixed' is not recordable against the reviewed report"
        )
    if status not in RECORDABLE_DISPOSITIONS:
        raise IndependentReviewError("disposition status must be rejected or blocker")
    if not _nonempty_string(rationale):
        raise IndependentReviewError("a disposition requires a non-empty rationale")
    report = _read_json(report_path(change, perspective), f"{perspective} review report")
    findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    if not any(isinstance(item, dict) and item.get("id") == finding for item in findings):
        raise IndependentReviewError(f"{perspective} report has no finding {finding!r}")
    digest = report_digest(report)
    items = [
        item for item in read_dispositions(change)
        if not (item.get("perspective") == perspective and item.get("finding") == finding)
    ]
    items.append({
        "perspective": perspective, "finding": finding, "status": status, "rationale": rationale.strip(),
        "report_sha256": digest, "request_id": report.get("request_id"), "recorded_at": utc_now(),
    })
    path = dispositions_path(change)
    atomic_write_text(path, json.dumps({"schema_version": SCHEMA_VERSION, "dispositions": items}, indent=2, sort_keys=True) + "\n")
    return path


def record_report(root: Path, change: Path, source: Path) -> Path:
    """Compatibility import of a runtime report; it never satisfies a required review."""
    request = _read_json(request_path(change), "independent review request")
    request_errors = _validate_request(request)
    if request_errors:
        raise IndependentReviewError("; ".join(request_errors))
    stale = request_staleness(root, change, request)
    if stale:
        raise IndependentReviewError(stale)
    report = _read_json(source, "independent review report")
    perspective = report.get("perspective")
    if perspective not in PERSPECTIVES:
        raise IndependentReviewError("independent review report must name a supported perspective")
    reviewer = report.get("reviewer")
    if isinstance(reviewer, dict) and reviewer.get("launch_evidence") == PLATFORM_OBSERVED:
        raise IndependentReviewError(
            "an imported report cannot claim platform-observed launch evidence; run the review through the platform instead"
        )
    errors = _validate_report(report, request, perspective)
    if errors:
        raise IndependentReviewError("; ".join(errors))
    destination = report_path(change, perspective)
    atomic_write_text(destination, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare, run and validate independent OpenSpec review evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    readiness = subparsers.add_parser(
        "preflight", help="prove the selected reviewer runtime and exact model are usable; writes no review evidence",
    )
    readiness.add_argument("change", nargs="?", help="OpenSpec change name (optional; active or archived)")
    for name in ("prepare", "check", "record", "run", "dispose", "status"):
        command = subparsers.add_parser(name)
        command.add_argument("change", help="OpenSpec change name (active or archived)")
        if name in {"prepare", "run"}:
            command.add_argument("--base", default=None, help="immutable base ref to review against (default: origin/<main_branch>)")
        if name == "record":
            command.add_argument("--report", required=True, type=Path, help="runtime-produced report JSON (compatibility; not accepted for required review)")
        if name == "dispose":
            command.add_argument("--perspective", required=True, choices=PERSPECTIVES)
            command.add_argument("--finding", required=True)
            command.add_argument("--status", required=True, choices=RECORDABLE_DISPOSITIONS)
            command.add_argument("--rationale", required=True)
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "preflight":
            import independent_review_runner

            if args.change and not resolve_change(root, args.change).is_dir():
                raise IndependentReviewError(f"OpenSpec change not found: {args.change}")
            readiness = independent_review_runner.preflight(root)
            if args.change:
                readiness = {"change": args.change, **readiness}
            print(json.dumps(readiness, indent=2, sort_keys=True))
            return 0 if readiness["ready"] else 2
        change = resolve_change(root, args.change)
        base = getattr(args, "base", None) or f"origin/{read_platform_config(root).get('main_branch', 'main')}"
        if args.command == "prepare":
            request = prepare_request(root, change, base)
            print(f"Prepared independent review request {request['request_id']} for {args.change}.")
        elif args.command == "run":
            import independent_review_runner

            reports = independent_review_runner.run_review(root, change, base_ref=base)
            for perspective, report in reports.items():
                detail = report.get("limitation") if report.get("availability") == "unavailable" else f"{len(report.get('findings', []))} finding(s)"
                print(f"{perspective}: {report.get('availability')} ({detail})")
            state = review_state(root, change)
            print(f"independent review: {state['state']}" + (f"; next: {state['next']}" if state.get("next") else ""))
            return 0 if state["state"] in {STATE_READY, STATE_NOT_REQUIRED} else 2
        elif args.command == "dispose":
            path = dispose(root, change, perspective=args.perspective, finding=args.finding, status=args.status, rationale=args.rationale)
            print(f"Recorded {args.status} disposition for {args.perspective}:{args.finding} in {path.relative_to(root)}")
        elif args.command == "record":
            destination = record_report(root, change, args.report)
            print(f"Recorded independent review report: {destination.relative_to(root)}")
        elif args.command == "status":
            print(json.dumps(review_state(root, change), indent=2, sort_keys=True))
        else:
            result = validate_evidence(root, change)
            print(f"Independent review evidence is ready for {args.change}: {result['request_id']}")
    except IndependentReviewError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
