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
import math
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, main_root, read_platform_config, utc_now
from _platform_common import profile as workflow_profile_of
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
# Route root topology. LINKED_WORKTREE is the multi-agent shape: task_worktree
# is a distinct, registered `git worktree` of integration_root, so a
# write-capable child can be safely assigned there. STANDALONE_CLONE is the
# standard-profile shape: the supervisor's own isolated full clone *is*
# task_worktree and integration_root at once (no linked worktree exists), so
# this route root is parent-only -- it must never be treated as a proven
# child-writer boundary (see dispatch_codex/prepare_claude_handoff).
LINKED_WORKTREE = "linked-worktree"
STANDALONE_CLONE = "standalone-clone"
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
    # LINKED_WORKTREE or STANDALONE_CLONE (see the module-level constants).
    # Defaults to LINKED_WORKTREE so a routing record written before this
    # field existed is read back as the strict topology it was always
    # recorded under.
    topology: str = LINKED_WORKTREE
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


def _durable_record_path(route: Route) -> Path:
    """Return the integration-owned copy of an executed routing record.

    The task-local copy remains the active route and containment receipt while
    a child runs. Once execution evidence is final, mirror that same record
    into existing integration lifecycle state so normal worktree cleanup does
    not discard a baseline observation.
    """
    return Path(route.integration_root) / ".claude" / "model-routing" / f"{route.change}.json"


def _persist_completed_execution(route: Route) -> None:
    if isinstance(route.execution, dict):
        _write_route(_durable_record_path(route), route)


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

# Runtime-neutral efficiency vocabulary.  A measurement is deliberately a
# small value/source/status tuple rather than a bare number: missing runtime
# data must remain distinguishable from a real zero.  The platform owns the
# timing boundary; optional usage values are only populated by a runtime
# adapter when its structured event contract exposes that exact value.
EFFICIENCY_USAGE_FIELDS = (
    "input_tokens",
    "cache_read_tokens",
    "fresh_input_tokens",
    "output_tokens",
    "total_tokens",
    "request_count",
)
EFFICIENCY_MIN_BASELINE_EXECUTIONS = 15
EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS = 5


def _unknown_measurement() -> dict[str, Any]:
    return {"value": None, "source": SOURCE_UNKNOWN, "status": "unknown"}


def _runtime_measurement(value: int) -> dict[str, Any]:
    return {"value": value, "source": SOURCE_RUNTIME_CONFIRMED, "status": "measured"}


def _unknown_usage() -> dict[str, dict[str, Any]]:
    return {field: _unknown_measurement() for field in EFFICIENCY_USAGE_FIELDS}


def _platform_timestamp() -> str:
    """An ISO timestamp with enough precision to explain a duration sample."""
    return datetime.now(timezone.utc).isoformat()


def _efficiency_timing(started_at: str, elapsed_ms: int) -> dict[str, Any]:
    return {
        "started_at": started_at,
        "ended_at": _platform_timestamp(),
        "elapsed_ms": elapsed_ms,
        "source": "platform",
        "status": "measured",
    }


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
        route = Route(source_issue=payload["source_issue"], change=payload["change"], task_worktree=payload["task_worktree"], integration_root=payload["integration_root"], provider=payload["provider"], profile=payload["profile"], executor_model=payload["executor_model"], rationale=payload["rationale"], evidence=tuple(payload.get("evidence", [])), prepared_at=payload["prepared_at"], pre_snapshot=payload["pre_snapshot"], execution=execution if isinstance(execution, dict) else None, escalations=tuple(payload.get("escalations", [])), start_tier=payload.get("start_tier"), freshness=payload.get("freshness", "confirmed"), topology=payload.get("topology", LINKED_WORKTREE), supervisor=supervisor if isinstance(supervisor, dict) else {})
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
    config = read_platform_config(root)
    task_root = root.resolve()
    if workflow_profile_of(config) == "standard" and task_root == integration:
        # The standard profile has no linked worktree: the supervisor's own
        # isolated full clone is both the assigned task root and the
        # integration copy. Recording that clone as a parent-only route root
        # is the point (see the standard-profile-lifecycle-compatibility
        # spec) -- it must never be reinterpreted as a proven child-writer
        # boundary, so dispatch_codex/prepare_claude_handoff refuse to launch
        # an actual child writer on a STANDALONE_CLONE route.
        assigned = integration
        topology = STANDALONE_CLONE
    else:
        assigned = resolve_assigned_worktree(integration, root)
        topology = LINKED_WORKTREE
    route = Route(source_issue=source_issue, change=change, task_worktree=str(assigned), integration_root=str(integration), provider=provider, profile=profile, executor_model=_model_for(config, provider, profile), rationale=rationale.strip(), evidence=tuple(evidence), prepared_at=utc_now(), pre_snapshot=_snapshot_to_dict(snapshot(integration)), start_tier=start_tier, freshness="confirmed", topology=topology, supervisor=_supervisor_provenance(config, provider))
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


