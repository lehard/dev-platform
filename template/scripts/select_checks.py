from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
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


def select(config: dict[str, Any], paths: list[str]) -> list[dict[str, Any]]:
    settings = config.get("settings", {})
    checks = config.get("checks", {})
    fallback = list(settings.get("fallback_commands", []))
    full_commands = list(settings.get("full_commands", []))
    full_trigger_patterns = list(settings.get("full_trigger_patterns", []))

    full_trigger_paths = [path for path in paths if full_trigger_patterns and match_any(path, full_trigger_patterns)]
    if full_trigger_paths:
        if not full_commands:
            raise SystemExit(
                "High-impact file matched settings.full_trigger_patterns, but settings.full_commands is empty. "
                "Refusing to downgrade the change to whitespace-only validation."
            )
        return [{"id": "full-trigger", "paths": full_trigger_paths, "commands": full_commands}]

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

    if unknown and fallback:
        selected.append({"id": "fallback", "paths": unknown, "commands": fallback})
    return selected


def full_checks(config: dict[str, Any]) -> list[dict[str, Any]]:
    commands = list(config.get("settings", {}).get("full_commands", []))
    return [{"id": "full", "paths": [], "commands": commands}]


def execute(root: Path, checks: list[dict[str, Any]]) -> int:
    commands: list[str] = []
    for check in checks:
        for command in check.get("commands", []):
            if command not in commands:
                commands.append(command)
    if not commands:
        print("No commands selected.")
        return 0

    for command in commands:
        print(f"+ {command}", flush=True)
        result = subprocess.run(command, cwd=root, shell=True)
        if result.returncode != 0:
            return result.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Select conservative project checks from changed files.")
    parser.add_argument("--base", help="Git base ref, e.g. origin/main")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    root = current_worktree_root()
    config = load_config(root)
    paths = [] if args.full else changed_files(root, args.base, args.changed_file)
    checks = full_checks(config) if args.full else select(config, paths)

    payload = {"files": paths, "checks": checks, "mode": "full" if args.full else "changed"}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if paths:
            print("Changed files:")
            for path in paths:
                print(f"  {path}")
        for check in checks:
            print(f"[{check['id']}]")
            for command in check.get("commands", []):
                print(f"  {command}")
        if not checks:
            print("No checks selected.")

    if args.execute:
        return execute(root, checks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
