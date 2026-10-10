from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import machine_pool
from _platform_common import (
    TASK_BASE_FRESH,
    PlatformConfigError,
    TaskFreshnessError,
    current_worktree_root,
    lifecycle_mode,
    main_root,
    read_platform_config,
    require_fresh_task_base,
    require_handoff_task_base,
    require_proven_task_base,
    run_git,
    validation_subprocess_env,
)
try:
    from managed_task import ManagedTaskError, require_managed_checkout_identity
except (ImportError, ModuleNotFoundError):  # Compatibility while old renders are upgraded.
    class ManagedTaskError(RuntimeError):
        pass

    def require_managed_checkout_identity(root: Path, *, expected_change: str | None = None, expected_source_issue: str | None = None):
        return None

try:
    from agent_board import HardScopeOverlap, enforce_scope_gate
except (ImportError, ModuleNotFoundError):  # Compatibility while an older rendered project is being upgraded.
    class HardScopeOverlap(RuntimeError):
        pass

    def enforce_scope_gate(root: Path, worktree: Path, branch: str) -> None:
        return None

try:
    from managed_project_status import block_for_scope_conflict
except (ImportError, ModuleNotFoundError):  # Compatibility while an older rendered project is being upgraded.
    def block_for_scope_conflict(root: Path, reason: str):
        return None


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


def instruction_behavior_surface_paths(config: dict[str, Any], paths: list[str]) -> list[str]:
    """Paths eligible for the `instruction-behavior-change` risk class (§0 of design.md)."""
    settings = config.get("settings", {})
    patterns = list(settings.get("instruction_behavior_surface_patterns", []))
    if not patterns:
        return []
    return [path for path in paths if match_any(path, patterns)]


def behavioral_evidence_commands(config: dict[str, Any], runtime: str) -> list[str]:
    table = config.get("behavioral_evidence", {})
    rule = table.get(runtime) if isinstance(table, dict) else None
    if not isinstance(rule, dict):
        return []
    commands = rule.get("commands", [])
    return list(commands) if isinstance(commands, list) else []


def select(config: dict[str, Any], paths: list[str], *, declare_behavior_change: str | None = None) -> list[dict[str, Any]]:
    settings = config.get("settings", {})
    checks = config.get("checks", {})
    full_trigger_patterns = list(settings.get("full_trigger_patterns", []))

    full_trigger_paths = [path for path in paths if full_trigger_patterns and match_any(path, full_trigger_patterns)]
    if full_trigger_paths:
        selected = full_checks(config, selection_reason="high-impact-path")
        selected[0]["id"] = "full-trigger"
        selected[0]["paths"] = full_trigger_paths
        return selected

    if declare_behavior_change:
        behavior_paths = instruction_behavior_surface_paths(config, paths)
        if behavior_paths:
            commands = behavioral_evidence_commands(config, declare_behavior_change)
            if not commands:
                # Model self-report is never accepted as behavioral evidence: a
                # declaration with no configured, executable command for this
                # runtime/provider fails closed to full validation instead of
                # being taken on trust.
                selected = full_checks(config, selection_reason="behavior-declaration-unproven")
                selected[0]["id"] = "full-fallback"
                selected[0]["paths"] = behavior_paths
                return selected
            behavior_check = {
                "id": "instruction-behavior-change",
                "paths": behavior_paths,
                "commands": commands,
                "selection_reason": "instruction-behavior-change",
            }
            remaining = [path for path in paths if path not in behavior_paths]
            return [behavior_check] + select(config, remaining, declare_behavior_change=None)

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


PRECHECK_REASONS = {"high-impact-path", "unknown-path"}


def precheck_outcome(result: subprocess.CompletedProcess[str]) -> str:
    """Classify the runner result: only reported failed test groups block."""
    output = result.stdout or ""
    aggregate = None
    selection = None
    try:
        for line in output.splitlines():
            if line.startswith("DEV_PLATFORM_TEST_AGGREGATE: "):
                aggregate = json.loads(line.split(": ", 1)[1])
            elif line.startswith("DEV_PLATFORM_AFFECTED_SELECTION: "):
                selection = json.loads(line.split(": ", 1)[1])
    except json.JSONDecodeError:
        return "unavailable"
    if not isinstance(aggregate, (dict, type(None))) or not isinstance(selection, (dict, type(None))):
        return "unavailable"
    if result.returncode == 0 and aggregate is None and selection is not None and not selection.get("groups"):
        return "not-applicable"
    if aggregate is None:
        return "unavailable"
    if result.returncode != 0 and aggregate.get("failed_groups"):
        return "failure"
    return "success" if result.returncode == 0 else "unavailable"