def _refuse_child_writer_on_standalone_clone(route: Route) -> None:
    if route.topology == STANDALONE_CLONE:
        raise RoutingError(
            "a write-capable delegated child cannot be launched from a standalone standard-profile clone: "
            "there is no distinct assigned worktree to prove a containment boundary against. Parent-only "
            "route recording is not child containment evidence -- retain this work on the supervisor."
        )


def codex_argv(route: Route, prompt: str, codex_bin: str | None = None) -> tuple[list[str], str]:
    if route.provider != "codex":
        raise RoutingError("the prepared route is not a Codex route")
    _refuse_child_writer_on_standalone_clone(route)
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


def _codex_usage_from_line(line: str) -> dict[str, int] | None:
    """Read only the exact structured completion usage shape we support.

    The adapter intentionally does not scrape terminal text or derive totals.
    A future runtime can add another explicit adapter once it has an equally
    authoritative contract.  An incomplete payload is still useful: each
    present non-negative integer is measured and every other field remains
    explicitly unknown.
    """
    if not line.lstrip().startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(event, dict) or event.get("type") != "turn.completed":
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    fields = {
        "input_tokens": "input_tokens",
        "cache_read_tokens": "cached_input_tokens",
        "output_tokens": "output_tokens",
        "total_tokens": "total_tokens",
    }
    captured: dict[str, int] = {}
    for normalized, runtime_name in fields.items():
        value = usage.get(runtime_name)
        # bool is an int subclass but is not a meaningful token count.
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            captured[normalized] = value
    return captured


def _codex_usage_evidence(usage_events: list[dict[str, int]], turn_count: int) -> dict[str, dict[str, Any]]:
    """Normalize one unambiguous structured Codex completion observation.

    Multiple completion payloads may be incremental or cumulative depending on
    a future runtime contract.  We therefore leave token values unknown rather
    than summing or selecting one without an explicit identity.  `turn.started`
    is an independently countable structured runtime event, so its count is
    safe to record when present.
    """
    usage = _unknown_usage()
    if turn_count:
        usage["request_count"] = _runtime_measurement(turn_count)
    if len(usage_events) == 1:
        for field, value in usage_events[0].items():
            usage[field] = _runtime_measurement(value)
    return usage


