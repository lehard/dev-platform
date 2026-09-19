#!/usr/bin/env python3
"""Build and validate bounded, derived Project Evidence Snapshots.

Snapshots are an intentionally small cache of source identities and semantic
projections.  They are not a project registry: OpenSpec, ``docs/context``,
AGENTS files, code, and tests remain the sources of truth.  This module owns
only deterministic inventory/freshness/digest checks and a neutral exchange
format for an existing read-only context worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

from _platform_common import atomic_write_text


SNAPSHOT_VERSION = 1
WORKER_RESULT_VERSION = 1
MAX_SOURCES = 300
SHA256_LENGTH = 64
GIT_BLOB_LENGTH = 40
CONCERNS = (
    "accepted-system",
    "topology",
    "integrations",
    "rules",
    "project-context",
    "conflicts-unknowns",
)


class ProjectEvidenceError(RuntimeError):
    """A snapshot is malformed, unsafe, or cannot prove its evidence."""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProjectEvidenceError(f"{label} is not readable: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectEvidenceError(f"{label} is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ProjectEvidenceError(f"{label} must be a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def current_revision(root: Path) -> str | None:
    result = _git(root, "rev-parse", "HEAD")
    revision = result.stdout.strip().lower()
    return revision if result.returncode == 0 and len(revision) == GIT_BLOB_LENGTH else None


def _safe_relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ProjectEvidenceError(f"source escapes repository root: {path}") from exc


def _files_under(root: Path, relative: str, *, suffixes: tuple[str, ...] = ()) -> list[Path]:
    path = root / relative
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return [candidate for candidate in path.rglob("*") if candidate.is_file() and (not suffixes or candidate.suffix in suffixes)]


def _active_change_files(root: Path) -> list[Path]:
    changes = root / "openspec" / "changes"
    if not changes.is_dir():
        return []
    return [
        path for path in changes.rglob("*")
        if path.is_file() and "archive" not in path.relative_to(changes).parts
    ]


def _module_agents(root: Path) -> list[Path]:
    # Ask Git for the bounded set of visible instruction files instead of
    # recursively walking every directory in the repository.  Include
    # untracked, non-ignored files because an in-progress instruction change
    # is still current evidence for this working tree.
    result = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--", ":(glob)**/AGENTS.md")
    if result.returncode != 0:
        raise ProjectEvidenceError("cannot inventory instruction files through Git")
    paths: list[Path] = []
    for relative in result.stdout.splitlines():
        candidate = root / relative
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _candidate_paths(root: Path, concern: str) -> list[Path]:
    """Return bounded, concern-specific source candidates, never a whole-tree scan."""
    if concern == "accepted-system":
        return _files_under(root, "openspec/specs") + _active_change_files(root)
    if concern == "topology":
        paths = [root / "README.md", root / "pyproject.toml", root / "package.json"]
        for relative in ("src", "app", "lib"):
            paths.extend(_files_under(root, relative))
        return paths
    if concern == "integrations":
        paths = _files_under(root, "openspec/specs") + _active_change_files(root)
        paths.extend(_files_under(root, "docs/engineering", suffixes=(".md",)))
        for relative in ("openapi", "schemas", "contracts"):
            paths.extend(_files_under(root, relative))
        return paths
    if concern == "rules":
        paths = _module_agents(root)
        paths.extend(_files_under(root, "docs/engineering", suffixes=(".md",)))
        for relative in ("dev-platform/checks.toml", ".dev-platform.toml"):
            paths.append(root / relative)
        return paths
    if concern == "project-context":
        return [root / "README.md"] + _files_under(root, "docs/context", suffixes=(".md",))
    if concern == "conflicts-unknowns":
        return _candidate_paths(root, "accepted-system") + _candidate_paths(root, "rules") + _candidate_paths(root, "project-context")
    raise ProjectEvidenceError(f"unknown projection concern: {concern}")


def _identity(root: Path, path: Path) -> dict[str, str]:
    relative = _safe_relative(root, path)
    # `hash-object` gives a Git blob identity for the actual current content,
    # including a dirty tracked file, rather than trusting mtime or HEAD alone.
    result = _git(root, "hash-object", "--", relative)
    blob = result.stdout.strip().lower()
    if result.returncode == 0 and len(blob) == GIT_BLOB_LENGTH and all(char in "0123456789abcdef" for char in blob):
        return {"algorithm": "git-blob", "digest": blob}
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ProjectEvidenceError(f"cannot hash source {relative}: {exc}") from exc
    return {"algorithm": "sha256", "digest": digest}


def inventory(root: Path) -> dict[str, Any]:
    """Inventory only the initial bounded concern roots with stable identities."""
    source_concerns: dict[str, set[str]] = {}
    all_paths: dict[str, Path] = {}
    for concern in CONCERNS:
        for path in _candidate_paths(root, concern):
            if path.is_file():
                relative = _safe_relative(root, path)
                source_concerns.setdefault(relative, set()).add(concern)
                all_paths[relative] = path
    if len(all_paths) > MAX_SOURCES:
        raise ProjectEvidenceError(
            f"bounded evidence inventory found {len(all_paths)} sources (limit {MAX_SOURCES}); narrow the projection roots before snapshotting"
        )
    sources = [
        {
            "path": relative,
            "identity": _identity(root, all_paths[relative]),
            "concerns": sorted(source_concerns[relative]),
        }
        for relative in sorted(all_paths)
    ]
    dependencies = {
        concern: [source["path"] for source in sources if concern in source["concerns"]]
        for concern in CONCERNS
    }
    return {"sources": sources, "dependencies": dependencies}


def _source_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = snapshot.get("sources")
    if not isinstance(raw, list):
        raise ProjectEvidenceError("snapshot.sources must be a list")
    result: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(raw):
        if not isinstance(source, dict):
            raise ProjectEvidenceError(f"snapshot.sources[{index}] must be an object")
        path = source.get("path")
        identity = source.get("identity")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
            raise ProjectEvidenceError(f"snapshot.sources[{index}].path is unsafe")
        if path in result:
            raise ProjectEvidenceError(f"snapshot.sources contains duplicate path {path!r}")
        if not isinstance(identity, dict) or identity.get("algorithm") not in ("git-blob", "sha256"):
            raise ProjectEvidenceError(f"snapshot.sources[{index}].identity is invalid")
        digest = identity.get("digest")
        expected = GIT_BLOB_LENGTH if identity["algorithm"] == "git-blob" else SHA256_LENGTH
        if not isinstance(digest, str) or len(digest) != expected or any(char not in "0123456789abcdef" for char in digest):
            raise ProjectEvidenceError(f"snapshot.sources[{index}].identity.digest is invalid")
        result[path] = source
    return result


def _input_digest(source_map: dict[str, dict[str, Any]], dependencies: list[str]) -> str:
    return _digest([{"path": path, "identity": source_map[path]["identity"]} for path in sorted(dependencies)])


def _projection_digest(projection: dict[str, Any]) -> str:
    stable = {key: value for key, value in projection.items() if key != "digest"}
    return _digest(stable)


def _snapshot_digest(snapshot: dict[str, Any]) -> str:
    # Efficiency is an observation about this build attempt, not snapshot
    # content.  Keeping it out preserves a stable consumer reference across
    # an unchanged cache hit and a prior full build.
    stable = {key: snapshot[key] for key in ("version", "revision", "sources", "projections")}
    return _digest(stable)


def _validate_result(result: dict[str, Any], dependencies: set[str], concern: str) -> dict[str, Any]:
    if result.get("version", WORKER_RESULT_VERSION) != WORKER_RESULT_VERSION:
        raise ProjectEvidenceError(f"worker result for {concern} has unsupported version")
    confidence = result.get("confidence")
    if confidence not in ("high", "medium", "low"):
        raise ProjectEvidenceError(f"worker result for {concern} must set confidence to high, medium, or low")
    normalized: dict[str, Any] = {"version": WORKER_RESULT_VERSION, "confidence": confidence}
    for key in ("facts", "conflicts", "unknowns"):
        value = result.get(key, [])
        if not isinstance(value, list):
            raise ProjectEvidenceError(f"worker result for {concern}.{key} must be a list")
        normalized[key] = value
    facts: list[dict[str, Any]] = []
    for index, fact in enumerate(normalized["facts"]):
        if not isinstance(fact, dict) or not isinstance(fact.get("statement"), str) or not fact["statement"].strip():
            raise ProjectEvidenceError(f"worker result for {concern}.facts[{index}] needs a non-empty statement")
        refs = fact.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref in dependencies for ref in refs):
            raise ProjectEvidenceError(f"worker result for {concern}.facts[{index}] has an unlinked evidence_refs entry")
        facts.append({"statement": fact["statement"].strip(), "evidence_refs": sorted(set(refs))})
    normalized["facts"] = facts
    for key in ("conflicts", "unknowns"):
        normalized[key] = [value.strip() for value in normalized[key] if isinstance(value, str) and value.strip()]
        if len(normalized[key]) != len(result.get(key, [])):
            raise ProjectEvidenceError(f"worker result for {concern}.{key} must contain non-empty strings")
    provenance = result.get("provenance_ref")
    if provenance is not None:
        if not isinstance(provenance, str) or not provenance.strip() or len(provenance) > 240:
            raise ProjectEvidenceError(f"worker result for {concern}.provenance_ref must be a bounded string when present")
        normalized["provenance_ref"] = provenance.strip()
    # Supported usage is optional.  Unknown remains absent; token estimates are
    # deliberately rejected so this substrate cannot fabricate efficiency data.
    if "usage" in result:
        usage = result["usage"]
        if not isinstance(usage, dict) or set(usage) - {"model_calls"} or not isinstance(usage.get("model_calls"), int) or usage["model_calls"] < 0:
            raise ProjectEvidenceError(f"worker result for {concern}.usage may contain only non-negative model_calls")
        normalized["usage"] = {"model_calls": usage["model_calls"]}
    return normalized


def _worker_request(concern: str, sources: dict[str, dict[str, Any]], dependencies: list[str]) -> dict[str, Any]:
    return {
        "version": WORKER_RESULT_VERSION,
        "concern": concern,
        "source_refs": [{"path": path, "identity": sources[path]["identity"]} for path in sorted(dependencies)],
        "result_contract": {
            "required": ["confidence", "facts", "conflicts", "unknowns"],
            "fact_contract": "Each fact has a statement and evidence_refs limited to source_refs.",
            "write_authority": "none",
            "non_authoritative": True,
            "forbidden": ["raw transcripts", "chain-of-thought", "bulk source copies", "architecture decisions"],
        },
    }


def _fresh_prior_projection(prior: dict[str, Any], concern: str, sources: dict[str, dict[str, Any]], dependencies: list[str]) -> dict[str, Any] | None:
    projections = prior.get("projections")
    if not isinstance(projections, dict):
        return None
    candidate = projections.get(concern)
    if not isinstance(candidate, dict):
        return None
    try:
        _validate_projection(candidate, sources)
    except ProjectEvidenceError:
        return None
    if candidate.get("dependencies") != sorted(dependencies):
        return None
    if candidate.get("input_digest") != _input_digest(sources, dependencies):
        return None
    return candidate


def _validate_projection(projection: dict[str, Any], sources: dict[str, dict[str, Any]]) -> None:
    concern = projection.get("concern")
    if concern not in CONCERNS:
        raise ProjectEvidenceError("projection concern is invalid")
    dependencies = projection.get("dependencies")
    if not isinstance(dependencies, list) or dependencies != sorted(dependencies) or not all(isinstance(path, str) and path in sources for path in dependencies):
        raise ProjectEvidenceError(f"projection {concern} dependencies are invalid")
    if projection.get("input_digest") != _input_digest(sources, dependencies):
        raise ProjectEvidenceError(f"projection {concern} input digest does not link to source identities")
    status = projection.get("status")
    if status not in ("fresh", "escalation-required", "requires-extraction"):
        raise ProjectEvidenceError(f"projection {concern} status is invalid")
    if status == "requires-extraction":
        if not isinstance(projection.get("worker_request"), dict):
            raise ProjectEvidenceError(f"projection {concern} lacks a worker request")
    else:
        result = projection.get("result")
        if not isinstance(result, dict):
            raise ProjectEvidenceError(f"projection {concern} lacks a worker result")
        _validate_result(result, set(dependencies), concern)
        if status == "fresh" and (result["confidence"] == "low" or result["conflicts"]):
            raise ProjectEvidenceError(f"projection {concern} suppresses a conflict or low-confidence escalation")
    if projection.get("digest") != _projection_digest(projection):
        raise ProjectEvidenceError(f"projection {concern} digest is invalid")


def validate_snapshot(root: Path, snapshot: dict[str, Any], *, check_freshness: bool = True) -> dict[str, Any]:
    if snapshot.get("version") != SNAPSHOT_VERSION:
        raise ProjectEvidenceError(f"unsupported snapshot schema version: {snapshot.get('version')!r}")
    revision = snapshot.get("revision")
    if revision is not None and (not isinstance(revision, str) or len(revision) != GIT_BLOB_LENGTH):
        raise ProjectEvidenceError("snapshot revision must be a Git SHA or null")
    sources = _source_map(snapshot)
    projections = snapshot.get("projections")
    if not isinstance(projections, dict) or set(projections) != set(CONCERNS):
        raise ProjectEvidenceError("snapshot must contain exactly the supported projections")
    for projection in projections.values():
        if not isinstance(projection, dict):
            raise ProjectEvidenceError("snapshot projection must be an object")
        _validate_projection(projection, sources)
    if snapshot.get("digest") != _snapshot_digest(snapshot):
        raise ProjectEvidenceError("snapshot digest is invalid")

    freshness = "not-checked"
    changed: list[str] = []
    if check_freshness:
        current = inventory(root)
        current_sources = {source["path"]: source for source in current["sources"]}
        for path in sorted(set(sources) | set(current_sources)):
            if path not in sources or path not in current_sources or sources[path]["identity"] != current_sources[path]["identity"]:
                changed.append(path)
        current_head = current_revision(root)
        if changed:
            freshness = "stale-sources"
        elif revision != current_head:
            freshness = "stale-revision"
        else:
            freshness = "fresh"
    return {"ok": True, "freshness": freshness, "changed_sources": changed, "digest": snapshot["digest"]}


def build_snapshot(root: Path, *, prior: dict[str, Any] | None, results: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    current = inventory(root)
    sources = {source["path"]: source for source in current["sources"]}
    projections: dict[str, dict[str, Any]] = {}
    counts: dict[str, Any] = {
        "hit": 0,
        "rebuild": 0,
        "routine_worker_count": 0,
        "model_calls": 0,
        "escalation_count": 0,
    }
    unknown_model_calls = False
    for concern in CONCERNS:
        dependencies = current["dependencies"][concern]
        reused = _fresh_prior_projection(prior, concern, sources, dependencies) if prior else None
        if reused is not None and concern not in results:
            projections[concern] = reused
            counts["hit"] += 1
            continue
        counts["rebuild"] += 1
        projection: dict[str, Any] = {
            "concern": concern,
            "dependencies": dependencies,
            "input_digest": _input_digest(sources, dependencies),
        }
        supplied = results.get(concern)
        if supplied is None:
            projection["status"] = "requires-extraction"
            projection["worker_request"] = _worker_request(concern, sources, dependencies)
        else:
            result = _validate_result(supplied, set(dependencies), concern)
            counts["routine_worker_count"] += 1
            if "usage" in result:
                counts["model_calls"] += result["usage"]["model_calls"]
            else:
                unknown_model_calls = True
            escalation_reason: str | None = None
            if result["conflicts"]:
                escalation_reason = "conflicting evidence"
            elif result["confidence"] == "low":
                escalation_reason = "low confidence"
            if escalation_reason:
                projection["status"] = "escalation-required"
                projection["escalation_reason"] = escalation_reason
                counts["escalation_count"] += 1
            else:
                projection["status"] = "fresh"
            projection["result"] = result
        projection["digest"] = _projection_digest(projection)
        projections[concern] = projection
    if unknown_model_calls:
        counts["model_calls"] = None
    snapshot: dict[str, Any] = {
        "version": SNAPSHOT_VERSION,
        "revision": current_revision(root),
        "sources": current["sources"],
        "projections": projections,
        "efficiency": {
            **counts,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "usage": "only worker-supplied model_calls; token usage unknown unless a caller records it elsewhere",
        },
    }
    snapshot["digest"] = _snapshot_digest(snapshot)
    return snapshot, snapshot["efficiency"]


def _result_arguments(values: Iterable[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for value in values:
        concern, separator, raw_path = value.partition("=")
        if not separator or concern not in CONCERNS or not raw_path:
            raise ProjectEvidenceError("--worker-result must be CONCERN=PATH using a supported concern")
        if concern in results:
            raise ProjectEvidenceError(f"duplicate worker result for {concern}")
        results[concern] = _load_json(Path(raw_path), f"worker result for {concern}")
    return results


def _command_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    prior = _load_json(Path(args.prior), "prior snapshot") if args.prior else None
    if prior is not None:
        # Prior content is structural cache input; freshness is deliberately not
        # required because unchanged projections can survive a new revision.
        validate_snapshot(root, prior, check_freshness=False)
    snapshot, evidence = build_snapshot(root, prior=prior, results=_result_arguments(args.worker_result))
    _write_json(Path(args.out), snapshot)
    print(json.dumps({"snapshot": str(Path(args.out)), "digest": snapshot["digest"], "efficiency": evidence}, ensure_ascii=False, sort_keys=True))
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    report = validate_snapshot(Path(args.root).resolve(), _load_json(Path(args.snapshot), "snapshot"), check_freshness=not args.no_freshness)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not args.require_fresh or report["freshness"] == "fresh" else 2


def _command_reference(args: argparse.Namespace) -> int:
    snapshot = _load_json(Path(args.snapshot), "snapshot")
    report = validate_snapshot(Path(args.root).resolve(), snapshot, check_freshness=True)
    concern = args.concern
    projection = snapshot["projections"][concern]
    payload = {
        "snapshot_digest": snapshot["digest"],
        "snapshot_revision": snapshot["revision"],
        "snapshot_freshness": report["freshness"],
        "projection": concern,
        "projection_digest": projection["digest"],
        "projection_status": projection["status"],
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not args.require_fresh or (report["freshness"] == "fresh" and projection["status"] == "fresh") else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded, derived Project Evidence Snapshots.")
    parser.add_argument("--root", default=".", help="repository root to inventory (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="inventory sources and reuse or request bounded projections")
    build.add_argument("--out", required=True, help="machine-local snapshot JSON path")
    build.add_argument("--prior", help="prior snapshot eligible for source-identity reuse")
    build.add_argument("--worker-result", action="append", default=[], metavar="CONCERN=PATH", help="read-only worker result; repeat per rebuilt concern")
    build.set_defaults(handler=_command_build)
    validate = commands.add_parser("validate", help="validate schema, provenance, digests, and optional current freshness")
    validate.add_argument("snapshot")
    validate.add_argument("--no-freshness", action="store_true")
    validate.add_argument("--require-fresh", action="store_true")
    validate.set_defaults(handler=_command_validate)
    reference = commands.add_parser("reference", help="emit a stable consumer reference for one projection")
    reference.add_argument("snapshot")
    reference.add_argument("--concern", required=True, choices=CONCERNS)
    reference.add_argument("--require-fresh", action="store_true")
    reference.set_defaults(handler=_command_reference)
    args = parser.parse_args()
    try:
        return args.handler(args)
    except ProjectEvidenceError as exc:
        parser.error(str(exc))
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
