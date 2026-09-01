#!/usr/bin/env python3
"""Run bounded, provider-neutral capability-eval fixtures.

This module deliberately owns neither capability descriptors nor provider
processes.  Descriptors remain the optional-capability lifecycle's source of
truth.  A real provider adapter must supply truthful trigger evidence through
its supported runtime contract; until then Codex and Claude are reported as
unsupported rather than being simulated with a nested CLI process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


STATUSES = {
    "triggered",
    "not-triggered",
    "timeout",
    "runtime-error",
    "unsupported",
    "unknown",
    "blocked/unavailable",
}
EXPECTATIONS = {"trigger", "not-trigger"}
CHANGE_KINDS = {"new", "metadata", "material", "trigger", "behavior", "tool", "safety"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class EvalError(RuntimeError):
    pass


def decision_for(change_kind: str, *, runtime: str = "unavailable", explicit: bool = False) -> dict[str, str]:
    """Classify lifecycle work without claiming that an unavailable runner ran."""
    if change_kind not in CHANGE_KINDS:
        raise EvalError(f"unsupported eval change kind: {change_kind}")
    if explicit:
        return {
            "decision": "run" if runtime == "fixture" else "blocked/unavailable",
            "reason": (
                "explicit evaluation requested; deterministic fixture adapter is available"
                if runtime == "fixture"
                else "explicit evaluation requested, but no supported provider adapter is available"
            ),
        }
    if change_kind == "metadata":
        return {
            "decision": "skip-with-reason",
            "reason": "declared metadata-only change; structural validation remains required",
        }
    if runtime == "fixture":
        return {
            "decision": "run",
            "reason": "material capability change has a bounded deterministic fixture adapter",
        }
    return {
        "decision": "blocked/unavailable",
        "reason": "material capability change requires live eval, but no supported provider adapter/runtime is available",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvalError(f"cannot read eval fixture {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvalError("eval fixture must be a JSON object")
    return value


def _required_string(value: dict[str, Any], key: str, label: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EvalError(f"{label}.{key} must be a non-empty string")
    return item.strip()


def _case_digest(prompt: str) -> str:
    """Preserve correlation without placing prompts into durable reports."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def load_fixture(path: Path) -> dict[str, Any]:
    fixture = _read_json(path)
    if fixture.get("version") != 1:
        raise EvalError("eval fixture version must be 1")
    capability = _required_string(fixture, "capability", "fixture")
    content_sha256 = _required_string(fixture, "content_sha256", "fixture")
    if not SHA256_RE.fullmatch(content_sha256):
        raise EvalError("fixture.content_sha256 must be a lowercase SHA-256")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvalError("fixture.cases must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(cases):
        label = f"fixture.cases[{index}]"
        if not isinstance(raw, dict):
            raise EvalError(f"{label} must be an object")
        case_id = _required_string(raw, "id", label)
        if case_id in seen:
            raise EvalError(f"fixture contains duplicate case id: {case_id}")
        seen.add(case_id)
        expectation = _required_string(raw, "expectation", label)
        if expectation not in EXPECTATIONS:
            raise EvalError(f"{label}.expectation must be trigger or not-trigger")
        prompt = _required_string(raw, "prompt", label)
        if len(prompt) > 500:
            raise EvalError(f"{label}.prompt exceeds the bounded 500-character fixture limit")
        samples = raw.get("samples")
        if not isinstance(samples, list) or not samples:
            raise EvalError(f"{label}.samples must be a non-empty list")
        if any(sample not in STATUSES for sample in samples):
            raise EvalError(f"{label}.samples contains an unsupported run status")
        normalized.append({
            "id": case_id,
            "expectation": expectation,
            "prompt_sha256": _case_digest(prompt),
            "samples": list(samples),
        })
    quality = fixture.get("quality_comparisons", [])
    if not isinstance(quality, list):
        raise EvalError("fixture.quality_comparisons must be a list")
    for index, comparison in enumerate(quality):
        if not isinstance(comparison, dict):
            raise EvalError(f"fixture.quality_comparisons[{index}] must be an object")
        for key in ("id", "objective_verifier", "baseline", "candidate"):
            _required_string(comparison, key, f"fixture.quality_comparisons[{index}]")
        if comparison["baseline"] not in {"verified", "not-verified"} or comparison["candidate"] not in {"verified", "not-verified"}:
            raise EvalError(f"fixture.quality_comparisons[{index}] verification values must be verified or not-verified")
    return {
        "capability": capability,
        "content_sha256": content_sha256,
        "cases": normalized,
        "quality_comparisons": quality,
    }


def _case_result(case: dict[str, Any], samples: list[str]) -> dict[str, Any]:
    counts = Counter(samples)
    comparable = counts["triggered"] + counts["not-triggered"]
    trigger_rate = counts["triggered"] / comparable if comparable else None
    expectation = case["expectation"]
    if comparable != len(samples):
        passed: bool | None = None
    elif expectation == "trigger":
        passed = trigger_rate == 1.0
    else:
        passed = trigger_rate == 0.0
    return {
        "case_id": case["id"],
        "expectation": expectation,
        "prompt_sha256": case["prompt_sha256"],
        "sample_size": len(samples),
        "trigger_rate": trigger_rate,
        "status_distribution": dict(sorted(counts.items())),
        "passed": passed,
    }


def run_fixture(fixture: dict[str, Any], *, runtime: str, runs: int) -> dict[str, Any]:
    if runs < 1:
        raise EvalError("runs must be positive")
    supported = runtime == "fixture"
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        if len(case["samples"]) < runs:
            raise EvalError(f"fixture case {case['id']} has fewer than {runs} samples")
        samples = case["samples"][:runs] if supported else ["unsupported"] * runs
        results.append(_case_result(case, samples))
    distribution: Counter[str] = Counter()
    for result in results:
        distribution.update(result["status_distribution"])
    passed = sum(item["passed"] is True for item in results)
    failed = sum(item["passed"] is False for item in results)
    incomplete = sum(item["passed"] is None for item in results)
    quality = [
        {
            "comparison_id": item["id"],
            "objective_verifier": item["objective_verifier"],
            "baseline": item["baseline"] if supported else "not-verified",
            "candidate": item["candidate"] if supported else "not-verified",
            "improved": (item["baseline"] == "not-verified" and item["candidate"] == "verified") if supported else None,
        }
        for item in fixture["quality_comparisons"]
    ]
    adapter = (
        {"provider": "fixture", "runtime": "deterministic-fixture", "status": "supported"}
        if supported
        else {
            "provider": runtime,
            "runtime": "none",
            "status": "unsupported",
            "reason": "no supported adapter exposes truthful capability-trigger evidence for this provider",
        }
    )
    return {
        "schema_version": 1,
        "candidate": {"capability_id": fixture["capability"], "content_sha256": fixture["content_sha256"]},
        "adapter": adapter,
        "runs_per_case": runs,
        "results": results,
        "summary": {
            "case_count": len(results),
            "passed": passed,
            "failed": failed,
            "incomplete": incomplete,
            "status_distribution": dict(sorted(distribution.items())),
        },
        "quality_comparisons": quality,
        "evidence_policy": "Reports retain case identifiers, prompt digests, bounded statuses, and provenance only; prompts, transcripts, secrets, and chain-of-thought are excluded.",
    }


def _emit(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    elif isinstance(payload, dict):
        for key, value in payload.items():
            print(f"{key}: {value}")
    else:
        print(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate optional capabilities without a provider-specific core schema.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)
    decision = sub.add_parser("decision", help="classify an automatic or explicit eval request")
    decision.add_argument("--change-kind", choices=sorted(CHANGE_KINDS), required=True)
    decision.add_argument("--runtime", choices=("unavailable", "fixture"), default="unavailable")
    decision.add_argument("--explicit", action="store_true")
    validate = sub.add_parser("validate-fixture", help="validate a bounded, sanitized fixture")
    validate.add_argument("--fixture", required=True)
    run = sub.add_parser("run", help="run a deterministic fixture or produce a truthful unsupported-provider report")
    run.add_argument("--fixture", required=True)
    run.add_argument("--runtime", choices=("fixture", "codex", "claude"), default="fixture")
    run.add_argument("--runs", type=int, default=3)
    run.add_argument("--output", help="optional report path; default is stdout only")
    args = parser.parse_args()
    try:
        if args.command == "decision":
            _emit(decision_for(args.change_kind, runtime=args.runtime, explicit=args.explicit), args.json)
            return 0
        fixture = load_fixture(Path(args.fixture))
        if args.command == "validate-fixture":
            _emit({"status": "ok", "capability": fixture["capability"], "case_count": len(fixture["cases"])}, args.json)
            return 0
        report = run_fixture(fixture, runtime=args.runtime, runs=args.runs)
        if args.output:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _emit(report, args.json)
        return 0
    except EvalError as exc:
        _emit({"status": "error", "error": str(exc)}, args.json)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