def run_codex(route: Route, prompt: str, codex_bin: str | None = None) -> dict[str, Any]:
    argv, mechanism = codex_argv(route, prompt, codex_bin)
    # Codex workspace-write is the prevention layer. The legacy helper only
    # validates the assignment and observes/records the required post-check.
    decision = determine_codex_tier(codex_bin=codex_bin, require_hard=True, integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree))
    captured: dict[str, str | int | list[dict[str, int]] | None] = {
        "thread_id": None,
        "turn_count": 0,
        "usage_events": [],
    }
    started_at = _platform_timestamp()
    started_tick = time.perf_counter_ns()

    def _on_line(line: str) -> None:
        print(line)
        thread_id = _codex_thread_id_from_line(line)
        if thread_id is not None:
            captured["thread_id"] = thread_id
        if line.lstrip().startswith("{"):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                event = None
            if isinstance(event, dict) and event.get("type") == "turn.started":
                captured["turn_count"] = int(captured["turn_count"] or 0) + 1
        usage = _codex_usage_from_line(line)
        if usage is not None:
            events = captured["usage_events"]
            assert isinstance(events, list)
            events.append(usage)

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
    except OSError as exc:
        # A platform-owned launch boundary (for example the local writer
        # receipt) can itself be unavailable before a child process exists.
        # Persist that attempted-but-unlaunched abnormal outcome, including
        # timing, instead of emitting a traceback that leaves a prepared route
        # looking like it has no meaningful execution evidence.
        result = SimpleNamespace(launched=False, returncode=None, violation=True, writer_state="unavailable")
        abnormal_error = f"unable to launch delegated Codex execution: {exc}"
    usage_events = captured["usage_events"]
    assert isinstance(usage_events, list)
    elapsed_ms = max(0, round((time.perf_counter_ns() - started_tick) / 1_000_000))
    output = {
        "mechanism": mechanism,
        "launched": result.launched,
        "returncode": result.returncode,
        "violation": result.violation,
        "writer_state": getattr(result, "writer_state", "released"),
        "efficiency": {
            "timing": _efficiency_timing(started_at, elapsed_ms),
            "usage": _codex_usage_evidence(usage_events, int(captured["turn_count"] or 0)),
        },
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
    _refuse_child_writer_on_standalone_clone(route)
    execution = run_codex(route, prompt, codex_bin)
    route = Route(**{**asdict(route), "execution": execution})
    _write_route(_record_path(root, route.change), route)
    _persist_completed_execution(route)
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
    _refuse_child_writer_on_standalone_clone(route)
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
    _refuse_child_writer_on_standalone_clone(route)
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
    _refuse_child_writer_on_standalone_clone(route)
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
    _persist_completed_execution(next_route)
    return execution


def postcheck(route: Route) -> dict[str, Any]:
    result = check_containment(_snapshot_from_dict(route.pre_snapshot), snapshot(Path(route.integration_root)))
    if result.violated:
        assigned = Path(route.task_worktree)
        record_containment_friction(Path(route.integration_root), assigned, result, task=route.source_issue, enforcement_tier="native-worktree")
        raise RoutingError(format_violation_message(assigned, result))
    return {"containment": "clean", "pre_existing_changes": list(result.pre_existing_changes)}


def _worktree_roots(root: Path) -> list[Path]:
    """Return local worktrees without requiring a network or mutating Git state."""
    roots = {root.resolve()}
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        return sorted(roots)
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            candidate = Path(line.removeprefix("worktree ")).resolve()
            if candidate.is_dir():
                roots.add(candidate)
    return sorted(roots)


def _local_routing_records(root: Path) -> list[dict[str, Any]]:
    """Read ignored local provenance conservatively; malformed records are skipped."""
    records: list[dict[str, Any]] = []
    seen: set[Path] = set()
    seen_routes: set[tuple[str, str]] = set()
    for worktree in _worktree_roots(root):
        for path in sorted((worktree / ".claude" / "model-routing").glob("*.json")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                source_issue = payload.get("source_issue")
                change = payload.get("change")
                identity = (source_issue, change) if isinstance(source_issue, str) and isinstance(change, str) else None
                if identity is not None and identity in seen_routes:
                    continue
                if identity is not None:
                    seen_routes.add(identity)
                records.append(payload)
    return records


def _measurement_from_execution(execution: dict[str, Any], field: str) -> dict[str, Any] | None:
    efficiency = execution.get("efficiency")
    if not isinstance(efficiency, dict):
        return None
    if field == "elapsed_ms":
        timing = efficiency.get("timing")
        if not isinstance(timing, dict):
            return None
        value = timing.get("elapsed_ms")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0 and timing.get("status") == "measured":
            return {"value": value, "source": timing.get("source", "unknown"), "status": "measured"}
        return _unknown_measurement()
    usage = efficiency.get("usage")
    if not isinstance(usage, dict):
        return None
    measurement = usage.get(field)
    return measurement if isinstance(measurement, dict) else None


def _summary(values: list[int], missing: int, unknown: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "measured": len(values),
        "unknown": unknown,
        "missing": missing,
    }
    if values:
        ordered = sorted(values)
        summary["median"] = statistics.median(ordered)
        if len(ordered) >= EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS:
            summary["p95"] = ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]
    return summary


def _verification_outcome(root: Path, record: dict[str, Any]) -> str:
    """Read the existing OpenSpec receipt; never create another status field."""
    change = record.get("change")
    if not isinstance(change, str) or not change:
        return "missing"
    candidates = [root / "openspec" / "changes" / change / "verification.md"]
    candidates.extend(sorted((root / "openspec" / "changes" / "archive").glob(f"*-{change}/verification.md")))
    for receipt in candidates:
        try:
            lines = {line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()}
        except OSError:
            continue
        return "passed" if "OpenSpec-Verify: PASS" in lines else "recorded_without_pass"
    return "missing"


def efficiency_baseline(root: Path) -> dict[str, Any]:
    """Produce a bounded local baseline from routing/execution provenance.

    This is deliberately analysis-only.  It neither changes a route nor tries
    to infer a token total from a partial provider response.  Historical route
    records remain observations with missing efficiency fields.
    """
    records = _local_routing_records(root)
    launched = [record.get("execution") for record in records if isinstance(record.get("execution"), dict) and record["execution"].get("launched")]
    executions = [execution for execution in launched if isinstance(execution, dict)]
    metrics: dict[str, dict[str, Any]] = {}
    for field in ("elapsed_ms", *EFFICIENCY_USAGE_FIELDS):
        values: list[int] = []
        missing = 0
        unknown = 0
        for execution in executions:
            measurement = _measurement_from_execution(execution, field)
            if measurement is None:
                missing += 1
                continue
            value = measurement.get("value")
            if measurement.get("status") == "measured" and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values.append(value)
            else:
                unknown += 1
        metrics[field] = _summary(values, missing, unknown)
    outcomes: dict[str, int] = {}
    for execution in executions:
        outcome = execution.get("outcome")
        label = outcome if isinstance(outcome, str) and outcome else "unknown"
        outcomes[label] = outcomes.get(label, 0) + 1
    verification: dict[str, int] = {}
    for record in records:
        label = _verification_outcome(root, record)
        verification[label] = verification.get(label, 0) + 1
    escalated = sum(1 for record in records if isinstance(record.get("escalations"), list) and record["escalations"])
    sufficient = len(executions) >= EFFICIENCY_MIN_BASELINE_EXECUTIONS
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "scope": "local routing/execution provenance",
        "observations": {
            "routing_records": len(records),
            "launched_executions": len(executions),
            "historical_or_unlaunched_records": len(records) - len(executions),
            "escalated_routes": escalated,
            "outcomes": outcomes,
            "verification": verification,
        },
        "metrics": metrics,
        "evidence": {
            "status": "sufficient" if sufficient else "insufficient",
            "minimum_decision_quality_executions": EFFICIENCY_MIN_BASELINE_EXECUTIONS,
            "detail": (
                "Local sample meets the initial execution-count guideline; compare only compatible populated fields."
                if sufficient
                else "Collect roughly 15–30 verified managed executions before drawing an efficiency conclusion; missing and unknown measurements are not zero."
            ),
        },
    }


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
    subparsers.add_parser("efficiency-baseline", help="report bounded local execution-efficiency evidence without changing routing")
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
            completed_route = Route(**{**asdict(route), "execution": output})
            _write_route(path, completed_route)
            _persist_completed_execution(completed_route)
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
        elif args.command == "efficiency-baseline":
            output = efficiency_baseline(root)
        else: output = postcheck(_read_route(root)[0])
    except (ContainmentError, RoutingError) as exc:
        print(f"Model routing blocked: {exc}", file=sys.stderr); return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.command == "run-codex" and _failed_codex_execution(output):
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
