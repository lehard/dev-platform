#!/usr/bin/env python3
"""Evaluate frozen Dev Platform harness replay cases without changing policy.

The runner intentionally accepts candidate *evidence* instead of an arbitrary
candidate command.  A caller which runs a harness must do so in its own
disposable clone and supply bounded observed outcomes here.  This keeps the
lab from becoming another executor or a path to mutate the integration tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


VERSION = 1
SHA256 = "sha256"
METRICS = (
    "payload_bytes",
    "input_tokens",
    "cache_read_tokens",
    "fresh_input_tokens",
    "output_tokens",
    "total_tokens",
    "model_request_count",
    "wall_time_seconds",
    "cost_usd",
    "retries",
    "escalations",
    "human_interventions",
)
HARNESS_CHANGES = {"shorter-instructions", "lazy-capability-definitions", "reduced-delegation-guidance", "cache-friendly-boundaries", "native-baseline-control"}


class ReplayError(RuntimeError):
    """A replay fixture or its evidence cannot be trusted."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"cannot read {label}: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ReplayError(f"{label} must be a JSON object")
    return raw


def _string(value: dict[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ReplayError(f"{label}.{key} must be a non-empty string")
    return item.strip()


def _revision(value: str, label: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ReplayError(f"{label} must be a lowercase 40-character Git revision")
    return value


def _digest_value(value: str, label: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ReplayError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _relative(value: str, label: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ReplayError(f"{label} must be a safe repository-relative path")
    return path.as_posix()


def _reference(raw: object, label: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ReplayError(f"{label} must be an object")
    return {
        "revision": _revision(_string(raw, "revision", label), f"{label}.revision"),
        "path": _relative(_string(raw, "path", label), f"{label}.path"),
        "sha256": _digest_value(_string(raw, "sha256", label), f"{label}.sha256"),
    }


def _case(raw: object, index: int) -> dict[str, Any]:
    label = f"suite.cases[{index}]"
    if not isinstance(raw, dict):
        raise ReplayError(f"{label} must be an object")
    case_id = _string(raw, "id", label)
    source_revision = _revision(_string(raw, "source_revision", label), f"{label}.source_revision")
    contract = raw.get("contract")
    evidence = raw.get("authoritative_evidence")
    if not isinstance(contract, list) or not contract:
        raise ReplayError(f"{label}.contract must be a non-empty list")
    if not isinstance(evidence, list) or not evidence:
        raise ReplayError(f"{label}.authoritative_evidence must be a non-empty list")
    baseline = raw.get("baseline", {})
    if not isinstance(baseline, dict):
        raise ReplayError(f"{label}.baseline must be an object")
    case = {
        "id": case_id,
        "work_shape": _string(raw, "work_shape", label),
        "source_revision": source_revision,
        "contract": [_reference(item, f"{label}.contract[{number}]") for number, item in enumerate(contract)],
        "authoritative_evidence": [_reference(item, f"{label}.authoritative_evidence[{number}]") for number, item in enumerate(evidence)],
        "baseline": baseline,
    }
    supplied = _digest_value(_string(raw, "case_sha256", label), f"{label}.case_sha256")
    if supplied != _digest(case):
        raise ReplayError(f"{label} has frozen-case drift: case_sha256 does not match its content")
    case["case_sha256"] = supplied
    return case


def load_suite(path: Path) -> dict[str, Any]:
    raw = _read_json(path, "replay suite")
    if raw.get("version") != VERSION:
        raise ReplayError(f"replay suite version must be {VERSION}")
    cases = raw.get("cases")
    if not isinstance(cases, list) or len(cases) < 5 or len(cases) > 10:
        raise ReplayError("replay suite must contain 5-10 frozen cases")
    normalized = [_case(case, index) for index, case in enumerate(cases)]
    ids = [case["id"] for case in normalized]
    if len(set(ids)) != len(ids):
        raise ReplayError("replay suite contains duplicate case ids")
    suite = {"version": VERSION, "cases": normalized}
    supplied = _digest_value(_string(raw, "suite_sha256", "suite"), "suite.suite_sha256")
    if supplied != _digest(suite):
        raise ReplayError("replay suite has frozen-case drift: suite_sha256 does not match its content")
    suite["suite_sha256"] = supplied
    return suite


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)


def _git_text(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode:
        raise ReplayError((result.stderr or result.stdout).strip() or f"git {' '.join(args)} failed")
    return result.stdout


def validate_suite(root: Path, suite: dict[str, Any]) -> dict[str, Any]:
    """Verify every pinned revision and evidence object from Git, read-only."""
    checked: list[dict[str, str]] = []
    for case in suite["cases"]:
        _git_text(root, "cat-file", "-e", f"{case['source_revision']}^{{commit}}")
        for reference in case["contract"] + case["authoritative_evidence"]:
            content = _git_text(root, "show", f"{reference['revision']}:{reference['path']}")
            actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if actual != reference["sha256"]:
                raise ReplayError(f"{case['id']} has frozen-case drift: {reference['path']} digest changed")
        if case["baseline"].get("wall_time_source") == "historical-automated-checks":
            checks = [ref for ref in case["authoritative_evidence"] if ref["path"].endswith("/automated-checks.json")]
            if len(checks) != 1:
                raise ReplayError(f"{case['id']} needs one pinned automated checks receipt")
            receipt = json.loads(_git_text(root, "show", f"{checks[0]['revision']}:{checks[0]['path']}"))
            commands = receipt.get("executed_commands", [])
            if receipt.get("outcome") != "success" or not commands or any(command.get("outcome") != "success" for command in commands):
                raise ReplayError(f"{case['id']} historical checks do not prove a successful baseline")
            actual_seconds = round(sum(command["duration_seconds"] for command in commands), 3)
            if actual_seconds != case["baseline"].get("wall_time_seconds"):
                raise ReplayError(f"{case['id']} historical wall-time baseline differs from its pinned receipt")
        checked.append({"case_id": case["id"], "source_revision": case["source_revision"], "status": "valid"})
    return {"status": "valid", "suite_sha256": suite["suite_sha256"], "cases": checked}


@contextmanager
def isolated_workspace(root: Path, revision: str) -> Iterator[Path]:
    """Create a disposable detached clone without changing the source checkout."""
    before_head = _git_text(root, "rev-parse", "HEAD").strip()
    with tempfile.TemporaryDirectory(prefix="dev-platform-harness-replay-") as temporary:
        clone = Path(temporary) / "case"
        # A fresh repository with a read-only alternates reference is quicker
        # than a local clone while avoiding hardlinks and any source writes.
        # The detached checkout still proves the exact historical tree.
        result = subprocess.run(["git", "init", "--quiet", str(clone)], text=True, capture_output=True, check=False)
        if result.returncode:
            raise ReplayError((result.stderr or result.stdout).strip() or "cannot create isolated replay repository")
        common_dir = Path(_git_text(root, "rev-parse", "--git-common-dir").strip())
        if not common_dir.is_absolute():
            common_dir = (root / common_dir).resolve()
        alternate = clone / ".git" / "objects" / "info" / "alternates"
        alternate.parent.mkdir(parents=True, exist_ok=True)
        alternate.write_text(str(common_dir / "objects") + "\n", encoding="utf-8")
        _git_text(clone, "checkout", "--detach", "--quiet", revision)
        if _git_text(clone, "rev-parse", "HEAD").strip() != revision:
            raise ReplayError("isolated replay clone did not resolve the exact requested revision")
        yield clone
    if _git_text(root, "rev-parse", "HEAD").strip() != before_head:
        raise ReplayError("replay changed source HEAD; evidence is invalid")


def _metric_comparison(baseline: object, candidate: object) -> dict[str, Any]:
    if not isinstance(baseline, (int, float)) or isinstance(baseline, bool) or not isinstance(candidate, (int, float)) or isinstance(candidate, bool):
        return {"status": "unknown", "baseline": baseline if baseline is None else None, "candidate": candidate if candidate is None else None}
    return {"status": "comparable", "baseline": baseline, "candidate": candidate, "delta": candidate - baseline}


def evaluate(root: Path, suite: dict[str, Any], candidate_path: Path) -> dict[str, Any]:
    candidate = _read_json(candidate_path, "candidate evidence")
    if candidate.get("version") != VERSION:
        raise ReplayError(f"candidate evidence version must be {VERSION}")
    if _string(candidate, "suite_sha256", "candidate") != suite["suite_sha256"]:
        raise ReplayError("candidate evidence is not bound to this frozen suite")
    candidate_id = _string(candidate, "candidate_id", "candidate")
    changes = candidate.get("harness_changes")
    if not isinstance(changes, list) or not changes or any(change not in HARNESS_CHANGES for change in changes):
        raise ReplayError("candidate.harness_changes must be a non-empty list of supported harness changes")
    native_control = changes == ["native-baseline-control"]
    if "native-baseline-control" in changes and not native_control:
        raise ReplayError("native baseline control cannot be combined with a harness change")
    acceptance = candidate.get("capability_acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("verification") != "pass" or acceptance.get("reference") != "match":
        raise ReplayError("candidate.capability_acceptance must explicitly require verification=pass and reference=match")
    raw_results = candidate.get("results")
    if not isinstance(raw_results, list):
        raise ReplayError("candidate.results must be a list")
    results = {item.get("case_id"): item for item in raw_results if isinstance(item, dict) and isinstance(item.get("case_id"), str)}
    if len(results) != len(raw_results) or set(results) != {case["id"] for case in suite["cases"]}:
        raise ReplayError("candidate.results must contain exactly one result for every frozen case")
    validation = validate_suite(root, suite)
    report_cases: list[dict[str, Any]] = []
    for case in suite["cases"]:
        # Materialization is intentionally isolated.  Candidate commands are
        # outside this interface, preventing a replay report from executing
        # unbounded code in the integration checkout.
        with isolated_workspace(root, case["source_revision"]):
            pass
        observed = results[case["id"]]
        if native_control and (observed.get("verification") != "pass" or observed.get("reference") != "match" or observed.get("metrics") != {"wall_time_seconds": case["baseline"]["wall_time_seconds"]}):
            raise ReplayError(f"{case['id']} native control must reuse its pinned historical verification and wall time exactly")
        capability_passed = observed.get("verification") == "pass" and observed.get("reference") == "match"
        entry: dict[str, Any] = {
            "case_id": case["id"],
            "capability": "passed" if capability_passed else "failed",
            "observed": {"verification": observed.get("verification"), "reference": observed.get("reference")},
        }
        if capability_passed:
            metrics = observed.get("metrics", {})
            if not isinstance(metrics, dict):
                raise ReplayError(f"candidate result {case['id']}.metrics must be an object")
            entry["efficiency"] = {metric: _metric_comparison(case["baseline"].get(metric), metrics.get(metric)) for metric in METRICS}
        else:
            entry["efficiency"] = {"status": "not-evaluated", "reason": "capability gate failed; efficiency cannot be promoted"}
        report_cases.append(entry)
    qualified = all(entry["capability"] == "passed" for entry in report_cases)
    comparisons = [
        metric
        for entry in report_cases
        if entry["capability"] == "passed"
        for metric in entry["efficiency"].values()
        if isinstance(metric, dict) and metric.get("status") == "comparable"
    ]
    # Externally supplied observations require independent assessment before
    # a resource-saving claim can be promoted. The bundled native control can
    # be verified here, but its delta is zero by construction.
    positive = native_control and qualified and any(metric["delta"] < 0 for metric in comparisons)
    return {
        "version": VERSION,
        "kind": "harness-replay-advisory-report",
        "advisory": True,
        "candidate_id": candidate_id,
        "candidate_evidence": "pinned-historical-control" if native_control else "supplied-external-observation",
        "harness_changes": changes,
        "suite_sha256": suite["suite_sha256"],
        "suite_validation": validation,
        "capability_gate": "passed" if qualified else "failed",
        "positive_efficiency_conclusion": positive,
        "efficiency_evidence": "available" if comparisons else "unknown",
        "cases": report_cases,
        "non_effects": ["routing", "context-policy", "runtime-defaults", "release-state", "backlog"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or evaluate a frozen Dev Platform harness replay suite.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git checkout containing the frozen history (default: cwd)")
    parser.add_argument("--suite", type=Path, required=True, help="Frozen replay suite JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate frozen identity and historical evidence")
    evaluate_parser = commands.add_parser("evaluate", help="Produce an advisory capability-first comparison")
    evaluate_parser.add_argument("--candidate", type=Path, required=True, help="Bounded candidate evidence JSON")
    evaluate_parser.add_argument("--report", type=Path, required=True, help="Report destination")
    args = parser.parse_args()
    try:
        suite = load_suite(args.suite)
        if args.command == "validate":
            print(json.dumps(validate_suite(args.root.resolve(), suite), indent=2, sort_keys=True))
            return
        report = evaluate(args.root.resolve(), suite, args.candidate)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "written", "report": str(args.report), "capability_gate": report["capability_gate"]}, sort_keys=True))
    except ReplayError as exc:
        raise SystemExit(f"Harness replay blocked: {exc}") from exc


if __name__ == "__main__":
    main()
