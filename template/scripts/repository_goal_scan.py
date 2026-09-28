#!/usr/bin/env python3
"""Deterministically select and account for a revision-bound goal scan.

This is deliberately bookkeeping, not an agent runner.  It reads only the
committed Git tree selected by a profile and writes a caller-named local run
directory.  Map workers (native delegates or the current executor) supply
structured verdicts through ``record``.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

VERSION = 1


class ScanError(RuntimeError):
    pass


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScanError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ScanError(f"{label} must be a JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _local_run(root: Path, path: Path) -> Path:
    location = path.resolve()
    allowed = (root.resolve() / ".dev-platform" / "repository-goal-scan").resolve()
    if not location.is_relative_to(allowed) or location == allowed:
        raise ScanError(f"scan run must be under {allowed}")
    return location


def _git(root: Path, *args: str, binary: bool = False) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode:
        raise ScanError(result.stderr.decode("utf-8", "replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


def resolve_revision(root: Path, revision: str | None) -> str:
    value = _git(root, "rev-parse", "--verify", f"{revision or 'HEAD'}^{{commit}}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ScanError("Git did not resolve an immutable commit SHA")
    return value


def _paths(root: Path, revision: str) -> list[str]:
    raw = _git(root, "ls-tree", "-r", "-z", "--name-only", revision)
    return sorted(item.decode("utf-8", "surrogateescape") for item in raw.split(b"\0") if item)


def _matches(path: str, patterns: list[str]) -> bool:
    return any(
        fnmatch.fnmatchcase(path, pattern)
        or (pattern.startswith("**/") and fnmatch.fnmatchcase(path, pattern[3:]))
        for pattern in patterns
    )


def _scope(paths: list[str], selector: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    include = selector.get("include", profile.get("include", ["**"]))
    exclude = selector.get("exclude", profile.get("exclude", []))
    if not isinstance(include, list) or not isinstance(exclude, list) or not all(isinstance(p, str) for p in include + exclude):
        raise ScanError("selector include/exclude must be string lists")
    return [path for path in paths if _matches(path, include) and not _matches(path, exclude)]


def _candidate_id(revision: str, selector_id: str, path: str, line: int, evidence: str) -> str:
    material = "\0".join((revision, selector_id, path, str(line), evidence)).encode("utf-8", "surrogateescape")
    return "signal-" + hashlib.sha256(material).hexdigest()[:24]


def _selectors(profile: dict[str, Any]) -> list[dict[str, Any]]:
    values = profile.get("selectors")
    if not isinstance(values, list) or not values:
        raise ScanError("profile.selectors must be a non-empty list")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for selector in values:
        if not isinstance(selector, dict):
            raise ScanError("every selector must be an object")
        if set(selector) - {"id", "type", "pattern", "include", "exclude"}:
            raise ScanError("selector has unsupported fields")
        identifier, kind = selector.get("id"), selector.get("type")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identifier) or identifier in seen:
            raise ScanError("selectors require unique safe ids")
        if kind not in {"inventory", "fixed", "regex"}:
            raise ScanError(f"selector {identifier!r} has unsupported type")
        if kind != "inventory" and (not isinstance(selector.get("pattern"), str) or not selector["pattern"]):
            raise ScanError(f"selector {identifier!r} requires a non-empty pattern")
        if kind != "inventory" and len(selector["pattern"]) > 500:
            raise ScanError("selector pattern is too long")
        if kind == "regex":
            try:
                re.compile(selector["pattern"])
            except re.error as exc:
                raise ScanError(f"selector {identifier!r} has invalid regex: {exc}") from exc
        seen.add(identifier)
        result.append(selector)
    return result


def plan(root: Path, profile: dict[str, Any], revision: str | None, out: Path) -> dict[str, Any]:
    out = _local_run(root, out)
    if set(profile) - {"goal", "question", "selection_confidence", "limitations", "include", "exclude", "selectors", "shard"}:
        raise ScanError("profile has unsupported fields")
    goal = profile.get("goal")
    limitations = profile.get("limitations", [])
    question = profile.get("question")
    confidence = profile.get("selection_confidence")
    if (not isinstance(goal, str) or not goal.strip() or not isinstance(question, str) or not question.strip()
            or confidence not in {"low", "medium", "high"}
            or not isinstance(limitations, list) or not all(isinstance(x, str) for x in limitations)):
        raise ScanError("profile requires goal, question, selection_confidence and a limitations list")
    if len(goal) > 500 or len(question) > 500 or len(limitations) > 30 or any(len(item) > 500 for item in limitations):
        raise ScanError("profile prose exceeds bounded evidence limits")
    if (out / "manifest.json").exists():
        raise ScanError("run directory already contains a manifest")
    commit = resolve_revision(root, revision)
    selectors = _selectors(profile)
    all_paths = _paths(root, commit)
    candidates: list[dict[str, Any]] = []
    selected_paths: set[str] = set()
    for selector in selectors:
        for path in _scope(all_paths, selector, profile):
            selected_paths.add(path)
            if selector["type"] == "inventory":
                candidates.append({"id": _candidate_id(commit, selector["id"], path, 1, path), "selector_id": selector["id"], "path": path, "line": 1, "provenance": "inventory"})
                continue
            content = _git(root, "show", f"{commit}:{path}")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                candidates.append({"id": _candidate_id(commit, selector["id"], path, 0, "non-utf8"), "selector_id": selector["id"], "path": path, "line": 0, "provenance": "non-utf8"})
                continue
            matcher = (lambda line: selector["pattern"] in line) if selector["type"] == "fixed" else re.compile(selector["pattern"]).search
            matched = False
            for number, line in enumerate(text.splitlines(), 1):
                if matcher(line):
                    matched = True
                    evidence = hashlib.sha256(line.encode()).hexdigest()[:16]
                    candidates.append({"id": _candidate_id(commit, selector["id"], path, number, evidence), "selector_id": selector["id"], "path": path, "line": number, "provenance": "text-match", "evidence_sha256": evidence})
            if not matched:
                candidates.append({"id": _candidate_id(commit, selector["id"], path, 0, "no-text-match"), "selector_id": selector["id"], "path": path, "line": 0, "provenance": "no-text-match"})
    candidates.sort(key=lambda item: (item["selector_id"], item["path"], item["line"], item["id"]))
    ids = [item["id"] for item in candidates]
    if len(ids) != len(set(ids)):
        raise ScanError("selection emitted duplicate candidate ids")
    if {item["path"] for item in candidates} != selected_paths:
        raise ScanError("selection omitted one or more selected tracked paths")
    shard = profile.get("shard", {})
    if not isinstance(shard, dict) or not isinstance(shard.get("max_candidates", 50), int) or shard.get("max_candidates", 50) < 1:
        raise ScanError("profile.shard.max_candidates must be a positive integer")
    bound = shard.get("max_candidates", 50)
    batches = [{"id": f"batch-{index // bound + 1:04d}", "candidate_ids": ids[index:index + bound]} for index in range(0, len(ids), bound)]
    assigned = [item for batch in batches for item in batch["candidate_ids"]]
    if assigned != ids or len(assigned) != len(set(assigned)):
        raise ScanError("sharding omitted or overlapped candidates")
    manifest = {"version": VERSION, "goal": goal, "question": question, "revision": commit, "profile": profile, "limitations": limitations, "selection_confidence": confidence, "selected_tracked_paths": sorted(selected_paths), "candidates": candidates, "batches": batches, "result_directory": "results"}
    _write(out / "manifest.json", manifest)
    return manifest


def _manifest(path: Path) -> dict[str, Any]:
    manifest = _json(path, "manifest")
    candidates, batches = manifest.get("candidates"), manifest.get("batches")
    if manifest.get("version") != VERSION or not isinstance(candidates, list) or not isinstance(batches, list):
        raise ScanError("invalid manifest version or inventory")
    ids = [item.get("id") for item in candidates if isinstance(item, dict)]
    batch_ids = [item.get("id") for item in batches if isinstance(item, dict)]
    if (len(ids) != len(candidates) or any(not isinstance(x, str) for x in ids)
            or len(ids) != len(set(ids)) or len(batch_ids) != len(batches)
            or any(not isinstance(x, str) for x in batch_ids) or len(batch_ids) != len(set(batch_ids))):
        raise ScanError("manifest has duplicate or malformed candidate/batch ids")
    if any(not isinstance(batch.get("candidate_ids"), list) or not all(isinstance(x, str) for x in batch["candidate_ids"]) for batch in batches):
        raise ScanError("manifest has malformed batch assignment")
    assigned = [candidate for batch in batches for candidate in batch.get("candidate_ids", [])]
    if sorted(assigned) != sorted(ids) or len(assigned) != len(set(assigned)):
        raise ScanError("manifest sharding omitted, duplicated or added candidates")
    if manifest.get("result_directory") != "results":
        raise ScanError("invalid manifest result directory")
    selected = manifest.get("selected_tracked_paths")
    if (not isinstance(selected, list) or any(not isinstance(item, str) for item in selected)
            or selected != sorted(set(selected))
            or {item.get("path") for item in candidates} != set(selected)):
        raise ScanError("manifest selected tracked paths do not match candidates")
    return manifest


def _validate_result(result: dict[str, Any], batch: dict[str, Any]) -> None:
    if result.get("version") != VERSION or result.get("batch_id") != batch["id"]:
        raise ScanError("stored batch result identity is invalid")
    if result.get("status") == "failed":
        if set(result) - {"version", "batch_id", "status", "error"} or not isinstance(result.get("error"), str) or not result["error"].strip() or len(result["error"]) > 500:
            raise ScanError("failed batch requires an error")
        return
    if result.get("status") != "valid":
        raise ScanError("stored batch result has invalid status")
    if set(result) - {"version", "batch_id", "status", "candidates"}:
        raise ScanError("batch result has unsupported fields")
    accounts = result.get("candidates")
    if not isinstance(accounts, list) or not all(isinstance(item, dict) for item in accounts):
        raise ScanError("stored batch result requires candidate verdicts")
    ids = [item.get("id") for item in accounts]
    if ids != batch["candidate_ids"] or len(ids) != len(set(ids)):
        raise ScanError("batch result must account for every assigned candidate exactly once in manifest order")
    for item in accounts:
        if set(item) - {"id", "verdict", "finding"}:
            raise ScanError("candidate verdict has unsupported fields")
        if item.get("verdict") not in {"finding", "no-finding"}:
            raise ScanError("every candidate verdict must be finding or no-finding")
        if item["verdict"] == "finding":
            finding = item.get("finding")
            if not isinstance(finding, dict) or set(finding) - {"description", "evidence", "priority", "confidence", "uncertainty"} or any(not isinstance(finding.get(key), str) or not finding[key].strip() or len(finding[key]) > 1000 for key in ("description", "evidence", "priority", "confidence")):
                raise ScanError("finding requires description, evidence, priority and confidence")
            if finding["priority"] not in {"P0", "P1", "P2", "P3"} or finding["confidence"] not in {"low", "medium", "high"}:
                raise ScanError("finding priority or confidence is invalid")
            if "uncertainty" in finding and (not isinstance(finding["uncertainty"], str) or len(finding["uncertainty"]) > 1000):
                raise ScanError("finding uncertainty is invalid")
        elif "finding" in item:
            raise ScanError("no-finding verdict cannot include finding data")


def _results(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    directory = manifest_path.parent / "results"
    values: dict[str, dict[str, Any]] = {}
    if directory.is_dir():
        for path in directory.glob("*.json"):
            value = _json(path, "batch result")
            identifier = value.get("batch_id")
            batch = next((item for item in manifest["batches"] if item["id"] == identifier), None)
            if batch is None or path.name != f"{identifier}.json":
                raise ScanError("unexpected batch result file")
            _validate_result(value, batch)
            values[identifier] = value
    return values


def record(manifest_path: Path, batch_id: str, result_path: Path, failed: bool = False) -> dict[str, Any]:
    manifest = _manifest(manifest_path)
    batch = next((item for item in manifest.get("batches", []) if item.get("id") == batch_id), None)
    if not isinstance(batch, dict):
        raise ScanError(f"unknown batch: {batch_id}")
    if failed:
        result = {"version": VERSION, "batch_id": batch_id, "status": "failed", "error": _json(result_path, "failure result").get("error", "worker failed")}
    else:
        result = _json(result_path, "batch result")
        if result.get("batch_id") != batch_id:
            raise ScanError("batch result identity does not match requested batch")
        accounts = result.get("candidates")
        if not isinstance(accounts, list) or not all(isinstance(x, dict) for x in accounts):
            raise ScanError("batch result requires candidates array")
        ids = [item.get("id") for item in accounts]
        if ids != batch["candidate_ids"] or len(ids) != len(set(ids)):
            raise ScanError("batch result must account for every assigned candidate exactly once in manifest order")
        result["version"], result["status"] = VERSION, "valid"
    _validate_result(result, batch)
    _write(manifest_path.parent / "results" / f"{batch_id}.json", result)
    return result


def status(manifest_path: Path) -> dict[str, Any]:
    manifest = _manifest(manifest_path)
    results = _results(manifest_path, manifest)
    batches = manifest.get("batches", [])
    states = {"pending": 0, "valid": 0, "failed": 0}
    for batch in batches:
        state = results.get(batch["id"], {}).get("status", "pending")
        states[state if state in states else "failed"] += 1
    return {"revision": manifest.get("revision"), "batches": len(batches), "candidates": len(manifest.get("candidates", [])), **states, "complete": states["pending"] == states["failed"] == 0}


def finalize(manifest_path: Path, out: Path) -> dict[str, Any]:
    manifest = _manifest(manifest_path)
    summary = status(manifest_path)
    results = _results(manifest_path, manifest)
    processed = sum(len(batch["candidate_ids"]) for batch in manifest["batches"] if results.get(batch["id"], {}).get("status") == "valid")
    receipt = {"version": VERSION, "revision": manifest.get("revision"), "goal": manifest.get("goal"), "question": manifest.get("question"), "status": "complete" if summary["complete"] else "incomplete", "selected_scope": {"tracked_paths": manifest["selected_tracked_paths"], "candidates": summary["candidates"], "processed": processed, "coverage": "100%" if summary["complete"] else "not-complete"}, "batch_accounting": summary, "selection_confidence": manifest["selection_confidence"], "selector_limitations": manifest.get("limitations", []), "exclusions": {"profile": manifest["profile"].get("exclude", []), "selectors": {item["id"]: item.get("exclude", []) for item in manifest["profile"]["selectors"]}}}
    _write(out, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("--profile", type=Path, required=True); p.add_argument("--revision"); p.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("record"); r.add_argument("--manifest", type=Path, required=True); r.add_argument("--batch", required=True); r.add_argument("--result", type=Path, required=True); r.add_argument("--failed", action="store_true")
    s = sub.add_parser("status"); s.add_argument("--manifest", type=Path, required=True)
    f = sub.add_parser("finalize"); f.add_argument("--manifest", type=Path, required=True); f.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.repo.resolve()
        if args.command != "plan":
            _local_run(root, args.manifest.parent)
            _local_run(root, args.manifest.parent / "results")
            if args.manifest.name != "manifest.json":
                raise ScanError("scan manifest must be named manifest.json")
        if args.command == "finalize" and args.out.resolve().parent != args.manifest.resolve().parent:
            raise ScanError("coverage receipt must be written in the scan run directory")
        if args.command == "plan": value = plan(root, _json(args.profile, "profile"), args.revision, args.out)
        elif args.command == "record": value = record(args.manifest, args.batch, args.result, args.failed)
        elif args.command == "status": value = status(args.manifest)
        else: value = finalize(args.manifest, args.out)
    except ScanError as exc:
        parser.error(str(exc))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