def precheck_paths(config: dict[str, Any], checks: list[dict[str, Any]]) -> list[str]:
    """Changed Python paths eligible for the affected-test precheck before a full run."""
    if not config.get("settings", {}).get("affected_precheck") or not config.get("test_groups"):
        return []
    paths: list[str] = []
    for check in checks:
        if str(check.get("selection_reason", "")) in PRECHECK_REASONS:
            paths.extend(path for path in check.get("paths", []) if path.endswith(".py") and path not in paths)
    return paths


def run_precheck(root: Path, paths: list[str], pass_fds: tuple[int, ...] = ()) -> tuple[dict[str, Any], subprocess.CompletedProcess[str]]:
    command = "python3 scripts/run_test_groups.py --quiet " + " ".join(f"--changed-file {shlex.quote(path)}" for path in paths)
    print(f"DEV_PLATFORM_PRECHECK_COMMAND: {command}", flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=root, shell=True, capture_output=True, text=True, env=validation_subprocess_env(),
                            pass_fds=pass_fds)
    record = command_result(command, result, time.monotonic() - started)
    record["role"] = "affected-precheck feedback; not validation coverage"
    print("DEV_PLATFORM_PRECHECK_RESULT: " + json.dumps(record, ensure_ascii=False), flush=True)
    return record, result


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


