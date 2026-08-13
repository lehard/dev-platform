#!/usr/bin/env python3
"""Provider-local executor routing for managed OpenSpec tasks.

The strong interactive agent remains the supervisor: it performs the semantic
preflight, records a bounded profile decision here, delegates through the
native provider surface, and evaluates the result. This module deliberately
does not decide from diff size or silently launch a cheaper writer. It makes
the decision, hand-off, escalation, and post-check evidence explicit.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, main_root, read_platform_config, utc_now
from delegated_write_guard import (
    EnforcementTier,
    GuardedChildError,
    build_codex_argv,
    determine_claude_tier,
    determine_codex_tier,
    run_observed_delegation,
)
from delegation_containment import (
    ContainmentError,
    GitSnapshot,
    PathState,
    check_containment,
    format_violation_message,
    record_containment_friction,
    resolve_assigned_worktree,
    snapshot,
)
from start_tier_routing import tier_to_profile


PROFILES = ("routine", "standard", "complex")
PROVIDERS = ("codex", "claude")
DEFAULT_MODELS = {
    "codex": {"routine": "gpt-5.6-terra", "standard": "gpt-5.6-terra", "complex": "gpt-5.6-sol"},
    "claude": {"routine": "haiku", "standard": "sonnet", "complex": "opus"},
}


class RoutingError(RuntimeError):
    """An actionable routing/preflight error."""


@dataclass(frozen=True)
class Route:
    source_issue: str
    change: str
    task_worktree: str
    integration_root: str
    provider: str
    profile: str
    executor_model: str
    rationale: str
    evidence: tuple[str, ...]
    prepared_at: str
    pre_snapshot: dict[str, Any]
    execution: dict[str, Any] | None = None
    escalations: tuple[dict[str, str], ...] = ()
    # The provider-neutral start tier authored with the managed task (`R1`,
    # `R2` or `R3`), when a routing receipt is available; `None` for a
    # legacy managed package authored before this rubric existed, in which
    # case an explicit --profile is required instead of tier derivation.
    start_tier: str | None = None
    # "confirmed": the freshness check found no new hard trigger and kept the
    # authored tier/profile. "escalated": execution discovered new evidence
    # and escalate() promoted the route to the strong profile.
    freshness: str = "confirmed"
    # Bounded, truthful execution provenance (task 6.2-6.6 of
    # adopt-gh-aw-process-automation). Reuses this existing routing record
    # instead of a second run/trace database. ``supervisor`` is the
    # policy-selected identity of the strong parent that recorded this route;
    # ``execution["participant"]`` (set only once a child actually ran) is the
    # delegated executor's provenance. Both distinguish selected/configured
    # from runtime-confirmed values and use "unknown" rather than a guess.
    supervisor: dict[str, Any] = field(default_factory=dict)


def _snapshot_to_dict(value: GitSnapshot) -> dict[str, Any]:
    return {"head": value.head, "paths": {path: {"status": state.status, "fingerprint": state.fingerprint, "orig_path": state.orig_path} for path, state in value.paths.items()}}


def _snapshot_from_dict(value: dict[str, Any]) -> GitSnapshot:
    paths = value.get("paths")
    if not isinstance(value.get("head"), str) or not isinstance(paths, dict):
        raise RoutingError("routing record has no readable pre-delegation containment snapshot")
    try:
        return GitSnapshot(head=value["head"], paths={str(path): PathState(status=str(state["status"]), fingerprint=str(state["fingerprint"]), orig_path=state.get("orig_path")) for path, state in paths.items() if isinstance(state, dict)})
    except (KeyError, TypeError) as exc:
        raise RoutingError("routing record has an invalid containment snapshot") from exc


def _managed_provenance(root: Path) -> dict[str, Any]:
    candidates = list((root / "openspec" / "changes").glob("*/.managed-task.json"))
    if len(candidates) != 1:
        raise RoutingError(f"model routing requires exactly one materialized managed OpenSpec change in this task checkout; found {len(candidates)}")
    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
        source_issue, change = payload["source_issue"], payload["change"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise RoutingError(f"cannot read managed-task provenance at {candidates[0]}") from exc
    if not isinstance(source_issue, str) or not isinstance(change, str):
        raise RoutingError("managed-task provenance has invalid source_issue/change values")
    return payload


def _managed_identity(root: Path) -> tuple[str, str]:
    payload = _managed_provenance(root)
    return payload["source_issue"], payload["change"]


def _authored_start_tier(root: Path) -> str | None:
    """The provider-neutral start tier authored with this managed task, if any.

    Absent for a legacy managed package authored before this rubric existed;
    callers fall back to requiring an explicit --profile in that case.
    """
    receipt = _managed_provenance(root).get("routing_receipt")
    if not isinstance(receipt, dict):
        return None
    tier = receipt.get("recommended_start_tier")
    return tier if isinstance(tier, str) else None


def _record_path(root: Path, change: str) -> Path:
    return root / ".claude" / "model-routing" / f"{change}.json"


def _model_for(config: dict[str, Any], provider: str, profile: str) -> str:
    routing = config.get("model_routing", {})
    provider_policy = routing.get(provider, {}) if isinstance(routing, dict) else {}
    model = provider_policy.get(f"{profile}_model") if isinstance(provider_policy, dict) else None
    return model.strip() if isinstance(model, str) and model.strip() else DEFAULT_MODELS[provider][profile]


# Provenance source/status vocabulary. Exactly the three states the spec asks
# for (openspec/changes/adopt-gh-aw-process-automation/specs/model-routing) --
# no richer taxonomy, so a missing/unconfirmable value degrades to "unknown"
# rather than inventing a fourth state.
SOURCE_SELECTED = "selected"
SOURCE_RUNTIME_CONFIRMED = "runtime-confirmed"
SOURCE_UNKNOWN = "unknown"


def _model_provenance(model: str | None, source: str) -> dict[str, Any]:
    return {"value": model, "source": source}


def _effort_provenance(value: str | None, source: str) -> dict[str, Any]:
    return {"value": value, "source": source}


def _supervisor_provenance(config: dict[str, Any], provider: str) -> dict[str, Any]:
    """The policy-selected identity of the strong parent recording this route.

    There is no supported runtime surface (Codex or Claude Code) that lets a
    plain script introspect "which model am I actually running as" -- only
    the caller's own harness-provided session context could state that, and
    free-form self-identification is explicitly not authoritative evidence
    (see the model-routing spec). So the supervisor's own model is recorded
    as policy-selected, exactly like an executor's, never runtime-confirmed.
    """
    return {
        "role": "supervisor",
        "provider": provider,
        "model": _model_provenance(_model_for(config, provider, "complex"), SOURCE_SELECTED),
    }


def _participant(
    *,
    role: str,
    provider: str,
    profile: str,
    model: str,
    effort_value: str | None,
    effort_source: str,
    execution_id: str | None,
    execution_id_kind: str | None,
) -> dict[str, Any]:
    """Bounded provenance for one actually-executed participant.

    Only called once launch is confirmed; a merely prepared/unrun route must
    never be represented as an executed participant (model-routing spec,
    "Preferred delegated executor is unavailable").
    """
    return {
        "role": role,
        "provider": provider,
        "profile": profile,
        "model": _model_provenance(model, SOURCE_SELECTED),
        "reasoning_effort": _effort_provenance(effort_value, effort_source),
        "execution_id": {"value": execution_id, "kind": execution_id_kind},
    }


def _read_route(root: Path) -> tuple[Route, Path]:
    source_issue, change = _managed_identity(root)
    path = _record_path(root, change)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        execution = payload.get("execution")
        supervisor = payload.get("supervisor")
        route = Route(source_issue=payload["source_issue"], change=payload["change"], task_worktree=payload["task_worktree"], integration_root=payload["integration_root"], provider=payload["provider"], profile=payload["profile"], executor_model=payload["executor_model"], rationale=payload["rationale"], evidence=tuple(payload.get("evidence", [])), prepared_at=payload["prepared_at"], pre_snapshot=payload["pre_snapshot"], execution=execution if isinstance(execution, dict) else None, escalations=tuple(payload.get("escalations", [])), start_tier=payload.get("start_tier"), freshness=payload.get("freshness", "confirmed"), supervisor=supervisor if isinstance(supervisor, dict) else {})
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RoutingError(f"no readable routing record for managed change {change}; run prepare first") from exc
    if route.source_issue != source_issue or route.change != change:
        raise RoutingError("routing record provenance does not match the materialized managed task")
    return route, path


def _write_route(path: Path, route: Route) -> None:
    atomic_write_text(path, json.dumps(asdict(route), indent=2, sort_keys=True) + "\n")


def prepare(root: Path, *, provider: str, profile: str | None, rationale: str, evidence: list[str]) -> Route:
    """Record a route: confirm the authored start tier, or accept an explicit override.

    When ``profile`` is omitted, this is the bounded execution-time freshness
    check -- it confirms the tier already recommended at managed-task
    authoring (mapped to the existing profile vocabulary) rather than
    requiring a strong parent to redo full semantic routing. A managed
    package authored before the start-tier rubric existed has no receipt to
    confirm, so an explicit ``profile`` is still required for it.
    """
    if provider not in PROVIDERS:
        raise RoutingError("unknown provider or execution profile")
    start_tier = _authored_start_tier(root)
    if profile is None:
        if start_tier is None:
            raise RoutingError(
                "no authored start-tier routing receipt is available for this managed task; pass --profile explicitly"
            )
        profile = tier_to_profile(start_tier)
    if profile not in PROFILES:
        raise RoutingError("unknown provider or execution profile")
    if not rationale.strip():
        raise RoutingError("semantic routing preflight requires a non-empty rationale")
    source_issue, change = _managed_identity(root)
    integration = main_root().resolve()
    assigned = resolve_assigned_worktree(integration, root)
    config = read_platform_config(root)
    route = Route(source_issue=source_issue, change=change, task_worktree=str(assigned), integration_root=str(integration), provider=provider, profile=profile, executor_model=_model_for(config, provider, profile), rationale=rationale.strip(), evidence=tuple(evidence), prepared_at=utc_now(), pre_snapshot=_snapshot_to_dict(snapshot(integration)), start_tier=start_tier, freshness="confirmed", supervisor=_supervisor_provenance(config, provider))
    _write_route(_record_path(root, change), route)
    return route


def escalation_context(route: Route) -> dict[str, Any]:
    return {"source_issue": route.source_issue, "change": route.change, "task_worktree": route.task_worktree, "profile": route.profile, "executor_model": route.executor_model, "rationale": route.rationale, "evidence": list(route.evidence), "escalations": list(route.escalations), "start_tier": route.start_tier, "freshness": route.freshness, "required_parent_actions": ["Review the child diff and all required check evidence in the assigned task worktree.", "Run postcheck after native Claude worktree delegation before reporting containment success.", "Escalate rather than broaden routine/standard work on material contract conflict, cross-cutting scope, low confidence, or bounded substantive verification failures."]}


def escalate(root: Path, reason: str) -> Route:
    """Promote a route to the strong profile: the freshness-check escalate path.

    Used both for classic under-routing escalation and for a bounded
    execution-time freshness check that discovers a new hard trigger absent
    from the authored recommendation. Either way this only rewrites the
    routing record; the canonical OpenSpec, assigned worktree/diff and prior
    findings/check evidence are untouched.
    """
    route, path = _read_route(root)
    if route.profile == "complex":
        raise RoutingError("the route is already complex; retain the strong parent instead of escalating again")
    if not reason.strip():
        raise RoutingError("escalation requires a concrete reason")
    next_route = Route(**{**asdict(route), "profile": "complex", "executor_model": _model_for(read_platform_config(root), route.provider, "complex"), "freshness": "escalated", "escalations": route.escalations + ({"at": utc_now(), "from": route.profile, "reason": reason.strip()},)})
    _write_route(path, next_route)
    return next_route


def codex_argv(route: Route, prompt: str, codex_bin: str | None = None) -> tuple[list[str], str]:
    if route.provider != "codex":
        raise RoutingError("the prepared route is not a Codex route")
    decision = determine_codex_tier(codex_bin=codex_bin, integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree))
    if decision.tier is not EnforcementTier.HARD:
        raise RoutingError("native Codex containment is not provable for this route; retain execution on the parent or use an explicitly reviewed fallback: " + decision.detail)
    # --json is the documented structured-event stream (verified at
    # implementation preflight: codex exec --json emits a "thread.started"
    # event carrying a real runtime thread_id). It is the only currently
    # supported source of a confirmed bounded execution identifier; no
    # documented surface confirms effective model/reasoning-effort, so those
    # remain policy-selected only (see _participant call sites).
    return build_codex_argv(codex_bin or "codex", Path(route.task_worktree), decision.tier, ["--json", "--model", route.executor_model, prompt]), decision.mechanism


def _codex_thread_id_from_line(line: str) -> str | None:
    if not line.lstrip().startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if isinstance(event, dict) and event.get("type") == "thread.started":
        thread_id = event.get("thread_id")
        if isinstance(thread_id, str) and thread_id:
            return thread_id
    return None


def run_codex(route: Route, prompt: str, codex_bin: str | None = None) -> dict[str, Any]:
    argv, mechanism = codex_argv(route, prompt, codex_bin)
    # Codex workspace-write is the prevention layer. The legacy helper only
    # validates the assignment and observes/records the required post-check.
    decision = determine_codex_tier(codex_bin=codex_bin, require_hard=True, integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree))
    captured: dict[str, str | None] = {"thread_id": None}

    def _on_line(line: str) -> None:
        print(line)
        thread_id = _codex_thread_id_from_line(line)
        if thread_id is not None:
            captured["thread_id"] = thread_id

    abnormal_error: str | None = None
    try:
        result = run_observed_delegation(
            integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree),
            argv=argv, tier_decision=decision, task=route.source_issue, stdout_line_hook=_on_line,
        )
    except GuardedChildError as exc:
        # The guard has already attempted process-tree cleanup and always ran
        # the containment comparison. Persist that known failure instead of
        # letting a parent-side exception make the route look clean/unrun.
        result = exc.result
        abnormal_error = str(exc)
    output = {
        "mechanism": mechanism,
        "launched": result.launched,
        "returncode": result.returncode,
        "violation": result.violation,
        "writer_state": getattr(result, "writer_state", "released"),
    }
    if abnormal_error is not None:
        output["outcome"] = "abnormal"
        output["error"] = abnormal_error
    elif result.returncode not in (0, None) or result.violation:
        output["outcome"] = "failed"
    else:
        output["outcome"] = "completed"
    if result.launched:
        # A route that was merely prepared must never look executed; only
        # attach participant provenance once the child actually launched.
        output["participant"] = _participant(
            role="executor", provider="codex", profile=route.profile, model=route.executor_model,
            effort_value=None, effort_source=SOURCE_UNKNOWN,
            execution_id=captured["thread_id"], execution_id_kind="codex-thread" if captured["thread_id"] else None,
        )
    return output


def _failed_codex_execution(execution: dict[str, Any]) -> bool:
    return execution.get("outcome") in {"abnormal", "failed"} or execution.get("writer_state") == "ambiguous"


def dispatch_codex(
    root: Path,
    *,
    profile: str | None,
    rationale: str,
    evidence: list[str],
    prompt: str,
    codex_bin: str | None = None,
) -> dict[str, Any]:
    """Atomically record a Codex route and launch only lower-cost profiles.

    The supervisor supplies the bounded semantic assessment.  Keeping prepare
    and the native child launch in one operation prevents dogfood guidance from
    degrading into a recorded-but-never-executed routine/standard route.
    """
    route = prepare(root, provider="codex", profile=profile, rationale=rationale, evidence=evidence)
    output: dict[str, Any] = {"route": asdict(route), "delegated": False}
    if route.profile == "complex":
        output["reason"] = "complex profile remains on the strong Codex supervisor"
        return output
    execution = run_codex(route, prompt, codex_bin)
    route = Route(**{**asdict(route), "execution": execution})
    _write_route(_record_path(root, route.change), route)
    output["route"] = asdict(route)
    output["delegated"] = True
    output["execution"] = execution
    if _failed_codex_execution(execution):
        raise RoutingError(
            "delegated Codex execution did not complete cleanly; its real outcome was persisted in routing provenance"
        )
    return output


def claude_agent(route: Route) -> dict[str, Any]:
    """Emit the native Agent-tool call the supervisor must actually invoke.

    Deliberately has no `isolation` key. Claude Code's `isolation: "worktree"`
    creates a fresh worktree off the platform's main branch HEAD -- it cannot
    see the materialized-but-uncommitted managed OpenSpec/task state that
    exists in the assigned task worktree at routing-preflight time. The
    supervisor must invoke this in place, with its own working directory
    already the assigned task worktree, so the child shares that exact
    filesystem/branch/uncommitted state instead of a divergent empty copy.

    Deliberately has no `effort`/`maxTurns` key either: verified at
    implementation preflight against the currently supported Agent tool,
    neither is an accepted parameter of that tool today (only description,
    isolation, model, prompt, run_in_background, subagent_type are). Emitting
    them would imitate a selection the runtime cannot actually honor, so
    reasoning effort for a Claude child is recorded as unknown rather than
    fabricated as selected/configured (see _participant call sites).
    """
    if route.provider != "claude":
        raise RoutingError("the prepared route is not a Claude route")
    return {"description": "Managed task executor; use only after supervisor routing preflight.", "model": route.executor_model, "prompt": "Work only in the current working directory, which is already the assigned task worktree for this managed dev-platform task -- do not request isolation or create a separate worktree. Preserve the canonical OpenSpec and return the exact diff, checks run, uncertainty, and any escalation trigger to the supervisor. Managed source: " + route.source_issue + "; change: " + route.change + "; assigned worktree: " + route.task_worktree + "."}


def prepare_claude_handoff(root: Path, *, profile: str | None, rationale: str, evidence: list[str]) -> dict[str, Any]:
    """Atomically record a Claude route and, for lower-cost profiles, the hand-off to invoke.

    A native Claude Code subagent can only be launched by the supervisor's own
    Agent-tool call -- this module cannot spawn one as a subprocess the way
    dispatch_codex spawns Codex. This records the route, performs the
    detection-only dirty-start refusal up front, and returns the exact
    hand-off spec; the supervisor must actually invoke it, then call
    record_claude_execution with the result before finish's routing gate
    accepts a routine/standard Claude route.
    """
    route = prepare(root, provider="claude", profile=profile, rationale=rationale, evidence=evidence)
    output: dict[str, Any] = {"route": asdict(route), "delegated": False}
    if route.profile == "complex":
        output["reason"] = "complex profile remains on the strong Claude supervisor"
        return output
    tier_decision = determine_claude_tier(shell_enabled=True)
    if tier_decision.tier is EnforcementTier.DETECTION_ONLY and route.pre_snapshot.get("paths"):
        dirty = ", ".join(sorted(route.pre_snapshot["paths"]))
        raise RoutingError(
            f"detection-only Claude delegation ({tier_decision.mechanism}) refused to start: integration "
            f"checkout already has uncommitted state ({dirty}). A detection-only writer cannot prove it did "
            "not touch pre-existing dirty state, so it must not launch until integration is clean."
        )
    output["handoff"] = claude_agent(route)
    output["tier"] = tier_decision.tier.value
    output["mechanism"] = tier_decision.mechanism
    output["delegated"] = "pending_supervisor_invocation"
    return output


def record_claude_execution(root: Path, *, agent_id: str, summary: str | None = None) -> dict[str, Any]:
    """Record that the supervisor actually invoked the emitted Claude hand-off.

    Must run after the real Agent-tool call returns. Runs the mandatory
    content-aware postcheck (fails closed on any integration/main mutation)
    and persists the resulting execution evidence so finish's routing gate
    can verify a routine/standard route was truly executed, not just
    recorded.
    """
    route, path = _read_route(root)
    if route.provider != "claude":
        raise RoutingError("the prepared route is not a Claude route")
    if route.profile == "complex":
        raise RoutingError("complex Claude routes are not delegated; there is no execution to record")
    if not agent_id.strip():
        raise RoutingError("recording Claude execution requires a non-empty agent id")
    tier_decision = determine_claude_tier(shell_enabled=True)
    check = postcheck(route)
    execution = {
        "launched": True,
        "agent_id": agent_id.strip(),
        "summary": summary.strip() if summary else None,
        "tier": tier_decision.tier.value,
        "mechanism": tier_decision.mechanism,
        "postcheck": check,
        "recorded_at": utc_now(),
        # A real Agent-tool invocation returned, so this participant actually
        # executed. Model is what the supervisor selected via claude_agent();
        # reasoning effort has no supported selection/confirmation surface on
        # the current Agent tool (see claude_agent docstring), so it stays
        # unknown rather than reusing the discarded profile-implied guess.
        "participant": _participant(
            role="executor", provider="claude", profile=route.profile, model=route.executor_model,
            effort_value=None, effort_source=SOURCE_UNKNOWN,
            execution_id=agent_id.strip(), execution_id_kind="claude-agent-id",
        ),
    }
    next_route = Route(**{**asdict(route), "execution": execution})
    _write_route(path, next_route)
    return execution


def postcheck(route: Route) -> dict[str, Any]:
    result = check_containment(_snapshot_from_dict(route.pre_snapshot), snapshot(Path(route.integration_root)))
    if result.violated:
        assigned = Path(route.task_worktree)
        record_containment_friction(Path(route.integration_root), assigned, result, task=route.source_issue, enforcement_tier="native-worktree")
        raise RoutingError(format_violation_message(assigned, result))
    return {"containment": "clean", "pre_existing_changes": list(result.pre_existing_changes)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record, hand off, escalate and verify provider-local model routing.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="record the supervisor's bounded semantic routing decision")
    prepare_parser.add_argument("--provider", choices=PROVIDERS, required=True)
    prepare_parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=None,
        help="omit to confirm the tier already authored with the managed task (bounded freshness check)",
    )
    prepare_parser.add_argument("--rationale", required=True)
    prepare_parser.add_argument("--evidence", action="append", default=[])
    subparsers.add_parser("context", help="emit bounded executor/supervisor hand-off context")
    escalate_parser = subparsers.add_parser("escalate", help="promote routine/standard work to the strong profile")
    escalate_parser.add_argument("--reason", required=True)
    codex_parser = subparsers.add_parser("codex-argv", help="emit a native-sandbox Codex invocation without launching it")
    codex_parser.add_argument("--prompt", required=True)
    codex_parser.add_argument("--codex-bin")
    run_parser = subparsers.add_parser("run-codex", help="launch a prepared Codex route with native containment and post-check")
    run_parser.add_argument("--prompt", required=True)
    run_parser.add_argument("--codex-bin")
    dispatch_parser = subparsers.add_parser(
        "dispatch-codex",
        help="record a Codex route and launch routine/standard work through the native child path",
    )
    dispatch_parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=None,
        help="omit to confirm the tier already authored with the managed task (bounded freshness check)",
    )
    dispatch_parser.add_argument("--rationale", required=True)
    dispatch_parser.add_argument("--evidence", action="append", default=[])
    dispatch_parser.add_argument("--prompt", required=True)
    dispatch_parser.add_argument("--codex-bin")
    subparsers.add_parser("claude-agent", help="emit a native Claude Code worktree-agent definition")
    dispatch_claude_parser = subparsers.add_parser(
        "dispatch-claude",
        help="record a Claude route and, for routine/standard, emit the in-place native subagent hand-off",
    )
    dispatch_claude_parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=None,
        help="omit to confirm the tier already authored with the managed task (bounded freshness check)",
    )
    dispatch_claude_parser.add_argument("--rationale", required=True)
    dispatch_claude_parser.add_argument("--evidence", action="append", default=[])
    record_claude_parser = subparsers.add_parser(
        "record-claude-execution",
        help="record that the supervisor actually invoked the Claude hand-off, and verify containment",
    )
    record_claude_parser.add_argument("--agent-id", required=True)
    record_claude_parser.add_argument("--summary")
    subparsers.add_parser("postcheck", help="verify the prepared native worktree route did not mutate integration")
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "prepare": output: Any = asdict(prepare(root, provider=args.provider, profile=args.profile, rationale=args.rationale, evidence=args.evidence))
        elif args.command == "context": output = escalation_context(_read_route(root)[0])
        elif args.command == "escalate": output = asdict(escalate(root, args.reason))
        elif args.command == "codex-argv":
            argv, mechanism = codex_argv(_read_route(root)[0], args.prompt, args.codex_bin); output = {"argv": argv, "mechanism": mechanism}
        elif args.command == "run-codex":
            route, path = _read_route(root)
            output = run_codex(route, args.prompt, args.codex_bin)
            _write_route(path, Route(**{**asdict(route), "execution": output}))
        elif args.command == "dispatch-codex":
            output = dispatch_codex(
                root,
                profile=args.profile,
                rationale=args.rationale,
                evidence=args.evidence,
                prompt=args.prompt,
                codex_bin=args.codex_bin,
            )
        elif args.command == "claude-agent": output = claude_agent(_read_route(root)[0])
        elif args.command == "dispatch-claude":
            output = prepare_claude_handoff(root, profile=args.profile, rationale=args.rationale, evidence=args.evidence)
        elif args.command == "record-claude-execution":
            output = record_claude_execution(root, agent_id=args.agent_id, summary=args.summary)
        else: output = postcheck(_read_route(root)[0])
    except (ContainmentError, RoutingError) as exc:
        print(f"Model routing blocked: {exc}", file=sys.stderr); return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.command == "run-codex" and _failed_codex_execution(output):
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
