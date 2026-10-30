"""One cheap preflight over the conditions that can stop an expensive lifecycle command later.

``select_checks.py --execute`` and ``finish_task.py`` run :func:`run_preflight` before the first
expensive operation. Each condition calls the function the corresponding gate uses, so a gate and its
preflight cannot answer differently. A condition reports ``passed``, ``repaired`` or ``not-applicable``
with the fact that makes it so, or refuses; a condition that cannot be evaluated refuses. Every
blocking gate in ``dev-platform/blocking-gates.toml`` names the condition that fronts it
(``preflight``) or states why none can (``no_preflight``).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PASSED = "passed"
REPAIRED = "repaired"
NOT_APPLICABLE = "not-applicable"
REFUSED = "refused"
OUTPUT_PREFIX = "DEV_PLATFORM_PREFLIGHT: "
DIAGNOSTIC_TAIL = 1500


class PreflightRefusal(Exception):
    """A condition is violated; the message names the condition and the command that repairs it."""


@dataclass(frozen=True)
class ConditionResult:
    state: str
    detail: str


@dataclass(frozen=True)
class PreflightContext:
    """What a condition needs. ``scope_gate_waiver``/``task_base_waiver`` carry the declared reason a
    condition does not apply (a disposable CI checkout, a proven-base finalization); ``None`` means it applies."""

    root: Path
    integration: Path
    branch: str
    entry: str
    scope_gate_waiver: str | None = None
    task_base_waiver: str | None = None


@dataclass(frozen=True)
class Condition:
    id: str
    gates: tuple[str, ...]
    check: Callable[[PreflightContext], ConditionResult]


def _gate_text(exc: BaseException) -> str:
    return str(exc.code) if isinstance(exc, SystemExit) else str(exc)


def summarize_paths(paths, limit: int = 5) -> str:
    """The first ``limit`` distinct paths, then the count of the rest (a fresh checkout repairs dozens)."""
    unique = list(dict.fromkeys(str(path) for path in paths))
    shown = ", ".join(unique[:limit])
    return shown + (f" and {len(unique) - limit} more" if len(unique) > limit else "")


def check_shared_workspace(ctx: PreflightContext) -> ConditionResult:
    import shared_workspace

    if not shared_workspace.shared_workspace_applicable(ctx.root):
        return ConditionResult(NOT_APPLICABLE, "no shared POSIX workspace contract here (disposable or single-user checkout)")
    try:
        repaired = shared_workspace.preflight_with_report(ctx.root)
        if ctx.integration.resolve() != ctx.root.resolve():
            repaired += shared_workspace.preflight_with_report(ctx.integration)
    except shared_workspace.SharedWorkspaceError as exc:
        raise PreflightRefusal(str(exc)) from exc
    if repaired:
        return ConditionResult(REPAIRED, f"repaired {len(set(repaired))} path(s) owned by this account: " + summarize_paths(repaired))
    return ConditionResult(PASSED, "registered paths conform to the shared group contract")


def check_board_claim_and_scope(ctx: PreflightContext) -> ConditionResult:
    import agent_board
    from _platform_common import read_platform_config

    if ctx.scope_gate_waiver is not None:
        return ConditionResult(NOT_APPLICABLE, ctx.scope_gate_waiver)
    if not agent_board.scope_gate_required(read_platform_config(ctx.root)):
        return ConditionResult(NOT_APPLICABLE, "[capabilities] agent_board is false")
    try:
        agent_board.enforce_scope_gate(ctx.integration, ctx.root, ctx.branch)
    except agent_board.HardScopeOverlap as exc:
        from managed_project_status import block_for_scope_conflict

        block_for_scope_conflict(ctx.root, str(exc))
        raise PreflightRefusal(str(exc)) from exc
    except SystemExit as exc:
        detail = _gate_text(exc)
        if "has no claim for worktree" in detail:
            detail += (f"\nrestore the claim: python3 scripts/agent_board.py start --task \"<task>\" --branch {ctx.branch} "
                       f"--worktree {ctx.root}")
        raise PreflightRefusal(detail) from exc
    return ConditionResult(PASSED, f"claim for {ctx.branch} found; no unacknowledged hard scope overlap")


def check_task_base(ctx: PreflightContext) -> ConditionResult:
    import task_reconciliation
    from _platform_common import RECONCILE_COMMAND, TaskFreshnessError

    if ctx.task_base_waiver is not None:
        return ConditionResult(NOT_APPLICABLE, ctx.task_base_waiver)
    try:
        freshness = task_reconciliation.observe_candidate(ctx.root)
    except TaskFreshnessError as exc:
        raise PreflightRefusal(f"task freshness cannot be determined: {exc}") from exc
    if freshness.reconcile_required:
        detail = f" ({freshness.detail})" if freshness.detail else ""
        raise PreflightRefusal(
            f"{ctx.branch} is {freshness.state} relative to freshly observed main{detail}. Reconcile: {RECONCILE_COMMAND}"
        )
    return ConditionResult(PASSED, f"task is {freshness.state} relative to main ({freshness.authoritative_sha})")


def load_checks_config(root: Path) -> dict:
    """The project's check configuration (``paths.checks``); a missing file is an explicit error."""
    import tomllib

    from _platform_common import read_platform_config

    path = root / read_platform_config(root)["paths"]["checks"]
    if not path.exists():
        raise SystemExit(f"Check configuration not found: {path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def configured_preflight_commands(root: Path) -> tuple[list[str] | None, str]:
    """``(commands, reason)``: the configured project cheap gates, or ``None`` with the stated reason they are not configured."""
    from _platform_common import read_platform_config

    path = root / read_platform_config(root)["paths"]["checks"]
    if not path.exists():
        return None, f"the check configuration {path.name} is not present, so no preflight_commands are configured"
    commands = load_checks_config(root).get("settings", {}).get("preflight_commands")
    if commands is None:
        return None, "settings.preflight_commands is not configured"
    return commands, ""


def check_project_cheap_gates(ctx: PreflightContext) -> ConditionResult:
    commands, reason = configured_preflight_commands(ctx.root)
    if commands is None:
        return ConditionResult(NOT_APPLICABLE, reason)
    if not isinstance(commands, list) or not all(isinstance(item, str) and item.strip() for item in commands):
        raise PreflightRefusal("settings.preflight_commands must be a list of non-empty command strings")
    for command in commands:
        result = subprocess.run(command, cwd=ctx.root, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            tail = ((result.stdout or "") + (result.stderr or "")).strip()[-DIAGNOSTIC_TAIL:]
            raise PreflightRefusal(f"project cheap gate failed (exit {result.returncode}): {command}\n{tail}")
    return ConditionResult(PASSED, f"{len(commands)} project cheap gate command(s) passed")


CONDITIONS: tuple[Condition, ...] = (
    Condition("shared-workspace", ("shared-workspace-admission",), check_shared_workspace),
    Condition("board-claim-and-scope", ("scope-gate-unavailable", "scope-overlap"), check_board_claim_and_scope),
    Condition("task-base", ("task-freshness",), check_task_base),
    Condition("project-cheap-gates", (), check_project_cheap_gates),
)
CONDITION_IDS = tuple(condition.id for condition in CONDITIONS)


def run_preflight(ctx: PreflightContext, *, conditions: tuple[Condition, ...] = CONDITIONS) -> list[tuple[str, ConditionResult]]:
    """Evaluate every condition, print each result, and raise one ``SystemExit`` naming all refusals."""
    results: list[tuple[str, ConditionResult]] = []
    refusals: list[str] = []
    for condition in conditions:
        try:
            result = condition.check(ctx)
        except PreflightRefusal as exc:
            result = ConditionResult(REFUSED, str(exc))
            refusals.append(f"[{condition.id}] {exc}")
        except (Exception, SystemExit) as exc:
            # A condition that cannot be evaluated refuses; it must not hide the other conditions' results.
            detail = f"cannot be evaluated: {exc if str(exc) else type(exc).__name__}"
            result = ConditionResult(REFUSED, detail)
            refusals.append(f"[{condition.id}] {detail}")
        results.append((condition.id, result))
        first = result.detail.splitlines()[0] if result.detail else ""
        print(f"{OUTPUT_PREFIX}{condition.id}: {result.state}: {first}", flush=True)
    if refusals:
        raise SystemExit(
            f"Lifecycle preflight refused {ctx.entry} before any expensive operation "
            f"({len(refusals)} condition(s) violated):\n" + "\n".join(refusals)
        )
    return results


if __name__ == "__main__":
    from _platform_common import current_worktree_root, main_root, run_git

    root = current_worktree_root()
    run_preflight(PreflightContext(root, main_root(), run_git(["branch", "--show-current"], cwd=root).stdout.strip(), "manual"))
