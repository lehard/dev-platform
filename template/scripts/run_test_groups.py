#!/usr/bin/env python3
"""Execute canonical unit-test groups with proven total coverage.

The mandatory suite is declared as named groups in the check configuration.  A
group is a set of `unittest` targets (module or `module.Class`) plus an
execution mode:

    [test_groups.publication]
    targets = ["test_git_lifecycle", "test_publication_state"]
    mode = "parallel"

`--all` is the protected-full path.  Before running anything it proves that the
declared groups collect exactly the tests `unittest discover` collects, so a
group that silently drops a module or a test class fails closed instead of
reporting a faster green run.  `--group` selects a bounded subset for local
feedback and never claims full coverage.

Parallel groups run concurrently as separate processes; serial groups run one at
a time so a legitimate shared boundary does not force the whole suite to
serialize.  Any failing group fails the aggregate result.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from _platform_common import current_worktree_root, read_platform_config, validation_subprocess_env

DEFAULT_START_DIR = "tests"
PARALLEL = "parallel"
SERIAL = "serial"


class TestGroupError(RuntimeError):
    """The declared group configuration cannot be trusted as mandatory coverage."""


def load_check_config(root: Path) -> dict[str, Any]:
    import tomllib

    relative = read_platform_config(root).get("paths", {}).get("checks", "dev-platform/checks.toml")
    path = root / relative
    if not path.exists():
        raise TestGroupError(f"Check configuration not found: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def start_dir_name(config: dict[str, Any]) -> str:
    return str(config.get("settings", {}).get("test_discovery_start", DEFAULT_START_DIR))


def read_groups(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = config.get("test_groups", {})
    if not isinstance(raw, dict) or not raw:
        raise TestGroupError("No [test_groups] are configured; the group runner has nothing authoritative to execute.")
    groups: dict[str, dict[str, Any]] = {}
    for group_id, rule in raw.items():
        if not isinstance(rule, dict):
            raise TestGroupError(f"Test group {group_id!r} must be a table.")
        targets = rule.get("targets", [])
        if not isinstance(targets, list) or not targets or not all(isinstance(item, str) for item in targets):
            raise TestGroupError(f"Test group {group_id!r} must declare a non-empty list of unittest targets.")
        mode = str(rule.get("mode", PARALLEL))
        if mode not in (PARALLEL, SERIAL):
            raise TestGroupError(f"Test group {group_id!r} has unsupported mode {mode!r}; use {PARALLEL!r} or {SERIAL!r}.")
        groups[str(group_id)] = {"targets": list(targets), "mode": mode}
    return groups


def collect_ids(tests: unittest.TestSuite) -> list[str]:
    collected: list[str] = []
    for item in tests:
        if isinstance(item, unittest.TestSuite):
            collected.extend(collect_ids(item))
        else:
            collected.append(item.id())
    return collected


def discovered_ids(root: Path, start_dir: str) -> list[str]:
    start = str((root / start_dir).resolve())
    if start not in sys.path:
        sys.path.insert(0, start)
    return collect_ids(unittest.TestLoader().discover(start, top_level_dir=start))


def declared_ids(root: Path, start_dir: str, groups: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    start = str((root / start_dir).resolve())
    if start not in sys.path:
        sys.path.insert(0, start)
    loader = unittest.TestLoader()
    return {group_id: collect_ids(loader.loadTestsFromNames(rule["targets"])) for group_id, rule in groups.items()}


def coverage_report(root: Path, start_dir: str, groups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compare declared group membership against discovery at test-id granularity."""
    discovered = set(discovered_ids(root, start_dir))
    per_group = declared_ids(root, start_dir, groups)

    owners: dict[str, list[str]] = {}
    for group_id, ids in per_group.items():
        for test_id in ids:
            owners.setdefault(test_id, []).append(group_id)

    declared = set(owners)
    return {
        "discovered_test_count": len(discovered),
        "declared_test_count": len(declared),
        "missing_from_groups": sorted(discovered - declared),
        "declared_but_not_discovered": sorted(declared - discovered),
        "duplicated_tests": sorted(test_id for test_id, group_ids in owners.items() if len(group_ids) > 1),
        "group_test_counts": {group_id: len(ids) for group_id, ids in sorted(per_group.items())},
    }


def require_total_coverage(report: dict[str, Any]) -> None:
    problems = []
    if report["missing_from_groups"]:
        problems.append(f"{len(report['missing_from_groups'])} discovered test(s) belong to no group: " + ", ".join(report["missing_from_groups"][:5]))
    if report["declared_but_not_discovered"]:
        problems.append(f"{len(report['declared_but_not_discovered'])} declared test(s) are not discoverable: " + ", ".join(report["declared_but_not_discovered"][:5]))
    if report["duplicated_tests"]:
        problems.append(f"{len(report['duplicated_tests'])} test(s) appear in more than one group: " + ", ".join(report["duplicated_tests"][:5]))
    if problems:
        raise TestGroupError(
            "Declared test groups are not equivalent to the discovered mandatory suite; refusing to report a faster full run. "
            + "; ".join(problems)
        )


def group_env(root: Path, start_dir: str) -> dict[str, str]:
    env = validation_subprocess_env()
    start = str((root / start_dir).resolve())
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = start + (os.pathsep + existing if existing else "")
    return env


def run_group(root: Path, start_dir: str, group_id: str, rule: dict[str, Any], verbose: bool) -> dict[str, Any]:
    command = [sys.executable, "-m", "unittest"]
    if verbose:
        command.append("-v")
    command.extend(rule["targets"])
    started = time.monotonic()
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, env=group_env(root, start_dir))
    duration = time.monotonic() - started
    return {
        "group": group_id,
        "mode": rule["mode"],
        "duration_seconds": round(duration, 3),
        "outcome": "success" if result.returncode == 0 else "failure",
        "exit_code": result.returncode,
        "output": (result.stdout or "") + (result.stderr or ""),
    }


