from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from _platform_common import current_worktree_root, read_platform_config, run_git


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
    commands = list(config.get("settings", {}).get("full_commands", []))
    if not commands:
        raise SystemExit("settings.full_commands must not be empty for protected full validation.")
    return [{"id": "full", "paths": [], "commands": commands, "selection_reason": selection_reason}]


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
                    selected.append({"id": check_id, "paths": [], "commands": list(rule.get("commands", []))})
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


def execute(root: Path, checks: list[dict[str, Any]]) -> int:
    commands = commands_for(checks)
    if not commands:
        print("No commands selected.")
        return 0

    for command in commands:
        print(f"DEV_PLATFORM_CHECK_COMMAND: {command}", flush=True)
        started = time.monotonic()
        result = subprocess.run(command, cwd=root, shell=True, capture_output=True, text=True)
        evidence = command_result(command, result, time.monotonic() - started)
        print("DEV_PLATFORM_CHECK_RESULT: " + json.dumps(evidence, ensure_ascii=False), flush=True)
        if result.returncode != 0:
            detail = diagnostic_tail((result.stdout or "") + (result.stderr or ""))
            if detail:
                print("DEV_PLATFORM_CHECK_DIAGNOSTIC:\n" + detail.rstrip(), flush=True)
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Select conservative project checks from changed files.")
    parser.add_argument("--base", help="Git base ref, e.g. origin/main")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true")
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

    payload = {"files": paths, "checks": checks, "mode": args.mode}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if paths:
            print("Changed files:")
            for path in paths:
                print(f"  {path}")
        if checks:
            reasons = sorted({str(check.get("selection_reason", "mapped")) for check in checks})
            print(f"Validation mode: {args.mode}; reason: {', '.join(reasons)}; commands: {len(commands_for(checks))}")
        else:
            print(f"Validation mode: {args.mode}; no commands selected.")

    if args.execute:
        return execute(root, checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