def failure_descriptor(checks: list[dict[str, Any]], command: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Return a bounded, log-free description of a selected-check failure."""
    descriptor: dict[str, Any] = {
        "failure_class": "selected-command-failure",
        "selected_checks": sorted(
            str(check.get("id", "unknown")) for check in checks if command in check.get("commands", [])
        ),
        "command": command,
        "exit_code": result.returncode,
    }
    for line in ((result.stdout or "") + (result.stderr or "")).splitlines():
        if not line.startswith("DEV_PLATFORM_TEST_AGGREGATE: "):
            continue
        try:
            aggregate = json.loads(line.split(": ", 1)[1])
        except (IndexError, json.JSONDecodeError):
            break
        failed = aggregate.get("failed_groups")
        if isinstance(failed, list) and all(isinstance(item, str) for item in failed):
            descriptor["failure_class"] = "test-group-failure"
            descriptor["failed_groups"] = sorted(failed)[:20]
        break
    return descriptor


def execute(
    root: Path,
    checks: list[dict[str, Any]],
    evidence_path: Path | None = None,
    managed_checkout: object | None = None,
    precheck: list[str] | None = None,
    base_contract: dict[str, str] | None = None,
) -> int:
    commands = commands_for(checks)
    if not commands:
        print("No applicable commands selected.")
        if evidence_path is not None:
            write_evidence(evidence_path, checks, selection_status(checks), [], "not-applicable", managed_checkout,
                           base_contract=base_contract)
        return 0

    from run_test_groups import resolve_jobs

    # One lease around the whole execution (affected-test precheck and command loop): the precheck's and the
    # commands' test-group runs are nested and reuse it, so a top-level run acquires exactly once.
    try:
        with machine_pool.lease(weight=resolve_jobs()[0], purpose="select_checks", bounded=True, root=root) as pool_lease:
            return _execute_commands(root, checks, commands, evidence_path, managed_checkout, precheck, pool_lease.fds,
                                     base_contract)
    except machine_pool.PoolError as exc:
        print(f"Machine pool blocked validation before any command started: {exc}", file=sys.stderr, flush=True)
        return 2


def _execute_commands(
    root: Path,
    checks: list[dict[str, Any]],
    commands: list[str],
    evidence_path: Path | None,
    managed_checkout: object | None,
    precheck: list[str] | None,
    pass_fds: tuple[int, ...],
    base_contract: dict[str, str] | None,
) -> int:
    records: list[dict[str, Any]] = []
    outcome = "success"
    precheck_record = None
    if precheck:
        precheck_record, result = run_precheck(root, precheck, pass_fds)
        precheck_record["outcome"] = precheck_outcome(result)
        if precheck_record["outcome"] == "unavailable":
            # A runner/configuration error leaves no feedback; the full set
            # still decides, so tooling trouble never blocks validation.
            print("Affected-test precheck was unavailable (exit %d); continuing with the full set." % result.returncode, flush=True)
    if precheck_record is not None and precheck_record["outcome"] == "failure":
        if evidence_path is not None:
            write_evidence(evidence_path, checks, selection_status(checks), records, "failure", managed_checkout, precheck_record,
                           base_contract=base_contract)
        descriptor = failure_descriptor(checks, precheck_record["command"], result)
        descriptor["phase"] = "affected-precheck"
        print("DEV_PLATFORM_CHECK_FAILURE: " + json.dumps(descriptor, ensure_ascii=False, sort_keys=True), flush=True)
        detail = diagnostic_tail((result.stdout or "") + (result.stderr or ""))
        if detail:
            print("DEV_PLATFORM_CHECK_DIAGNOSTIC:\n" + detail.rstrip(), flush=True)
        print("Affected-test precheck failed; the full validation set was not started.", flush=True)
        return result.returncode

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
            pass_fds=pass_fds,
        )
        evidence = command_result(command, result, time.monotonic() - started)
        records.append(evidence)
        print("DEV_PLATFORM_CHECK_RESULT: " + json.dumps(evidence, ensure_ascii=False), flush=True)
        if result.returncode != 0:
            outcome = "failure"
            if evidence_path is not None:
                write_evidence(evidence_path, checks, selection_status(checks), records, outcome, managed_checkout, precheck_record,
                           base_contract=base_contract)
            print("DEV_PLATFORM_CHECK_FAILURE: " + json.dumps(failure_descriptor(checks, command, result), ensure_ascii=False, sort_keys=True), flush=True)
            detail = diagnostic_tail((result.stdout or "") + (result.stderr or ""))
            if detail:
                print("DEV_PLATFORM_CHECK_DIAGNOSTIC:\n" + detail.rstrip(), flush=True)
            return result.returncode
    if evidence_path is not None:
        write_evidence(evidence_path, checks, selection_status(checks), records, outcome, managed_checkout, precheck_record,
                           base_contract=base_contract)
    return 0


def write_evidence(
    path: Path,
    checks: list[dict[str, Any]],
    status: dict[str, Any],
    records: list[dict[str, Any]],
    outcome: str,
    managed_checkout: object | None = None,
    precheck: dict[str, Any] | None = None,
    *,
    base_contract: dict[str, str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2 if managed_checkout is not None else 1,
        "selection": status,
        "outcome": outcome,
        "executed_commands": records,
        "selected_checks": checks,
    }
    if managed_checkout is not None:
        payload["managed_checkout"] = managed_checkout.evidence_payload()
        from task_content_identity import review_content_identity

        change = payload["managed_checkout"].get("change")
        if isinstance(change, str):
            payload["gate_task_content"] = review_content_identity(managed_checkout.worktree, change)
    if precheck is not None:
        payload["affected_precheck"] = precheck
    if base_contract is not None:
        # The head did not contain main: a reviewer of the evidence sees which contract passed it.
        payload["task_base"] = base_contract
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def coordinator_contract(root: Path) -> bool:
    """Whether the committed contract is the coordinator one; an undeterminable contract stops."""
    try:
        return lifecycle_mode(read_platform_config(root)) == "coordinator"
    except PlatformConfigError as exc:
        raise SystemExit(f"Task freshness gate blocked: lifecycle mode is not determinable: {exc}") from exc


def require_proven_base_contract(root: Path, args: argparse.Namespace) -> str:
    """Validate the bounded coordinator-finalization freshness contract before any command starts."""
    refused = "Proven-base freshness contract refused before any command started: "
    if not args.execute:
        raise SystemExit(refused + "--proven-base requires --execute")
    if args.evidence is not None:
        raise SystemExit(refused + "--proven-base never produces handoff evidence and is refused with --evidence")
    if args.contribution_base is not None:
        raise SystemExit(refused + "--proven-base is refused with --contribution-base")
    if args.mode == "protected-full":
        raise SystemExit(refused + "--proven-base is refused in protected-full mode")
    platform = read_platform_config(root)
    try:
        mode = lifecycle_mode(platform)
    except PlatformConfigError as exc:
        raise SystemExit(refused + f"lifecycle mode is not determinable: {exc}") from exc
    if mode != "coordinator":
        raise SystemExit(refused + f"--proven-base is accepted only in coordinator lifecycle mode (found {mode})")
    main_branch = platform.get("main_branch")
    if not isinstance(main_branch, str) or not main_branch:
        raise SystemExit(refused + "main_branch must be a non-empty string in .dev-platform.toml")
    try:
        return require_proven_task_base(root, args.proven_base, "origin", main_branch)
    except TaskFreshnessError as exc:
        raise SystemExit(refused + str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Select conservative project checks from changed files.")
    parser.add_argument("--base", help="Git base ref, e.g. origin/main")
    parser.add_argument(
        "--contribution-base",
        metavar="SHA",
        help=(
            "Requirement contribution candidate: its freshness is the exact recorded integration "
            "base it contributes onto (HEAD must contain this commit), not current main. Current "
            "main is validated later by the Requirement composition candidate."
        ),
    )
    parser.add_argument(
        "--proven-base",
        metavar="SHA",
        help=(
            "Coordinator finalization only: HEAD must fork from exactly this commit on origin/<main> "
            "(merge-base(HEAD, origin/<main>) == SHA) instead of containing current main. Requires "
            "--execute in coordinator lifecycle mode; refused with --evidence, --contribution-base "
            "and protected-full."
        ),
    )
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--evidence", help="Write the selected and actually executed command evidence to this JSON file.")
    parser.add_argument("--mode", choices=("local-affected", "protected-full"), default="local-affected")
    parser.add_argument("--protected-full", action="store_true", help="Alias for --mode protected-full.")
    parser.add_argument("--full", action="store_true", help="Deprecated alias for --mode protected-full.")
    parser.add_argument(
        "--declare-behavior-change",
        metavar="RUNTIME",
        help=(
            "Declare that an instruction/prompt-surface change intentionally changes agent "
            "behavior for RUNTIME. The configured behavioral evidence command(s) for RUNTIME "
            "are executed as part of this invocation; a declaration with no configured, "
            "executed, successful command falls back to full validation. A model's own report "
            "that the change is safe is never accepted in place of an executed command."
        ),
    )
    args = parser.parse_args()

    if args.protected_full or args.full:
        args.mode = "protected-full"

    root = current_worktree_root()
    proven_description = require_proven_base_contract(root, args) if args.proven_base is not None else None
    config = load_config(root)
    paths = [] if args.mode == "protected-full" else changed_files(root, args.base, args.changed_file)
    checks = (
        full_checks(config)
        if args.mode == "protected-full"
        else select(config, paths, declare_behavior_change=args.declare_behavior_change)
    )
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
        evidence_path = (root / args.evidence).resolve() if args.evidence else None
        # Managed task state makes this a protected evidence-producing path,
        # even if the selected group is narrower than protected-full.  The
        # preflight deliberately precedes freshness/scope checks and command
        # execution, so a reset cwd cannot create usable green evidence.
        try:
            managed_checkout = require_managed_checkout_identity(root)
        except ManagedTaskError as exc:
            raise SystemExit("Managed checkout identity gate blocked validation before any expensive command started: " + str(exc)) from exc
        base_contract = None
        # Narrow mapped selections that produce coordinator handoff evidence need the
        # same currency classification as full selections.
        handoff_evidence = bool(checks) and evidence_path is not None and args.mode == "local-affected" and coordinator_contract(root)
        if harness == "platform" and (requires_task_freshness(checks) or handoff_evidence):
            if proven_description is not None:
                print(
                    "Task freshness gate passed (coordinator-finalization proven-base contract): "
                    f"proven base {args.proven_base} is the {proven_description}."
                )
            elif args.contribution_base:
                if run_git(["merge-base", "--is-ancestor", args.contribution_base, "HEAD"], cwd=root, check=False).returncode:
                    raise SystemExit(
                        "Task freshness gate blocked full/protected validation before any expensive command started: "
                        f"HEAD does not contain its exact contribution base {args.contribution_base}"
                    )
                print(f"Task freshness gate passed: HEAD contains its exact contribution base ({args.contribution_base}).")
            elif evidence_path is not None and args.mode == "local-affected" and coordinator_contract(root):
                # Developer handoff evidence: a coordinator candidate behind a disjoint,
                # cleanly mergeable main passes; the queue merges main and gates on the
                # integrated head. Any other head keeps the fresh-base rule.
                main_branch = read_platform_config(root).get("main_branch")
                if not isinstance(main_branch, str) or not main_branch:
                    raise SystemExit("Task freshness gate blocked: main_branch must be a non-empty string in .dev-platform.toml")
                try:
                    currency = require_handoff_task_base(root, "origin", main_branch)
                except TaskFreshnessError as exc:
                    raise SystemExit(
                        "Task freshness gate blocked full/protected validation before any expensive command started: " + str(exc)
                    ) from exc
                if currency.state == TASK_BASE_FRESH:
                    print(f"Task freshness gate passed: HEAD contains freshly observed origin/{main_branch} ({currency.main}).")
                else:
                    base_contract = currency.evidence()
                    print(
                        "Task freshness gate passed (coordinator-candidate behind-disjoint contract): "
                        f"{currency.describe('origin/' + main_branch)}; merge base {currency.base}."
                    )
            else:
                try:
                    observed = require_fresh_task_base(root, "origin", str(read_platform_config(root).get("main_branch", "main")))
                except TaskFreshnessError as exc:
                    raise SystemExit(
                        "Task freshness gate blocked full/protected validation before any expensive command started: " + str(exc)
                    ) from exc
                print(f"Task freshness gate passed: HEAD contains freshly observed origin/{read_platform_config(root).get('main_branch', 'main')} ({observed}).")
            branch = run_git(["branch", "--show-current"], cwd=root).stdout.strip()
            try:
                enforce_scope_gate(main_root(), root, branch)
            except HardScopeOverlap as exc:
                block_for_scope_conflict(root, str(exc))
                raise SystemExit(str(exc)) from exc
        return execute(root, checks, evidence_path, managed_checkout, precheck_paths(config, checks), base_contract)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