def report_group(record: dict[str, Any]) -> None:
    summary = {key: value for key, value in record.items() if key != "output"}
    print("DEV_PLATFORM_TEST_GROUP: " + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    if record["outcome"] == "failure":
        print(f"----- failing group {record['group']} -----", flush=True)
        print(record["output"].rstrip(), flush=True)


def execute(root: Path, start_dir: str, groups: dict[str, dict[str, Any]], jobs: int, verbose: bool) -> list[dict[str, Any]]:
    parallel = {gid: rule for gid, rule in groups.items() if rule["mode"] == PARALLEL}
    serial = {gid: rule for gid, rule in groups.items() if rule["mode"] == SERIAL}
    records: list[dict[str, Any]] = []

    if parallel:
        workers = max(1, min(jobs, len(parallel)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {gid: pool.submit(run_group, root, start_dir, gid, rule, verbose) for gid, rule in parallel.items()}
            for group_id in sorted(futures):
                record = futures[group_id].result()
                report_group(record)
                records.append(record)

    for group_id in sorted(serial):
        record = run_group(root, start_dir, group_id, serial[group_id], verbose)
        report_group(record)
        records.append(record)

    return records


# A conservative host-independent ceiling for *automatically* selected
# parallelism. Every group already shells out to a `unittest` process that
# itself spawns helper subprocesses, so matching `cpu_count` oversubscribes a
# busy machine and turns process-start scheduling delay into flaky timeouts. An
# explicit `DEV_PLATFORM_TEST_JOBS` is always honoured as-is.
_DEFAULT_JOBS_CEILING = 4


def resolve_jobs() -> tuple[int, str]:
    """Return the automatic parallelism and whether an operator selected it."""
    configured = os.environ.get("DEV_PLATFORM_TEST_JOBS")
    if configured and configured.isdigit() and int(configured) > 0:
        return int(configured), "DEV_PLATFORM_TEST_JOBS"
    return max(1, min(_DEFAULT_JOBS_CEILING, (os.cpu_count() or 2) - 1)), "auto-capped"


def default_jobs() -> int:
    return resolve_jobs()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical unit-test groups with proven mandatory coverage.")
    parser.add_argument("--all", action="store_true", help="Run every declared group as the mandatory suite.")
    parser.add_argument("--group", action="append", default=[], help="Run only this group (repeatable); never claims full coverage.")
    parser.add_argument("--jobs", type=int, default=None, help="Maximum concurrent parallel groups.")
    parser.add_argument("--list", action="store_true", help="Print the declared groups and their coverage, then exit.")
    parser.add_argument("--verify-coverage", action="store_true", help="Only prove group/discovery equivalence, then exit.")
    parser.add_argument("--evidence", help="Write group-level result and duration evidence to this JSON file.")
    parser.add_argument("--quiet", action="store_true", help="Do not pass -v to the group processes.")
    args = parser.parse_args()

    root = current_worktree_root()
    try:
        config = load_check_config(root)
        groups = read_groups(config)
        start_dir = start_dir_name(config)

        if args.list:
            report = coverage_report(root, start_dir, groups)
            print(json.dumps({"groups": {gid: rule for gid, rule in sorted(groups.items())}, "coverage": report}, ensure_ascii=False, indent=2))
            return 0

        if args.verify_coverage:
            report = coverage_report(root, start_dir, groups)
            require_total_coverage(report)
            print("DEV_PLATFORM_TEST_COVERAGE: " + json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
            return 0

        if args.group and args.all:
            raise TestGroupError("--all and --group are mutually exclusive; --group is a bounded local subset.")
        if not args.group and not args.all:
            args.all = True

        if args.all:
            selected = groups
            report = coverage_report(root, start_dir, groups)
            require_total_coverage(report)
            print("DEV_PLATFORM_TEST_COVERAGE: " + json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        else:
            requested = sorted(set(args.group))
            unknown = [group_id for group_id in requested if group_id not in groups]
            if unknown:
                raise TestGroupError("Unknown test group(s): " + ", ".join(unknown))
            selected = {group_id: groups[group_id] for group_id in requested}
    except TestGroupError as exc:
        print(f"Test group configuration blocked execution: {exc}", file=sys.stderr)
        return 2

    if args.jobs is not None and args.jobs > 0:
        jobs, jobs_source = args.jobs, "cli"
    elif args.jobs is not None:
        print("--jobs must be a positive integer", file=sys.stderr)
        return 2
    else:
        jobs, jobs_source = resolve_jobs()

    records = execute(root, start_dir, selected, jobs, not args.quiet)
    failed = [record["group"] for record in records if record["outcome"] == "failure"]
    total = round(sum(record["duration_seconds"] for record in records), 3)
    slowest = max((record["duration_seconds"] for record in records), default=0.0)
    aggregate = {
        "mode": "all" if args.all else "selected",
        "group_count": len(records),
        "failed_groups": sorted(failed),
        "outcome": "failure" if failed else "success",
        "group_seconds_total": total,
        "slowest_group_seconds": slowest,
        "jobs": jobs,
        "jobs_source": jobs_source,
    }
    print("DEV_PLATFORM_TEST_AGGREGATE: " + json.dumps(aggregate, ensure_ascii=False, sort_keys=True), flush=True)

    if args.evidence:
        path = (root / args.evidence).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "aggregate": aggregate,
            "groups": [{key: value for key, value in record.items() if key != "output"} for record in records],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
