from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

BLOCKED_RE = re.compile(r"Managed rollout: BLOCKED:\s*(.*)")
CHECK_COMMAND_RE = re.compile(r"DEV_PLATFORM_CHECK_COMMAND:\s*(.*)")
REJECT_LIST_RE = re.compile(r"Copier left unresolved \.rej files: (.*?)(?:; non-recoverable conflicts: (.*))?$")

# Reason substrings that identify a deterministic safety/config guard rather than
# a transient environment condition. Kept narrow and additive: unmatched reasons
# fall back to the generic "safety_guard" category rather than a false negative.
SAFETY_GUARD_MARKERS = (
    "downstream checkout is dirty",
    "rollout branch already exists",
    "refusing platform downgrade",
    "platform version metadata mismatch",
    "is missing",
    "does not contain",
    "unexpected Copier source",
    "project-owned files changed",
    "project-owned .dev-platform.toml changed",
    "guarded recopy changed harness_mode",
    "reclaimed platform files no longer match",
    "baseline-equivalent rollout proof changed",
    "baseline-equivalent conflict paths do not match",
    "produced no repository diff",
    "Copier recorded",
    "could not inspect",
    "could not fetch recorded platform baseline",
    "DEV_PLATFORM_SOURCE_TOKEN is required",
    "Copier is not installed",
)

COPIER_CONFLICT_MARKERS = (
    "Copier left unresolved .rej files",
    "guarded Copier recopy still left unresolved",
)

RUNTIME_ENVIRONMENT_MARKERS = (
    "node: command not found",
    "wrong node version",
    "python3: command not found",
    "copier: command not found",
)


def last_match(pattern: re.Pattern[str], text: str) -> str | None:
    matches = pattern.findall(text)
    if not matches:
        return None
    value = matches[-1]
    if isinstance(value, tuple):
        value = value[0]
    return value.strip() or None


def parse_conflict_paths(reason: str) -> list[str]:
    match = REJECT_LIST_RE.search(reason)
    if not match:
        return []
    raw = match.group(1) or ""
    paths = [item.strip() for item in raw.split(",") if item.strip()]
    return paths


def classify(reason: str | None, command: str | None) -> tuple[str, str]:
    """Return (stage, category) for a known reason or selected-check failure."""
    if reason:
        if any(marker in reason for marker in RUNTIME_ENVIRONMENT_MARKERS):
            return ("prepare", "runtime_environment")
        if any(marker in reason for marker in COPIER_CONFLICT_MARKERS):
            return ("recovery", "copier_conflict")
        if any(marker in reason for marker in SAFETY_GUARD_MARKERS):
            return ("prepare", "safety_guard")
        return ("prepare", "safety_guard")
    if command:
        return ("downstream_check", "downstream_check")
    return ("unknown", "unknown")


def retry_advisory(category: str) -> str:
    if category in {"safety_guard", "copier_conflict", "publish_guard"}:
        return "pointless"
    if category == "runtime_environment":
        return "pointless"
    return "unknown"


def build_envelope(
    *,
    log_text: str,
    exit_code: int,
    repository: str,
    version: str,
) -> dict[str, Any]:
    reason = last_match(BLOCKED_RE, log_text)
    command = last_match(CHECK_COMMAND_RE, log_text)
    conflict_paths = parse_conflict_paths(reason) if reason else []

    if reason:
        stage, category = classify(reason, None)
        final_reason = reason
        final_command = None
    elif command:
        stage, category = classify(None, command)
        final_reason = f"command failed (exit {exit_code}): {command}"
        final_command = command
    else:
        stage, category = "unknown", "unknown"
        final_reason = f"rollout preparation exited with status {exit_code}"
        final_command = None

    envelope: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "project": repository,
        "target_release": version,
        "stage": stage,
        "category": category,
        "reason": final_reason,
        "command": final_command,
        "exit_code": exit_code,
        "retry_same_inputs": retry_advisory(category),
        "evidence": {
            "marker": "Managed rollout: BLOCKED:" if reason else ("DEV_PLATFORM_CHECK_COMMAND:" if command else None),
            "conflict_paths": conflict_paths,
        },
    }
    return envelope


def render_summary(envelope: dict[str, Any]) -> str:
    lines = [
        "#### Rollout diagnostic",
        "",
        f"- stage: `{envelope['stage']}`",
        f"- category: `{envelope['category']}`",
        f"- reason: {envelope['reason']}",
        f"- exit_code: `{envelope['exit_code']}`",
        f"- retry_same_inputs: `{envelope['retry_same_inputs']}`",
    ]
    if envelope.get("command"):
        lines.append(f"- command: `{envelope['command']}`")
    if envelope["evidence"].get("conflict_paths"):
        lines.append(f"- conflict_paths: {', '.join(envelope['evidence']['conflict_paths'][:10])}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one canonical machine-readable diagnostic envelope for a "
            "terminal failed managed rollout attempt from already-known "
            "structured rollout state."
        )
    )
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    log_text = args.log_file.read_text(encoding="utf-8", errors="replace")
    envelope = build_envelope(
        log_text=log_text,
        exit_code=args.exit_code,
        repository=args.repository,
        version=args.version,
    )
    args.output.write_text(json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    summary = render_summary(envelope)
    if args.summary_output:
        with args.summary_output.open("a", encoding="utf-8") as fh:
            fh.write(summary)
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - diagnostic generation must never fail the rollout
        print(f"rollout_diagnostic: failed to build diagnostic envelope: {exc}", file=sys.stderr)
        raise SystemExit(0)
