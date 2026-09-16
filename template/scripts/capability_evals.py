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
import shutil
import subprocess
import tempfile
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
EVIDENCE_POLICY = (
    "Reports retain case identifiers, prompt digests, bounded statuses, and provenance only; "
    "prompts, transcripts, secrets, and chain-of-thought are excluded."
)

# `claude plugin eval` was introduced in Claude Code 2.1.269 (confirmed against the
# published 2.1.269-2.1.273 releases during backlog #108 preflight). Older CLIs
# expose `claude plugin` without an `eval` subcommand at all.
MIN_NATIVE_VERSION = (2, 1, 269)
NATIVE_TIMEOUT_SECONDS = 900
DEFAULT_MAX_COST_USD = 1.0
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
# Native runs execute as a full `claude` child process on the operator's own
# credential; when that process cannot authenticate, the boundary is runtime
# availability, not a truthful behavioral non-trigger.
_AUTH_FAILURE_MARKERS = (
    "not logged in",
    "oauth session expired",
    "please run /login",
    "failed to authenticate",
    "auth_failed",
    "unauthenticated",
)
_TIMEOUT_MARKERS = ("timed out", "timeout")


class EvalError(RuntimeError):
    pass


def decision_for(change_kind: str, *, runtime: str = "unavailable", explicit: bool = False) -> dict[str, str]:
    """Classify lifecycle work without claiming that an unavailable runner ran."""
    if change_kind not in CHANGE_KINDS:
        raise EvalError(f"unsupported eval change kind: {change_kind}")
    if explicit:
        return {
            "decision": "run" if runtime in ("fixture", "claude") else "blocked/unavailable",
            "reason": (
                "explicit evaluation requested; deterministic fixture adapter is available"
                if runtime == "fixture"
                else "explicit evaluation requested; native Claude plugin eval adapter is available"
                if runtime == "claude"
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
    if runtime == "claude":
        return {
            "decision": "run",
            "reason": "material capability change can execute through the native Claude plugin eval adapter",
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


def probe_claude_native(claude_bin: str) -> dict[str, Any]:
    """Bounded, side-effect-free compatibility check; never claims support without evidence.

    Only runs ``--version`` and ``plugin eval --help`` -- both read-only, free,
    and require no credential -- so calling this never spends budget or risks
    executing untrusted plugin code.
    """
    resolved = shutil.which(claude_bin)
    if not resolved:
        return {"available": False, "version": None, "reason": f"{claude_bin!r} was not found on PATH"}
    try:
        version_proc = subprocess.run([resolved, "--version"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "version": None, "reason": f"could not execute {claude_bin} --version: {exc}"}
    if version_proc.returncode != 0:
        return {"available": False, "version": None, "reason": f"{claude_bin} --version exited {version_proc.returncode}"}
    match = _VERSION_RE.search(version_proc.stdout)
    if not match:
        return {"available": False, "version": None, "reason": "could not parse Claude Code version output"}
    version = tuple(int(part) for part in match.groups())
    version_str = ".".join(str(part) for part in version)
    if version < MIN_NATIVE_VERSION:
        minimum = ".".join(str(part) for part in MIN_NATIVE_VERSION)
        return {
            "available": False,
            "version": version_str,
            "reason": f"Claude Code {version_str} does not expose plugin eval (requires >= {minimum})",
        }
    try:
        help_proc = subprocess.run([resolved, "plugin", "eval", "--help"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "available": False,
            "version": version_str,
            "reason": f"could not execute {claude_bin} plugin eval --help: {exc}",
        }
    if help_proc.returncode != 0 or "eval" not in help_proc.stdout.lower():
        return {
            "available": False,
            "version": version_str,
            "reason": "installed Claude Code does not expose a working plugin eval subcommand",
        }
    return {"available": True, "version": version_str, "reason": None, "binary": resolved}


def _classify_run_error(text: str) -> str:
    lowered = (text or "").lower()
    if any(marker in lowered for marker in _AUTH_FAILURE_MARKERS):
        return "blocked/unavailable"
    if any(marker in lowered for marker in _TIMEOUT_MARKERS):
        return "timeout"
    return "runtime-error"


def _native_case_status(entry: dict[str, Any]) -> str:
    error = entry.get("error")
    if isinstance(error, str) and error.strip():
        return _classify_run_error(error)
    passed = entry.get("passed")
    if passed is True:
        return "triggered"
    if passed is False:
        return "not-triggered"
    return "unknown"


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


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    distribution: Counter[str] = Counter()
    for result in results:
        distribution.update(result["status_distribution"])
    return {
        "case_count": len(results),
        "passed": sum(item["passed"] is True for item in results),
        "failed": sum(item["passed"] is False for item in results),
        "incomplete": sum(item["passed"] is None for item in results),
        "status_distribution": dict(sorted(distribution.items())),
    }


def _compose_report(
    fixture: dict[str, Any], *, adapter: dict[str, Any], runs: int, results: list[dict[str, Any]], quality: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate": {"capability_id": fixture["capability"], "content_sha256": fixture["content_sha256"]},
        "adapter": adapter,
        "runs_per_case": runs,
        "results": results,
        "summary": _summarize(results),
        "quality_comparisons": quality,
        "evidence_policy": EVIDENCE_POLICY,
    }


def _unavailable_report(fixture: dict[str, Any], *, runs: int, provider: str, reason: str) -> dict[str, Any]:
    """A truthful blocked/unavailable report: no case is scored, none is a fabricated non-trigger."""
    results = [_case_result(case, ["blocked/unavailable"] * runs) for case in fixture["cases"]]
    quality = [
        {
            "comparison_id": item["id"],
            "objective_verifier": item["objective_verifier"],
            "baseline": "not-verified",
            "candidate": "not-verified",
            "improved": None,
        }
        for item in fixture["quality_comparisons"]
    ]
    adapter = {"provider": provider, "runtime": "none", "status": "blocked/unavailable", "reason": reason}
    return _compose_report(fixture, adapter=adapter, runs=runs, results=results, quality=quality)


def run_claude_native(
    fixture: dict[str, Any],
    *,
    target: Path,
    runs: int,
    claude_bin: str = "claude",
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    timeout_seconds: int = NATIVE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Bridge the provider-neutral fixture contract onto ``claude plugin eval``.

    The loaded fixture is hash-only (see ``load_fixture``): prompt text never
    re-enters this process. Live execution instead runs against ``target``, an
    on-disk eval suite the operator authored to match the reviewed fixture; this
    function re-hashes each native prompt and refuses to trust evidence for a
    case whose on-disk prompt has drifted from the reviewed ``prompt_sha256``.
    Only ``--version`` and ``plugin eval --help`` run during the compatibility
    probe; the plugin itself only executes once that probe succeeds, and never
    with ``--scaffold``/``--allow-tools``/``--allow-real-servers`` so a capability
    eval cannot reach beyond its own sandboxed conversation.
    """
    probe = probe_claude_native(claude_bin)
    if not probe["available"]:
        return _unavailable_report(fixture, runs=runs, provider="claude", reason=probe["reason"])

    with tempfile.TemporaryDirectory(prefix="capability-eval-") as scratch:
        output_path = Path(scratch) / "native-result.json"
        command = [
            probe["binary"], "plugin", "eval", str(target),
            "--runs", str(runs),
            "--concurrency", "1",
            "--threshold", "0",
            "--mocks", "record",
            "--trust-plugin",
            "--max-cost-usd", str(max_cost_usd),
            "--json", str(output_path),
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return _unavailable_report(
                fixture, runs=runs, provider="claude",
                reason=f"claude plugin eval did not complete within {timeout_seconds}s",
            )
        except OSError as exc:
            return _unavailable_report(
                fixture, runs=runs, provider="claude", reason=f"could not execute claude plugin eval: {exc}"
            )

        if not output_path.is_file():
            detail = (process.stderr or process.stdout or "no diagnostic output").strip()[:500]
            return _unavailable_report(
                fixture, runs=runs, provider="claude",
                reason=f"claude plugin eval exited {process.returncode} without a JSON report: {detail}",
            )

        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvalError(f"claude plugin eval produced an unreadable JSON report: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        raise EvalError(
            "claude plugin eval report has an unsupported schema; recording the boundary instead of guessing at its shape"
        )

    partial_reason: str | None = None
    if payload.get("partial") is True:
        partial_reason = str(payload.get("partialReason") or "unspecified")
        if _classify_run_error(partial_reason) == "blocked/unavailable":
            return _unavailable_report(
                fixture, runs=runs, provider="claude",
                reason=f"claude plugin eval run was partial: {partial_reason}",
            )

    native_cases = {case.get("name"): case for case in payload.get("cases", []) if isinstance(case, dict)}
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        native_case = native_cases.get(case["id"])
        if native_case is None:
            results.append(_case_result(case, ["unknown"] * runs))
            continue
        prompt_markdown = native_case.get("promptMarkdown")
        if not isinstance(prompt_markdown, str) or _case_digest(prompt_markdown) != case["prompt_sha256"]:
            raise EvalError(
                f"on-disk eval suite prompt for case {case['id']!r} does not match the reviewed fixture hash; "
                "the suite drifted from reviewed content and must be re-authored, not silently trusted"
            )
        entries = native_case.get("arms", {}).get("with", [])
        if not isinstance(entries, list) or len(entries) < runs:
            raise EvalError(f"native case {case['id']!r} has fewer than {runs} recorded runs")
        samples = [_native_case_status(entry) for entry in entries[:runs] if isinstance(entry, dict)]
        results.append(_case_result(case, samples))

    quality = [
        {
            "comparison_id": item["id"],
            "objective_verifier": item["objective_verifier"],
            "baseline": "not-verified",
            "candidate": "not-verified",
            "improved": None,
        }
        for item in fixture["quality_comparisons"]
    ]
    adapter = {
        "provider": "claude",
        "runtime": "claude-plugin-eval",
        "status": "supported",
        "claude_version": probe["version"],
        "target": str(target),
    }
    if partial_reason is not None:
        adapter["partial_reason"] = partial_reason
    return _compose_report(fixture, adapter=adapter, runs=runs, results=results, quality=quality)


def run_fixture(
    fixture: dict[str, Any],
    *,
    runtime: str,
    runs: int,
    target: Path | None = None,
    claude_bin: str = "claude",
    max_cost_usd: float = DEFAULT_MAX_COST_USD,
    timeout_seconds: int = NATIVE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if runs < 1:
        raise EvalError("runs must be positive")
    if runtime == "claude":
        if target is None:
            raise EvalError(
                "runtime claude requires --target pointing at the capability's on-disk eval suite "
                "(a skills-dir plugin claude plugin eval can resolve)"
            )
        return run_claude_native(
            fixture, target=Path(target), runs=runs, claude_bin=claude_bin,
            max_cost_usd=max_cost_usd, timeout_seconds=timeout_seconds,
        )
    supported = runtime == "fixture"
    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        if len(case["samples"]) < runs:
            raise EvalError(f"fixture case {case['id']} has fewer than {runs} samples")
        samples = case["samples"][:runs] if supported else ["unsupported"] * runs
        results.append(_case_result(case, samples))
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
    return _compose_report(fixture, adapter=adapter, runs=runs, results=results, quality=quality)


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
    decision.add_argument("--runtime", choices=("unavailable", "fixture", "claude"), default="unavailable")
    decision.add_argument("--explicit", action="store_true")
    validate = sub.add_parser("validate-fixture", help="validate a bounded, sanitized fixture")
    validate.add_argument("--fixture", required=True)
    run = sub.add_parser("run", help="run a deterministic fixture, a native Claude plugin eval, or a truthful unsupported-provider report")
    run.add_argument("--fixture", required=True)
    run.add_argument("--runtime", choices=("fixture", "codex", "claude"), default="fixture")
    run.add_argument("--runs", type=int, default=3)
    run.add_argument("--output", help="optional report path; default is stdout only")
    run.add_argument("--target", help="on-disk eval suite (skills-dir plugin) for --runtime claude")
    run.add_argument("--claude-bin", default="claude", help="claude executable to probe/invoke for --runtime claude")
    run.add_argument("--max-cost-usd", type=float, default=DEFAULT_MAX_COST_USD, help="hard cost ceiling passed to claude plugin eval")
    run.add_argument("--timeout-seconds", type=int, default=NATIVE_TIMEOUT_SECONDS, help="subprocess timeout for claude plugin eval")
    args = parser.parse_args()
    try:
        if args.command == "decision":
            _emit(decision_for(args.change_kind, runtime=args.runtime, explicit=args.explicit), args.json)
            return 0
        fixture = load_fixture(Path(args.fixture))
        if args.command == "validate-fixture":
            _emit({"status": "ok", "capability": fixture["capability"], "case_count": len(fixture["cases"])}, args.json)
            return 0
        report = run_fixture(
            fixture, runtime=args.runtime, runs=args.runs,
            target=Path(args.target) if args.target else None,
            claude_bin=args.claude_bin, max_cost_usd=args.max_cost_usd, timeout_seconds=args.timeout_seconds,
        )
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _emit(report, args.json)
        return 0
    except EvalError as exc:
        _emit({"status": "error", "error": str(exc)}, args.json)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
