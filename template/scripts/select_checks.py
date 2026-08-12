from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from _platform_common import (
    TaskFreshnessError,
    current_worktree_root,
    read_platform_config,
    require_fresh_task_base,
    run_git,
    validation_subprocess_env,
)


def load_config(root: Path) -> dict[str, Any]:
    import tomllib

    platform = read_platform_config(root)
    rel = platform.get("paths", {}).get("checks", "dev-platform/checks.toml")
    path = root / rel
    if not path.exists():
        raise SystemExit(f"Check configuration not found: {path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def changed_files(root: Path, base: str | None, explicit: list[str]) -> list[str]:
    if explicit:
        return sorted(set(explicit))

    result: set[str] = set()
    if base:
        diff = run_git(["diff", "--name-only", f"{base}...HEAD"], cwd=root, check=False)
        if diff.returncode == 0:
            result.update(line for line in diff.stdout.splitlines() if line.strip())

    for args in (["diff", "--name-only"], ["diff", "--cached", "--name-only"]):
        diff = run_git(args, cwd=root, check=False)
        if diff.returncode == 0:
            result.update(line for line in diff.stdout.splitlines() if line.strip())

    if not result and not base:
        diff = run_git(["diff", "--name-only", "HEAD~1..HEAD"], cwd=root, check=False)
        if diff.returncode == 0:
            result.update(line for line in diff.stdout.splitlines() if line.strip())

    return sorted(result)


def full_checks(config: dict[str, Any], *, selection_reason: str = "protected-full") -> list[dict[str, Any]]:
    settings = config.get("settings", {})
    commands = list(settings.get("full_commands", []))
    if not commands:
        raise SystemExit("settings.full_commands must not be empty for protected full validation.")
    check = {
        "id": "full",
        "paths": [],
        "commands": commands,
        "selection_reason": selection_reason,
    }
    if "full_evidence_types" in settings:
        check["evidence_types"] = list(settings["full_evidence_types"])
    if "full_required_evidence_types" in settings:
        check["required_evidence_types"] = list(settings["full_required_evidence_types"])
    return [check]


def select(config: dict[str, Any], paths: list[str]) -> list[dict[str, Any]]:
    settings = config.get("settings", {})
    checks = config.get("checks", {})
    full_trigger_patterns = list(settings.get("full_trigger_patterns", []))

    full_trigger_paths = [path for path in paths if full_trigger_patterns and match_any(path, full_trigger_patterns)]
    if full_trigger_paths:
        selected = full_checks(config, selection_reason="high-impact-path")
        selected[0]["id"] = "full-trigger"
        selected[0]["paths"] = full_trigger_paths
        return selected

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    unknown: list[str] = []

    for path in paths:
        matched = False
        for check_id, rule in checks.items():
            patterns = list(rule.get("patterns", []))
            if patterns and match_any(path, patterns):
                matched = True
                if check_id not in seen:
                    check = {
                        "id": check_id,
                        "paths": [],
                        "commands": list(rule.get("commands", [])),
                    }
                    if "evidence_types" in rule:
                        check["evidence_types"] = list(rule["evidence_types"])
                    if "required_evidence_types" in rule:
                        check["required_evidence_types"] = list(rule["required_evidence_types"])
                    selected.append(check)
                    seen.add(check_id)
                next(item for item in selected if item["id"] == check_id)["paths"].append(path)
        if not matched:
            unknown.append(path)

    if unknown:
        selected = full_checks(config, selection_reason="unknown-path")
        selected[0]["id"] = "full-fallback"
        selected[0]["paths"] = unknown
        return selected
    return selected


def commands_for(checks: list[dict[str, Any]]) -> list[str]:
    commands: list[str] = []
    for check in checks:
        for command in check.get("commands", []):
            if command not in commands:
                commands.append(command)
    return commands


def requires_task_freshness(checks: list[dict[str, Any]]) -> bool:
    """Whether this selection will start the configured full validation set."""
    return any(
        str(check.get("selection_reason", "")) in {"protected-full", "high-impact-path", "unknown-path"}
        for check in checks
    )


def selection_status(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a stable, machine-readable distinction between no work and bad coverage."""
    if not checks:
        return {"state": "not-applicable", "command_count": 0, "check_count": 0}

    empty = [str(check["id"]) for check in checks if not check.get("commands", [])]
    malformed: list[str] = []
    missing_evidence: dict[str, list[str]] = {}
    for check in checks:
        check_id = str(check["id"])
        commands = list(check.get("commands", []))
        kinds = list(check.get("evidence_types", []))
        required = list(check.get("required_evidence_types", []))
        if kinds and len(kinds) != len(commands):
            malformed.append(check_id)
            continue
        absent = sorted(set(required) - set(kinds))
        if absent:
            missing_evidence[check_id] = absent

    status: dict[str, Any] = {
        "state": "ready" if not empty and not malformed and not missing_evidence else "invalid-coverage",
        "command_count": len(commands_for(checks)),
        "check_count": len(checks),
    }
    if empty:
        status["empty_check_ids"] = empty
    if malformed:
        status["malformed_evidence_check_ids"] = malformed
    if missing_evidence:
        status["missing_required_evidence"] = missing_evidence
    return status


def validate_platform_selection(checks: list[dict[str, Any]], harness: str) -> dict[str, Any]:
    status = selection_status(checks)
    if harness == "platform" and status["state"] == "invalid-coverage":
        detail = json.dumps(status, ensure_ascii=False, sort_keys=True)
        raise SystemExit(
            "Platform-managed check coverage is invalid: an applicable group has no executable "
            f"commands or lacks its required evidence type. {detail}"
        )
    return status


def configured_empty_check_ids(config: dict[str, Any]) -> list[str]:
    """Expose latent empty groups without treating unrelated files as affected."""
    checks = config.get("checks", {})
    if not isinstance(checks, dict):
        return []
    return sorted(str(check_id) for check_id, rule in checks.items() if isinstance(rule, dict) and not rule.get("commands", []))


def diagnostic_tail(output: str, limit: int = 7000) -> str:
    if len(output) <= limit:
        return output
    return "[output truncated]\n" + output[-limit:]


def command_result(command: str, result: subprocess.CompletedProcess[str], duration_seconds: float) -> dict[str, Any]:
    return {
        "command": command,
        "duration_seconds": round(duration_seconds, 3),
        "outcome": "success" if result.returncode == 0 else "failure",
        "exit_code": result.returncode,
    }


def execute(root: Path, checks: list[dict[str, Any]], evidence_path: Path | None = None) -> int:
    commands = commands_for(checks)
    records: list[dict[str, Any]] = []
    outcome = "success"
    if not commands:
        print("No applicable commands selected.")
        if evidence_path is not None:
            write_evidence(evidence_path, checks, selection_status(checks), records, "not-applicable")
        return 0

    for command in commands:
        print(f"DEV_PLATFORM_CHECK_COMMAND: {command}", flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            env=validation_subprocess_env(),
        )
        evidence = command_result(command, result, time.monotonic() - started)
        records.append(evidence)
        print("DEV_PLATFORM_CHECK_RESULT: " + json.dumps(evidence, ensure_ascii=False), flush=True)
        if result.returncode != 0:
            outcome = "failure"
            if evidence_path is not None:
                write_evidence(evidence_path, checks, selection_status(checks), records, outcome)
            detail = diagnostic_tail((result.stdout or "") + (result.stderr or ""))
            if detail:
                print("DEV_PLATFORM_CHECK_DIAGNOSTIC:\n" + detail.rstrip(), flush=True)
            return result.returncode
    if evidence_path is not None:
        write_evidence(evidence_path, checks, selection_status(checks), records, outcome)
    return 0


def write_evidence(
    path: Path, checks: list[dict[str, Any]], status: dict[str, Any], records: list[dict[str, Any]], outcome: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "selection": status,
        "outcome": outcome,
        "executed_commands": records,
        "selected_checks": checks,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Select conservative project checks from changed files.")
    parser.add_argument("--base", help="Git base ref, e.g. origin/main")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence", help="Write the selected and actually executed command evidence to this JSON file.")
    parser.add_argument("--mode", choices=("local-affected", "protected-full"), default="local-affected")
    parser.add_argument("--protected-full", action="store_true", help="Alias for --mode protected-full.")
    parser.add_argument("--full", action="store_true", help="Deprecated alias for --mode protected-full.")
    args = parser.parse_args()

    if args.protected_full or args.full:
        args.mode = "protected-full"

    root = current_worktree_root()
    config = load_config(root)
    paths = [] if args.mode == "protected-full" else changed_files(root, args.base, args.changed_file)
    checks = full_checks(config) if args.mode == "protected-full" else select(config, paths)
    harness = str(read_platform_config(root).get("harness_mode", "platform"))
    status = validate_platform_selection(checks, harness)

    payload = {"files": paths, "checks": checks, "selection": status, "mode": args.mode}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if paths:
            print("Changed files:")
            for path in paths:
                print(f"  {path}")
        if checks:
            reasons = sorted({str(check.get("selection_reason", "mapped")) for check in checks})
            print(f"Validation mode: {args.mode}; reason: {', '.join(reasons)}; selection: {status['state']}; commands: {status['command_count']}")
        else:
            print(f"Validation mode: {args.mode}; selection: not-applicable; no commands selected.")
    print("DEV_PLATFORM_CHECK_SELECTION: " + json.dumps(status, ensure_ascii=False, sort_keys=True), flush=True)

    if args.execute:
        if harness == "platform" and requires_task_freshness(checks):
            try:
                observed = require_fresh_task_base(root, "origin", str(read_platform_config(root).get("main_branch", "main")))
            except TaskFreshnessError as exc:
                raise SystemExit(
                    "Task freshness gate blocked full/protected validation before any expensive command started: " + str(exc)
                ) from exc
            print(f"Task freshness gate passed: HEAD contains freshly observed origin/{read_platform_config(root).get('main_branch', 'main')} ({observed}).")
        evidence_path = (root / args.evidence).resolve() if args.evidence else None
        return execute(root, checks, evidence_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
