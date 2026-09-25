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
import ast
import json
import math
import re
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, main_root, read_platform_config, utc_now
from _platform_common import profile as workflow_profile_of
from delegated_write_guard import (
    CLASSIFICATION_CLEAN,
    CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE,
    CLASSIFICATION_VIOLATION,
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
    verify_historical_external_advance,
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
    # Read-only context shunting is an auxiliary operation inside this route,
    # not a second execution/routing state machine.  Keep only bounded
    # observations here; never retain a prompt, transcript, or source text.
    context_delegations: tuple[dict[str, Any], ...] = ()


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


def _read_managed_provenance(path: Path, root: Path | None = None, expected_source: str | None = None) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        change = payload["change"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise RoutingError(f"cannot read managed-task provenance at {path}") from exc
    source_issue = payload.get("source_issue")
    if source_issue is None and root is not None and "private_lineage_handle" in payload:
        import managed_task

        try:
            source_issue = managed_task.source_issue_for_provenance(root, path.parent, expected_source=expected_source)
        except managed_task.ManagedTaskError as exc:
            raise RoutingError("private managed-task lineage could not be verified") from exc
        payload = {**payload, "source_issue": source_issue}
    if not isinstance(source_issue, str) or not isinstance(change, str):
        raise RoutingError("managed-task provenance has invalid source_issue/change values")
    return payload


def _managed_provenance(root: Path) -> dict[str, Any]:
    """Read the active provenance required for route preparation and dispatch.

    This deliberately remains active-only. The archive-stable resolver below
    is read/enforcement-only and must not legalize a retrospective route.
    """
    candidates = list((root / "openspec" / "changes").glob("*/.managed-task.json"))
    if len(candidates) != 1:
        raise RoutingError(f"model routing requires exactly one materialized managed OpenSpec change in this task checkout; found {len(candidates)}")
    return _read_managed_provenance(candidates[0], root)


def resolve_managed_provenance(root: Path, source_issue: str, change: str) -> tuple[dict[str, Any], Path, str]:
    """Resolve one supplied task/change binding from active or archived lineage.

    The caller must know both parts of the identity. In particular, this
    helper never chooses an arbitrary archived change based on ambient state.
    """
    if not isinstance(source_issue, str) or not source_issue.strip() or not isinstance(change, str) or not change.strip():
        raise RoutingError("routing verification needs an exact non-empty managed source_issue and change binding")
    active = root / "openspec" / "changes" / change / ".managed-task.json"
    candidates = [active] if active.is_file() else []
    archive = root / "openspec" / "changes" / "archive"
    if archive.is_dir():
        candidates.extend(sorted(archive.glob(f"*-{change}/.managed-task.json")))
        candidates.extend(sorted(archive.glob(f"*/{change}/.managed-task.json")))
    matches: list[tuple[dict[str, Any], Path, str]] = []
    wrong_identity: list[str] = []
    for path in candidates:
        payload = _read_managed_provenance(path, root, source_issue)
        candidate_source = payload["source_issue"]
        candidate_change = payload["change"]
        if candidate_change == change and candidate_source.lower() == source_issue.lower():
            matches.append((payload, path, "active" if path == active else "archived"))
        else:
            wrong_identity.append(f"{candidate_source} ({candidate_change})")
    if not matches:
        if wrong_identity:
            raise RoutingError(
                f"managed routing identity mismatch for {source_issue} ({change}); canonical provenance belongs to "
                + ", ".join(sorted(set(wrong_identity)))
            )
        raise RoutingError(
            f"no matching active or archived managed OpenSpec provenance for {source_issue} ({change}); "
            "restore the canonical lineage through reviewed recovery"
        )
    if len(matches) != 1:
        raise RoutingError(
            f"managed routing identity is ambiguous for {source_issue} ({change}): "
            + ", ".join(str(path) for _, path, _ in matches)
        )
    return matches[0]


def current_managed_identity(root: Path) -> tuple[str, str]:
    """Read durable task state, with narrow active-only legacy compatibility."""
    state = root / ".managed-task-state.json"
    if state.is_file():
        payload = _read_managed_provenance(state)
        return payload["source_issue"], payload["change"]
    return _managed_identity(root)


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


def _route_from_payload(payload: dict[str, Any], *, source_issue: str, change: str, missing_detail: str) -> Route:
    try:
        execution = payload.get("execution")
        supervisor = payload.get("supervisor")
        observations = payload.get("context_delegations", [])
        route = Route(source_issue=payload["source_issue"], change=payload["change"], task_worktree=payload["task_worktree"], integration_root=payload["integration_root"], provider=payload["provider"], profile=payload["profile"], executor_model=payload["executor_model"], rationale=payload["rationale"], evidence=tuple(payload.get("evidence", [])), prepared_at=payload["prepared_at"], pre_snapshot=payload["pre_snapshot"], execution=execution if isinstance(execution, dict) else None, escalations=tuple(payload.get("escalations", [])), start_tier=payload.get("start_tier"), freshness=payload.get("freshness", "confirmed"), topology=payload.get("topology", LINKED_WORKTREE), supervisor=supervisor if isinstance(supervisor, dict) else {}, context_delegations=tuple(item for item in observations if isinstance(item, dict)))
    except (KeyError, TypeError) as exc:
        raise RoutingError(missing_detail) from exc
    if route.source_issue.lower() != source_issue.lower() or route.change != change:
        raise RoutingError("routing record provenance does not match the exact managed task identity")
    return route


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
# A supplied Claude Agent-tool id is a claim the supervisor itself makes, not
# a platform-observed fact -- distinct from both a policy-selected value and
# a runtime-confirmed one. See record_claude_execution.
SOURCE_SELF_REPORTED = "self-reported"

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
    # This field is deliberately distinct from a runtime-local turn, message,
    # or step count.  An adapter may only populate it when its published event
    # contract proves that one counted event is exactly one model request.
    "model_request_count",
)
# Records created before decision-quality comparability used ``request_count``
# for several incompatible runtime events.  Keep it readable as historical
# evidence, but never present it as a canonical cross-runtime metric again.
LEGACY_AMBIGUOUS_USAGE_FIELDS = ("request_count",)
# Platform-owned elapsed time has one measurement boundary across runtimes. A
# canonical model-request count joins it only if an adapter later proves the
# event identity. Token accounting remains provider/runtime-generation local.
CROSS_RUNTIME_EFFICIENCY_FIELDS = ("elapsed_ms", "model_request_count")
EFFICIENCY_MIN_BASELINE_EXECUTIONS = 15
EFFICIENCY_MIN_PERCENTILE_OBSERVATIONS = 5


def efficiency_unknown_measurement() -> dict[str, Any]:
    """Return the canonical representation of unavailable runtime evidence."""
    return {"value": None, "source": SOURCE_UNKNOWN, "status": "unknown"}


def efficiency_runtime_measurement(value: int) -> dict[str, Any]:
    """Return one canonical runtime-confirmed efficiency measurement."""
    return {"value": value, "source": SOURCE_RUNTIME_CONFIRMED, "status": "measured"}


def efficiency_unknown_usage() -> dict[str, dict[str, Any]]:
    """Return all canonical usage fields as unknown, never fabricated zeroes."""
    return {field: efficiency_unknown_measurement() for field in EFFICIENCY_USAGE_FIELDS}


def _platform_timestamp() -> str:
    """An ISO timestamp with enough precision to explain a duration sample."""
    return datetime.now(timezone.utc).isoformat()


def efficiency_timing(started_at: str, elapsed_ms: int) -> dict[str, Any]:
    """Return canonical platform-owned execution timing evidence."""
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
    except (OSError, json.JSONDecodeError) as exc:
        raise RoutingError(f"no readable routing record for managed change {change}; run prepare first") from exc
    route = _route_from_payload(
        payload,
        source_issue=source_issue,
        change=change,
        missing_detail=f"routing record for managed change {change} is incomplete or invalid",
    )
    return route, path


def _durable_route_paths(root: Path, change: str) -> list[Path]:
    """Prefer the integration-owned record while retaining same-root compatibility."""
    roots: list[Path] = []
    try:
        roots.append(main_root().resolve())
    except Exception:  # pragma: no cover - read-only recovery outside a Git worktree
        pass
    roots.append(root.resolve())
    return list(dict.fromkeys(candidate / ".claude" / "model-routing" / f"{change}.json" for candidate in roots))


def read_durable_route(root: Path, source_issue: str, change: str) -> tuple[Route, Path]:
    """Read exact task evidence after validating active-or-archived lineage."""
    resolve_managed_provenance(root, source_issue, change)
    paths = _durable_route_paths(root, change)
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError) as exc:
            raise RoutingError(f"routing evidence for {source_issue} ({change}) is unreadable: {path}") from exc
        return _route_from_payload(
            payload,
            source_issue=source_issue,
            change=change,
            missing_detail=f"routing evidence for {source_issue} ({change}) is incomplete or invalid",
        ), path
    raise RoutingError(
        f"routing evidence is missing for {source_issue} ({change}); run route-codex or route-claude before implementation and archive"
    )


def read_current_durable_route(root: Path) -> tuple[Route, Path]:
    source_issue, change = current_managed_identity(root)
    return read_durable_route(root, source_issue, change)


def _retention_policy(route: Route) -> str | None:
    if route.profile == "complex":
        return "complex-parent"
    if route.profile in {"routine", "standard"} and route.topology == STANDALONE_CLONE:
        return "parent-only-topology"
    return None


def _require_clean_postcheck(execution: dict[str, Any], provider: str) -> None:
    postcheck_result = execution.get("postcheck")
    if not isinstance(postcheck_result, dict) or postcheck_result.get("containment") != "clean":
        raise RoutingError(f"routing gate requires a clean containment postcheck for {provider} execution")


def _is_self_reported_claude(execution: dict[str, Any]) -> bool:
    """True for a Claude execution recorded only as a self-reported claim.

    Covers both the current explicit shape (``launch_evidence ==
    "self-reported"``) and the legacy pre-repair shape, which carried an
    ``agent_id`` key but no ``outcome`` key at all (it always wrote
    ``launched: True`` unconditionally).
    """
    if not isinstance(execution, dict):
        return False
    if execution.get("launch_evidence") == "self-reported":
        return True
    return "agent_id" in execution and "outcome" not in execution


def _launch_confirmed(execution: Any) -> bool:
    """True only for a launch the platform can actually treat as confirmed.

    A self-reported Claude claim -- current or legacy -- never counts, even
    when a legacy record carries ``launched: True``.
    """
    if not isinstance(execution, dict):
        return False
    return execution.get("launched") is True and not _is_self_reported_claude(execution)


def require_routing_gate(root: Path, source_issue: str, change: str) -> Route:
    """Fail closed unless durable evidence proves the exact routed outcome."""
    route, _ = read_durable_route(root, source_issue, change)
    if route.provider not in PROVIDERS or route.profile not in PROFILES:
        raise RoutingError("routing evidence has an unsupported provider or execution profile")
    execution = route.execution
    if not isinstance(execution, dict):
        if route.profile == "complex":
            raise RoutingError(
                "complex routing requires an explicit retained execution outcome after implementation; "
                "a prepared complex route is not terminal evidence"
            )
        raise RoutingError(
            "routing evidence has no completed execution outcome; record a clean child execution or an explicit supported retained outcome before archive"
        )
    if execution.get("outcome") == "retained":
        policy = _retention_policy(route)
        retained = execution.get("retained")
        if not isinstance(retained, dict) or retained.get("role") != "supervisor" or retained.get("policy") != policy:
            raise RoutingError("routing evidence has unsupported or incomplete retained execution metadata")
        if execution.get("launched") is not False or not isinstance(retained.get("reason"), str) or not retained["reason"].strip():
            raise RoutingError("routing evidence must explicitly state a non-empty parent-retention reason")
        _require_clean_postcheck(execution, route.provider)
        return route
    if route.provider == "codex":
        if not execution.get("launched"):
            raise RoutingError(f"routing gate requires a clean successful native {route.provider} executor launch for routine/standard work")
        recovery = execution.get("recovery")
        # A reviewed recovery bypasses exactly the three checks below and
        # nothing else: it never edits `outcome`/`returncode`/`violation` on
        # the original execution (see `recover_external_advance`), so this
        # gate is the only place the recovered classification is consulted,
        # never inferred from `returncode == 0` alone.
        recovered = isinstance(recovery, dict) and recovery.get("classification") == CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE
        if not recovered and (
            execution.get("outcome") != "completed" or execution.get("returncode") != 0 or execution.get("violation")
        ):
            raise RoutingError("routing gate requires a clean successful native Codex executor launch for routine/standard work")
        return route
    # Claude: the gate cannot rely on `launched` (the Agent tool has no
    # platform-verifiable receipt); it accepts only an explicit self-reported
    # claim backed by a clean containment postcheck. A legacy record carrying
    # `launched: True` without that explicit outcome is refused so it gets
    # repaired by rerunning record-claude-execution before archive.
    if execution.get("outcome") == "claimed" and execution.get("launch_evidence") == "self-reported":
        _require_clean_postcheck(execution, "Claude")
        return route
    raise RoutingError(
        "routing evidence claims a Claude launch the platform cannot verify (no self-reported claim outcome recorded); "
        "rerun record-claude-execution before archive"
    )


def _write_route(path: Path, route: Route) -> None:
    atomic_write_text(path, json.dumps(asdict(route), indent=2, sort_keys=True) + "\n")


# The exact, deterministic string `delegation_containment.record_containment_friction`
# writes as friction evidence. Recovery only trusts this evidence shape -- never
# free-form prose describing the same incident -- because it is generated by
# reviewed code with a fixed format, not authored after the fact.
_CONTAINMENT_FRICTION_EVIDENCE_RE = re.compile(
    r"new_changes=(\[.*\]) disappeared_changes=(\[.*\]) head_moved=(True|False) enforcement_tier='([^']*)'"
)


def _parse_containment_friction_evidence(evidence: str) -> tuple[list[str], list[str], bool, str] | None:
    """Parse `record_containment_friction`'s evidence string, or return None.

    Never guesses: any deviation from the exact expected format -- including a
    manually authored summary of the same incident -- yields None rather than
    a best-effort partial parse.
    """
    match = _CONTAINMENT_FRICTION_EVIDENCE_RE.fullmatch(evidence.strip())
    if match is None:
        return None
    try:
        new_changes = ast.literal_eval(match.group(1))
        disappeared_changes = ast.literal_eval(match.group(2))
    except (ValueError, SyntaxError):
        return None
    if not isinstance(new_changes, list) or not isinstance(disappeared_changes, list):
        return None
    return new_changes, disappeared_changes, match.group(3) == "True", match.group(4)


def _read_friction_log(root: Path) -> list[dict[str, Any]]:
    from agent_friction import log_path  # deferred: avoid a hard top-level coupling for callers that never recover.

    path = log_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entries.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return entries


def recover_external_advance(root: Path, *, friction_event: str, before_head: str, after_head: str) -> dict[str, Any]:
    """Narrowly reviewed recovery for a historic pure-head-move false positive.

    This is not a generic routing override: every fact below must be proven or
    the command refuses without writing anything. It nests a new `recovery`
    record beside the original execution rather than editing it -- `outcome`,
    `returncode` and `violation` on the original execution are never rewritten,
    so the historical failed observation stays intact and auditable.
    """
    route, path = _read_route(root)
    execution = route.execution
    if not isinstance(execution, dict):
        raise RoutingError("recovery requires an existing recorded execution outcome; there is nothing to recover")
    if route.provider != "codex":
        raise RoutingError("recovery is currently supported only for a recorded native-hard Codex execution")
    if execution.get("recovery") is not None:
        raise RoutingError("this execution already has a recorded recovery; recovery is not repeatable")
    if not (execution.get("launched") is True and execution.get("returncode") == 0 and execution.get("violation") is True):
        raise RoutingError(
            "recovery only applies to a launched, returncode==0 execution flagged violation=True; "
            "this execution is not in that exact shape"
        )
    recorded_before = route.pre_snapshot.get("head") if isinstance(route.pre_snapshot, dict) else None
    if recorded_before != before_head:
        raise RoutingError(f"supplied --before-head does not match this route's recorded pre-execution head ({recorded_before!r})")

    entries = _read_friction_log(root)
    friction = next((entry for entry in entries if entry.get("id") == friction_event), None)
    if friction is None:
        raise RoutingError(f"no machine-local friction event with id {friction_event!r} was found")

    friction_source_issue = friction.get("task") or (friction.get("run") or {}).get("source_issue")
    if friction_source_issue != route.source_issue:
        raise RoutingError("the supplied friction event does not identify this exact managed task")
    if route.task_worktree not in str(friction.get("observation", "")):
        raise RoutingError("the supplied friction event does not identify this exact assigned worktree")

    parsed = _parse_containment_friction_evidence(str(friction.get("evidence", "")))
    if parsed is None:
        raise RoutingError(
            "the supplied friction event's evidence is not the exact structured containment format; "
            "cannot prove pure-head-move facts from prose"
        )
    new_changes, disappeared_changes, head_moved, enforcement_tier = parsed
    if new_changes or disappeared_changes or not head_moved:
        raise RoutingError("the supplied friction event does not describe a pure integration-head move with no path mutation")
    if enforcement_tier != EnforcementTier.HARD.value:
        raise RoutingError(f"the supplied friction event records enforcement_tier={enforcement_tier!r}, not native hard containment")

    integration_root = Path(route.integration_root)
    efficiency = execution.get("efficiency")
    timing = efficiency.get("timing") if isinstance(efficiency, dict) else None
    started_at = timing.get("started_at") if isinstance(timing, dict) else None
    ended_at = timing.get("ended_at") if isinstance(timing, dict) else None
    if not (isinstance(started_at, str) and started_at and isinstance(ended_at, str) and ended_at):
        raise RoutingError(
            "recovery requires the original execution's own recorded start/end timing to bind historical "
            "remote-ref evidence; none is available"
        )
    if not verify_historical_external_advance(
        integration_root, before_head, after_head, not_before=started_at, not_after=ended_at
    ):
        raise RoutingError(
            "cannot prove --after-head was this checkout's recorded remote-tracking main during the flagged "
            "execution's own timing window (ancestry and current-main containment alone are not sufficient "
            "historical provenance)"
        )

    recovery = {
        "recovered_at": utc_now(),
        "friction_event": friction_event,
        "classification": CLASSIFICATION_VERIFIED_EXTERNAL_ADVANCE,
        "before_head": before_head,
        "after_head": after_head,
        "reason": (
            "Verified concurrent integration advance: the flagged execution's only observed change was "
            "integration HEAD moving from before_head to after_head with no path mutation under native "
            "hard containment, and after_head is a fast-forward equal to this checkout's recorded remote "
            "main. The original failed execution outcome above is preserved unchanged."
        ),
    }
    next_route = Route(**{**asdict(route), "execution": {**execution, "recovery": recovery}})
    # Durable write first: `require_routing_gate` (verify-routing, archive) reads the
    # integration-root copy before the task-local one. Writing it first and refusing
    # closed on any failure means the task-local copy is never updated while the
    # gate-checked durable record is still stale -- there is no window where this
    # command can report success but a terminal gate still sees the old violation.
    try:
        _persist_completed_execution(next_route)
    except OSError as exc:
        raise RoutingError(
            f"recovery could not persist the durable integration-root routing record; the task-local "
            f"copy was left unchanged so no partial success is reported: {exc}"
        ) from exc
    _write_route(path, next_route)
    return recovery


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


def _codex_usage_evidence(usage_events: list[dict[str, int]]) -> dict[str, dict[str, Any]]:
    """Normalize one unambiguous structured Codex completion observation.

    Multiple completion payloads may be incremental or cumulative depending on
    a future runtime contract.  We therefore leave token values unknown rather
    than summing or selecting one without an explicit identity.  A Codex
    `turn.started` event is useful local evidence, but its published contract
    does not prove one event equals one model request, so it is stored outside
    this canonical usage shape by ``_codex_runtime_counters``.
    """
    usage = efficiency_unknown_usage()
    if len(usage_events) == 1:
        for field, value in usage_events[0].items():
            usage[field] = efficiency_runtime_measurement(value)
    return usage


def _codex_runtime_counters(turn_count: int) -> dict[str, dict[str, Any]]:
    """Keep countable Codex events without promoting them to model requests."""
    if not turn_count:
        return {}
    return {"codex_turn_started": efficiency_runtime_measurement(turn_count)}


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
        result = SimpleNamespace(
            launched=False, returncode=None, violation=True, writer_state="unavailable",
            abnormal_kind="launch-unavailable", retained_work=None,
        )
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
        "classification": getattr(result, "classification", CLASSIFICATION_VIOLATION if result.violation else CLASSIFICATION_CLEAN),
        "before_head": getattr(result, "before_head", None),
        "after_head": getattr(result, "after_head", None),
        "efficiency": {
            "timing": efficiency_timing(started_at, elapsed_ms),
            "usage": _codex_usage_evidence(usage_events),
            "runtime_counters": _codex_runtime_counters(int(captured["turn_count"] or 0)),
        },
    }
    if abnormal_error is not None:
        output["outcome"] = "abnormal"
        output["error"] = abnormal_error
        # Distinguish an external launcher interruption from a steady-state
        # timeout or another launcher failure, and carry the bounded
        # retained-work handoff so a later recovery step is not guessing.
        output["abnormal_kind"] = getattr(result, "abnormal_kind", None) or "other"
        retained_work = getattr(result, "retained_work", None)
        if retained_work is not None:
            output["retained_work"] = (
                retained_work.as_dict() if hasattr(retained_work, "as_dict") else dict(retained_work)
            )
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
    """Record the supervisor's claim that it invoked the emitted Claude hand-off.

    Must run after the real Agent-tool call returns. Runs the mandatory
    content-aware postcheck (fails closed on any integration/main mutation)
    and persists the resulting execution evidence so finish's routing gate
    can consider a routine/standard route.

    The native Agent tool is invoked by the supervisor's own tool call and its
    result reaches only the supervisor's conversation; no platform-owned
    process observes it, and no supported Claude Code surface hands back a
    machine-verifiable launch receipt. The supplied id is therefore recorded
    only as a self-reported claim (``outcome: "claimed"``, ``launched: None``)
    -- never as ``launched: True`` with an executed participant -- so nothing
    downstream can mistake an arbitrary string for proof a child actually ran.
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
        "outcome": "claimed",
        "launch_evidence": "self-reported",
        "launched": None,
        "claimed_agent_id": agent_id.strip(),
        "summary": summary.strip() if summary else None,
        "tier": tier_decision.tier.value,
        "mechanism": tier_decision.mechanism,
        "postcheck": check,
        "recorded_at": utc_now(),
        # Not an executed participant: the model is what the supervisor
        # selected via claude_agent(), but there is no platform-verifiable
        # evidence a child using it ever ran, so provenance source is
        # self-reported rather than selected/runtime-confirmed. Reasoning
        # effort has no supported selection/confirmation surface on the
        # current Agent tool (see claude_agent docstring), so it stays
        # unknown.
        "claimed_participant": {
            "role": "executor",
            "provider": "claude",
            "profile": route.profile,
            "model": _model_provenance(route.executor_model, SOURCE_SELF_REPORTED),
            "reasoning_effort": _effort_provenance(None, SOURCE_UNKNOWN),
            "execution_id": {"value": agent_id.strip(), "kind": "claude-agent-id"},
        },
    }
    next_route = Route(**{**asdict(route), "execution": execution})
    _write_route(path, next_route)
    _persist_completed_execution(next_route)
    return execution


def record_retained_execution(root: Path, *, reason: str) -> dict[str, Any]:
    """Persist a policy-valid parent-retained outcome after implementation.

    This is intentionally active-only through ``_read_route``. Once the
    change is archived, the pre-implementation routing boundary has passed;
    callers can only verify the durable history, never repair it late.
    """
    route, path = _read_route(root)
    policy = _retention_policy(route)
    if policy is None:
        raise RoutingError(
            "this routine/standard route has a proven child-writer path; record its real child execution or escalate before retaining work"
        )
    if route.execution is not None:
        raise RoutingError("routing record already has execution evidence; do not overwrite a real child outcome with parent retention")
    if not reason.strip():
        raise RoutingError("recording retained execution requires a concrete non-empty reason")
    execution = {
        "outcome": "retained",
        "launched": False,
        "retained": {"role": "supervisor", "policy": policy, "reason": reason.strip()},
        "postcheck": postcheck(route),
        "recorded_at": utc_now(),
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
        return efficiency_unknown_measurement()
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


def _verification_roots(root: Path, record: dict[str, Any]) -> list[Path]:
    """Find lifecycle-owned locations that can outlive a task worktree."""
    roots: list[Path] = []
    integration_root = record.get("integration_root")
    if isinstance(integration_root, str) and integration_root:
        candidate = Path(integration_root).expanduser()
        if candidate.is_dir():
            roots.append(candidate.resolve())
    try:
        roots.append(main_root().resolve())
    except Exception:  # pragma: no cover - reporting stays useful outside Git
        pass
    roots.append(root.resolve())
    return list(dict.fromkeys(roots))


def _verification_outcome(root: Path, record: dict[str, Any]) -> str:
    """Read the existing OpenSpec receipt; never create another status field."""
    change = record.get("change")
    if not isinstance(change, str) or not change:
        return "missing"
    candidates: list[Path] = []
    for lifecycle_root in _verification_roots(root, record):
        candidates.append(lifecycle_root / "openspec" / "changes" / change / "verification.md")
        candidates.extend(sorted((lifecycle_root / "openspec" / "changes" / "archive").glob(f"*-{change}/verification.md")))
    for receipt in candidates:
        try:
            lines = {line.strip() for line in receipt.read_text(encoding="utf-8").splitlines()}
        except OSError:
            continue
        return "passed" if "OpenSpec-Verify: PASS" in lines else "recorded_without_pass"
    return "missing"


def _summarize_measurements(executions: list[dict[str, Any]], field: str) -> dict[str, Any]:
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
    return _summary(values, missing, unknown)


def _runtime_counter_summaries(executions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Summarize each runtime-local counter independently, never together."""
    names: set[str] = set()
    for execution in executions:
        efficiency = execution.get("efficiency")
        counters = efficiency.get("runtime_counters") if isinstance(efficiency, dict) else None
        if isinstance(counters, dict):
            names.update(name for name in counters if isinstance(name, str))
    summaries: dict[str, dict[str, Any]] = {}
    for name in sorted(names):
        values: list[int] = []
        missing = 0
        unknown = 0
        for execution in executions:
            efficiency = execution.get("efficiency")
            counters = efficiency.get("runtime_counters") if isinstance(efficiency, dict) else None
            measurement = counters.get(name) if isinstance(counters, dict) else None
            if not isinstance(measurement, dict):
                missing += 1
                continue
            value = measurement.get("value")
            if measurement.get("status") == "measured" and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values.append(value)
            else:
                unknown += 1
        summaries[name] = _summary(values, missing, unknown)
    return summaries


def _runtime_identity(record: dict[str, Any]) -> str:
    """Keep provider/runtime-generation local metrics out of cross-runtime sums."""
    provider = record.get("provider")
    model = record.get("executor_model")
    if isinstance(provider, str) and provider and isinstance(model, str) and model:
        return f"{provider}:{model}"
    if isinstance(provider, str) and provider:
        return provider
    return "unknown"


def _runtime_local_metric_summaries(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        execution = record.get("execution")
        if isinstance(execution, dict):
            grouped.setdefault(_runtime_identity(record), []).append(execution)
    return {
        identity: {field: _summarize_measurements(executions, field) for field in EFFICIENCY_USAGE_FIELDS if field != "model_request_count"}
        for identity, executions in sorted(grouped.items())
    }


def efficiency_baseline(root: Path) -> dict[str, Any]:
    """Produce a bounded local baseline from routing/execution provenance.

    This is deliberately analysis-only.  It neither changes a route nor tries
    to infer a token total from a partial provider response.  Historical route
    records remain observations with missing efficiency fields.
    """
    records = _local_routing_records(root)
    launched_records = [record for record in records if _launch_confirmed(record.get("execution"))]
    executions = [record["execution"] for record in launched_records if isinstance(record.get("execution"), dict)]
    verification_by_record = [(record, _verification_outcome(root, record)) for record in records]
    verified_records = [record for record, outcome in verification_by_record if outcome == "passed" and _launch_confirmed(record.get("execution"))]
    verified_executions = [record["execution"] for record in verified_records if isinstance(record.get("execution"), dict)]
    metrics = {field: _summarize_measurements(executions, field) for field in CROSS_RUNTIME_EFFICIENCY_FIELDS}
    comparable_coverage = {field: _summarize_measurements(verified_executions, field) for field in CROSS_RUNTIME_EFFICIENCY_FIELDS}
    outcomes: dict[str, int] = {}
    for execution in executions:
        outcome = execution.get("outcome")
        label = outcome if isinstance(outcome, str) and outcome else "unknown"
        outcomes[label] = outcomes.get(label, 0) + 1
    verification: dict[str, int] = {}
    for _record, label in verification_by_record:
        verification[label] = verification.get(label, 0) + 1
    escalated = sum(1 for record in records if isinstance(record.get("escalations"), list) and record["escalations"])
    qualified_comparable_fields = [
        field for field, coverage in comparable_coverage.items() if coverage["measured"] >= EFFICIENCY_MIN_BASELINE_EXECUTIONS
    ]
    enough_verified = len(verified_executions) >= EFFICIENCY_MIN_BASELINE_EXECUTIONS
    sufficient = enough_verified and bool(qualified_comparable_fields)
    if not enough_verified:
        detail = "Collect roughly 15–30 verified managed executions before drawing an efficiency conclusion; launched-only, missing, and unknown evidence are not zero."
    elif not qualified_comparable_fields:
        detail = "The verified sample meets the count guideline but has no comparable metric measured across that eligible sample."
    else:
        detail = "Verified sample meets the initial decision-quality guideline; compare only the listed qualified canonical fields."
    return {
        "schema_version": 2,
        "generated_at": utc_now(),
        "scope": "local routing/execution provenance",
        "observations": {
            "routing_records": len(records),
            "launched_executions": len(executions),
            "verified_eligible_executions": len(verified_executions),
            "missing_verification_executions": len(executions) - len(verified_executions),
            "historical_or_unlaunched_records": len(records) - len(executions),
            "escalated_routes": escalated,
            "outcomes": outcomes,
            "verification": verification,
        },
        "metrics": metrics,
        "verified_comparable_metric_coverage": comparable_coverage,
        "qualified_comparable_fields": qualified_comparable_fields,
        "runtime_local_metrics": _runtime_local_metric_summaries(launched_records),
        "runtime_local_counters": _runtime_counter_summaries(executions),
        "legacy_ambiguous_counters": {
            field: _summarize_measurements(executions, field) for field in LEGACY_AMBIGUOUS_USAGE_FIELDS
        },
        "evidence": {
            "status": "sufficient" if sufficient else "insufficient",
            "minimum_decision_quality_executions": EFFICIENCY_MIN_BASELINE_EXECUTIONS,
            "detail": detail,
        },
    }


# Routing calibration reuses the efficiency-baseline scanner and verification
# lookup rather than a second execution store. Its eligibility is intentionally
# looser on efficiency comparability (token/request fields) and stricter on the
# routing facts a rubric review actually needs: an authored tier, a determinable
# actual path, and a passed verification receipt.
ROUTING_CALIBRATION_MIN_OBSERVATIONS = EFFICIENCY_MIN_BASELINE_EXECUTIONS
# Bounded descriptive thresholds, not statistical confidence claims. They only
# gate whether an *adequate* sample yields a concrete candidate decision or a
# "monitor" hold; an inadequate sample never reaches them.
ROUTING_CALIBRATION_LOW_ESCALATION_RATE = 0.15
ROUTING_CALIBRATION_HIGH_ESCALATION_RATE = 0.30
ROUTING_CALIBRATION_MIN_R2_SUCCESS_RATE = 0.60


def _authored_tier_of(record: dict[str, Any]) -> str:
    tier = record.get("start_tier")
    return tier if isinstance(tier, str) and tier else "unknown"


def _escalation_reasons(record: dict[str, Any]) -> list[str]:
    escalations = record.get("escalations")
    if not isinstance(escalations, list):
        return []
    reasons: list[str] = []
    for entry in escalations:
        if isinstance(entry, dict):
            reason = entry.get("reason")
            if isinstance(reason, str) and reason.strip():
                reasons.append(reason.strip())
    return reasons


def _actual_route_of(record: dict[str, Any]) -> dict[str, Any]:
    """Distinguish the authored route from what actually ran.

    ``freshness == "escalated"`` and a non-empty ``escalations`` list both
    signal an R2->R3 promotion; the final ``profile`` records where execution
    actually landed. Nothing here is inferred when the record does not say it.
    """
    escalations = record.get("escalations")
    has_escalation = isinstance(escalations, list) and bool(escalations)
    escalated = has_escalation or record.get("freshness") == "escalated"
    profile = record.get("profile")
    final_profile = profile if isinstance(profile, str) and profile else "unknown"
    return {
        "final_profile": final_profile,
        "escalated": escalated,
        "frontier_profile": final_profile == "complex",
        "escalation_reasons": _escalation_reasons(record),
    }


def _execution_outcome_label(record: dict[str, Any]) -> str:
    execution = record.get("execution")
    if isinstance(execution, dict) and _is_self_reported_claude(execution):
        outcome = execution.get("outcome")
        return outcome if isinstance(outcome, str) and outcome else "claimed"
    if not isinstance(execution, dict) or not execution.get("launched"):
        return "not_launched"
    outcome = execution.get("outcome")
    if isinstance(outcome, str) and outcome:
        return outcome
    return "unknown"


def _managed_receipt_for_change(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Read the authored routing receipt for a record's change, if it survives.

    ``task_family``/``rubric_version`` live in the managed-task provenance, not
    the routing record. They are available for an active change and for an
    archived one that kept ``.managed-task.json``; otherwise they stay unknown
    rather than being guessed.
    """
    change = record.get("change")
    if not isinstance(change, str) or not change:
        return {}
    for lifecycle_root in _verification_roots(root, record):
        candidates = [lifecycle_root / "openspec" / "changes" / change / ".managed-task.json"]
        candidates.extend(sorted((lifecycle_root / "openspec" / "changes" / "archive").glob(f"*-{change}/.managed-task.json")))
        for candidate in candidates:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            receipt = payload.get("routing_receipt")
            if isinstance(receipt, dict):
                return receipt
    return {}


def _calibration_observation(root: Path, record: dict[str, Any], verification: str) -> dict[str, Any]:
    receipt = _managed_receipt_for_change(root, record)
    task_family = receipt.get("task_family")
    rubric_version = receipt.get("rubric_version")
    return {
        "change": record.get("change") if isinstance(record.get("change"), str) else "unknown",
        "authored_tier": _authored_tier_of(record),
        "actual": _actual_route_of(record),
        "outcome": _execution_outcome_label(record),
        "verification": verification,
        "launched": _launch_confirmed(record.get("execution")),
        "task_family": task_family if isinstance(task_family, str) and task_family else "unknown",
        "rubric_version": rubric_version if isinstance(rubric_version, str) and rubric_version else "unknown",
        "provider_model_generation": _runtime_identity(record),
    }


def _tier_distribution(observations: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for observation in observations:
        tier = observation["authored_tier"]
        distribution[tier] = distribution.get(tier, 0) + 1
    return dict(sorted(distribution.items()))


def _outcome_distribution(observations: list[dict[str, Any]]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for observation in observations:
        label = observation["outcome"]
        distribution[label] = distribution.get(label, 0) + 1
    return dict(sorted(distribution.items()))


def _is_verified_r2_success_without_escalation(observation: dict[str, Any]) -> bool:
    return (
        observation["authored_tier"] == "R2"
        and not observation["actual"]["escalated"]
        and not observation["actual"]["frontier_profile"]
        and observation["outcome"] == "completed"
        and observation["verification"] == "passed"
    )


def _calibration_slice(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """The bounded metric block shared by the global report and each breakdown."""
    usable = [
        observation
        for observation in observations
        if observation["launched"]
        and observation["verification"] == "passed"
        and observation["authored_tier"] != "unknown"
    ]
    r2_usable = [observation for observation in usable if observation["authored_tier"] == "R2"]
    escalated_usable = [observation for observation in r2_usable if observation["actual"]["escalated"]]
    escalated_success = [
        observation
        for observation in escalated_usable
        if observation["outcome"] == "completed" and observation["verification"] == "passed"
    ]
    r2_verified_success = [observation for observation in r2_usable if _is_verified_r2_success_without_escalation(observation)]
    frontier_exposure = [observation for observation in usable if observation["actual"]["frontier_profile"]]

    reason_counts: dict[str, int] = {}
    unknown_reason = 0
    for observation in observations:
        if not observation["actual"]["escalated"]:
            continue
        reasons = observation["actual"]["escalation_reasons"]
        if not reasons:
            unknown_reason += 1
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    direct_r3 = [observation for observation in observations if observation["authored_tier"] == "R3"]
    direct_r3_launched = [observation for observation in direct_r3 if observation["launched"]]
    direct_r3_success = [
        observation
        for observation in direct_r3_launched
        if not observation["actual"]["escalated"]
        and observation["outcome"] == "completed"
        and observation["verification"] == "passed"
    ]

    adequate = len(usable) >= ROUTING_CALIBRATION_MIN_OBSERVATIONS
    return {
        "usable_observations": len(usable),
        "adequacy": "adequate" if adequate else "insufficient",
        "authored_tier_distribution": _tier_distribution(observations),
        "authored_tier_distribution_usable": _tier_distribution(usable),
        "frontier_exposure_usable": len(frontier_exposure),
        "authored_r2_verified_success_without_escalation": len(r2_verified_success),
        "r2_to_r3_escalation": {
            "usable_r2_observations": len(r2_usable),
            "escalated_usable": len(escalated_usable),
            "escalated_records_total": sum(1 for observation in observations if observation["authored_tier"] == "R2" and observation["actual"]["escalated"]),
            "success_after_escalation": len(escalated_success),
            "recorded_reasons": dict(sorted(reason_counts.items())),
            "unknown_reason": unknown_reason,
        },
        "direct_frontier": {
            "authored_r3_records": len(direct_r3),
            "launched": len(direct_r3_launched),
            "verified_success": len(direct_r3_success),
            "counterfactual_note": (
                "A successful direct R3 execution is not evidence that R2 would have failed; "
                "it is not counted as over-routing."
            ),
        },
        "outcomes_usable": _outcome_distribution(usable),
    }


def _breakdown(observations: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        grouped.setdefault(str(observation[key]), []).append(observation)
    result: dict[str, dict[str, Any]] = {}
    for name, group in sorted(grouped.items()):
        slice_report = _calibration_slice(group)
        result[name] = {
            "usable_observations": slice_report["usable_observations"],
            "adequacy": slice_report["adequacy"],
            "authored_r2_verified_success_without_escalation": slice_report["authored_r2_verified_success_without_escalation"],
            "escalated_usable": slice_report["r2_to_r3_escalation"]["escalated_usable"],
            "frontier_exposure_usable": slice_report["frontier_exposure_usable"],
            "outcomes_usable": slice_report["outcomes_usable"],
        }
    return result


def _calibration_advice(report: dict[str, Any]) -> dict[str, Any]:
    """A human-readable candidate decision. Never a policy mutation."""
    slice_report = report["global"]
    requires_managed_change = True
    if slice_report["adequacy"] != "adequate":
        return {
            "candidate_decision": "insufficient evidence / no policy change",
            "detail": (
                "The usable routing sample is below the decision-quality guideline of "
                f"{ROUTING_CALIBRATION_MIN_OBSERVATIONS} verified observations. The report is still valid: "
                "let more verified managed executions accumulate before tuning the rubric. "
                "Building this report is not blocked by the small sample."
            ),
            "requires_separate_managed_change": requires_managed_change,
        }
    escalation = slice_report["r2_to_r3_escalation"]
    r2_usable = escalation["usable_r2_observations"]
    escalation_rate = escalation["escalated_usable"] / r2_usable if r2_usable else 0.0
    success_rate = slice_report["authored_r2_verified_success_without_escalation"] / r2_usable if r2_usable else 0.0
    if escalation_rate <= ROUTING_CALIBRATION_LOW_ESCALATION_RATE and success_rate >= ROUTING_CALIBRATION_MIN_R2_SUCCESS_RATE:
        candidate = "no change"
        detail = (
            "In the observed verified sample the authored R2 path completed required verification without "
            "R3 escalation at a rate consistent with the current default. Keeping the R2 default and the "
            "current R3 hard-trigger list is a defensible manual decision. This is not a counterfactual claim "
            "about work that ran directly at R3."
        )
    elif escalation_rate >= ROUTING_CALIBRATION_HIGH_ESCALATION_RATE:
        candidate = "review: recorded R2->R3 escalations are frequent"
        detail = (
            "Authored R2 observations escalated to R3 often enough to review manually whether a recorded "
            "escalation reason should become an authored R3 hard trigger for the affected task families. "
            "Inspect the recorded_reasons and per-family breakdown; escalation reasons without recorded text "
            "are not evidence for a specific trigger."
        )
    else:
        candidate = "no confident change; monitor"
        detail = (
            "The sample is adequate in size but the escalation and R2 success signals are mixed. Continue "
            "accumulating verified observations and re-run before adjusting the rubric."
        )
    return {
        "candidate_decision": candidate,
        "detail": detail,
        "requires_separate_managed_change": requires_managed_change,
    }


def routing_calibration(root: Path) -> dict[str, Any]:
    """Bounded read-only calibration of the R2/R3 routing rubric.

    Reuses the efficiency-baseline routing-record scanner and the existing
    OpenSpec verification receipt lookup. It separates the authored route from
    the actual execution path, never makes a counterfactual claim, and either
    produces a concrete human-readable candidate policy decision or an honest
    ``insufficient evidence`` result. It changes no routing policy.
    """
    records = _local_routing_records(root)
    verification_by_record = [(record, _verification_outcome(root, record)) for record in records]
    observations = [_calibration_observation(root, record, verification) for record, verification in verification_by_record]

    launched = [observation for observation in observations if observation["launched"]]
    verified = [observation for observation in observations if observation["verification"] == "passed"]
    verification_signals: dict[str, int] = {}
    for _record, label in verification_by_record:
        verification_signals[label] = verification_signals.get(label, 0) + 1

    global_slice = _calibration_slice(observations)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "scope": "local routing/execution provenance",
        "sample": {
            "routing_records": len(records),
            "planned_only_routes": len(records) - len(launched),
            "launched_executions": len(launched),
            "verified_executions": len(verified),
            "usable_observations": global_slice["usable_observations"],
            "minimum_decision_quality_observations": ROUTING_CALIBRATION_MIN_OBSERVATIONS,
            "adequacy": global_slice["adequacy"],
        },
        "verification_signals": verification_signals,
        "unavailable_signals": {
            "first_pass_verification": "No deterministic first-pass-vs-retry field exists in current routing records.",
            "human_intervention": "No deterministic human-intervention field exists in current routing records.",
        },
        "global": global_slice,
        "breakdowns": {
            "task_family": _breakdown(observations, "task_family"),
            "rubric_version": _breakdown(observations, "rubric_version"),
            "provider_model_generation": _breakdown(observations, "provider_model_generation"),
        },
    }
    report["advice"] = _calibration_advice(report)
    return report


# --------------------------------------------------------------------------
# Read-only context delegation
# --------------------------------------------------------------------------
# This is intentionally adjacent to, rather than inside, the writer launch
# code above.  Context workers do not modify the repository and therefore do
# not acquire writer ownership or run write-containment ceremony.  Their small
# observations live on the existing Route record so calibration has one local
# provenance lifecycle to inspect.
CONTEXT_DELEGATION_SCHEMA_VERSION = 1
CONTEXT_CONFIDENCES = ("high", "medium", "low")
CONTEXT_OUTCOMES = ("completed", "fallback", "low-confidence", "runtime-unavailable")
CONTEXT_MAX_SCOPE_ITEMS = 50
CONTEXT_MAX_EVIDENCE_ITEMS = 25
CONTEXT_MAX_QUESTION_CHARS = 4000
CONTEXT_MAX_SYNTHESIS_CHARS = 2000
CONTEXT_MAX_FINDING_CHARS = 1200
CONTEXT_MAX_UNCERTAINTY_CHARS = 800


class ContextDelegationError(RoutingError):
    """A context request or worker result is not safe enough to trust."""


def _context_enabled(root: Path) -> bool:
    settings = read_platform_config(root).get("context_delegation", {})
    return isinstance(settings, dict) and settings.get("enabled") is True


def _context_nonempty_string(value: Any, label: str, *, limit: int = CONTEXT_MAX_FINDING_CHARS) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextDelegationError(f"context delegation {label} must be a non-empty string")
    result = value.strip()
    if len(result) > limit:
        raise ContextDelegationError(f"context delegation {label} exceeds the {limit}-character bound")
    return result


def _context_scope(root: Path, value: Any) -> list[dict[str, Any]]:
    """Validate a bounded list of repository-relative text ranges.

    Resolving every path before the worker starts makes the passed scope
    inspectable and prevents a symlink from quietly expanding the advertised
    repository boundary.  The worker's read-only sandbox protects writes; the
    explicit scope is the semantic/read budget supplied to the worker.
    """
    if not isinstance(value, list) or not value:
        raise ContextDelegationError("context delegation request needs a non-empty scope list")
    if len(value) > CONTEXT_MAX_SCOPE_ITEMS:
        raise ContextDelegationError(f"context delegation scope exceeds {CONTEXT_MAX_SCOPE_ITEMS} items")
    root_resolved = root.resolve()
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ContextDelegationError(f"context delegation scope item {index} must be an object")
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ContextDelegationError(f"context delegation scope item {index} needs a relative path")
        candidate = Path(raw_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ContextDelegationError(f"context delegation scope item {index} path must stay inside the repository")
        resolved = (root / candidate).resolve()
        try:
            relative = resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ContextDelegationError(f"context delegation scope item {index} escapes the repository") from exc
        if not resolved.is_file():
            raise ContextDelegationError(f"context delegation scope item {index} is not a readable file: {relative}")
        start = item.get("start_line")
        end = item.get("end_line")
        if start is not None and (not isinstance(start, int) or isinstance(start, bool) or start < 1):
            raise ContextDelegationError(f"context delegation scope item {index} start_line must be a positive integer")
        if end is not None and (not isinstance(end, int) or isinstance(end, bool) or end < 1):
            raise ContextDelegationError(f"context delegation scope item {index} end_line must be a positive integer")
        if start is not None and end is not None and end < start:
            raise ContextDelegationError(f"context delegation scope item {index} end_line precedes start_line")
        entry = {"path": relative.as_posix()}
        if start is not None:
            entry["start_line"] = start
        if end is not None:
            entry["end_line"] = end
        identity = (entry["path"], entry.get("start_line"), entry.get("end_line"))
        if identity not in seen:
            normalized.append(entry)
            seen.add(identity)
    return normalized


def context_request(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Normalize the provider-neutral, question-directed worker input."""
    if not isinstance(request, dict):
        raise ContextDelegationError("context delegation request must be a JSON object")
    return {
        "question": _context_nonempty_string(request.get("question"), "question", limit=CONTEXT_MAX_QUESTION_CHARS),
        "scope": _context_scope(root, request.get("scope")),
    }


def _context_payload(root: Path, scope: list[dict[str, Any]]) -> dict[str, Any]:
    """Count the exact selected source text without retaining any of it."""
    files: list[dict[str, Any]] = []
    total_lines = 0
    total_bytes = 0
    for entry in scope:
        path = root / entry["path"]
        try:
            lines = path.read_bytes().splitlines(keepends=True)
        except OSError as exc:
            raise ContextDelegationError(f"cannot read delegated context source {entry['path']}: {exc}") from exc
        start = entry.get("start_line", 1)
        end = entry.get("end_line", len(lines))
        assert isinstance(start, int) and isinstance(end, int)
        selected = lines[start - 1 : end]
        item = {
            "path": entry["path"],
            "start_line": start,
            "end_line": min(end, len(lines)),
            "lines": len(selected),
            "bytes": sum(len(line) for line in selected),
        }
        files.append(item)
        total_lines += item["lines"]
        total_bytes += item["bytes"]
    return {"lines": total_lines, "bytes": total_bytes, "files": files}


def _context_unknown_reread() -> dict[str, Any]:
    return {"lines": None, "bytes": None, "status": "unknown"}


def _context_usage_unknown() -> dict[str, dict[str, Any]]:
    return efficiency_unknown_usage()


def _context_observation(
    route: Route,
    root: Path,
    request: dict[str, Any],
    *,
    outcome: str,
    limitation: str | None = None,
    result: dict[str, Any] | None = None,
    result_raw: bytes | None = None,
    started_at: str | None = None,
    elapsed_ms: int | None = None,
    usage: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if outcome not in CONTEXT_OUTCOMES:
        raise ContextDelegationError(f"unsupported context delegation outcome: {outcome}")
    observation: dict[str, Any] = {
        "schema_version": CONTEXT_DELEGATION_SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "recorded_at": utc_now(),
        "provider": route.provider,
        "profile": "routine",
        "model": _model_provenance(_model_for(read_platform_config(root), route.provider, "routine"), SOURCE_SELECTED),
        # The question is transient worker input and may itself contain
        # sensitive repository context. Retain only its bounded size plus
        # the scope identity needed for later aggregation; never the prompt
        # text or a reconstruction of it.
        "request": {"question_chars": len(request["question"]), "scope": request["scope"]},
        "source_payload": _context_payload(root, request["scope"]),
        "outcome": outcome,
        "fallback": {"direct_read_available": True, "reason": limitation},
        "reread_payload": _context_unknown_reread(),
        "usage": usage if usage is not None else _context_usage_unknown(),
    }
    if started_at is not None and elapsed_ms is not None:
        observation["timing"] = efficiency_timing(started_at, elapsed_ms)
    else:
        observation["timing"] = {"elapsed_ms": None, "source": SOURCE_UNKNOWN, "status": "unknown"}
    if result is not None:
        observation["result"] = result
    if result_raw is not None:
        observation["returned_payload"] = {
            "lines": len(result_raw.splitlines()),
            "bytes": len(result_raw),
        }
    else:
        observation["returned_payload"] = {"lines": None, "bytes": None, "status": "unknown"}
    return observation


def _context_result(raw: bytes, scope: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate a compact worker answer, never an arbitrary transcript."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContextDelegationError("context worker did not return the required structured JSON evidence") from exc
    if not isinstance(value, dict):
        raise ContextDelegationError("context worker result must be a JSON object")
    confidence = value.get("confidence")
    if confidence not in CONTEXT_CONFIDENCES:
        raise ContextDelegationError("context worker result confidence must be high, medium, or low")
    synthesis = _context_nonempty_string(value.get("synthesis"), "result synthesis", limit=CONTEXT_MAX_SYNTHESIS_CHARS)
    findings = value.get("findings")
    if not isinstance(findings, list) or len(findings) > CONTEXT_MAX_EVIDENCE_ITEMS:
        raise ContextDelegationError(f"context worker result needs at most {CONTEXT_MAX_EVIDENCE_ITEMS} findings")
    allowed_paths = {item["path"] for item in scope}
    normalized: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise ContextDelegationError(f"context worker finding {index} must be an object")
        path = finding.get("path")
        if path not in allowed_paths:
            raise ContextDelegationError(f"context worker finding {index} cites a path outside the requested scope")
        item: dict[str, Any] = {
            "path": path,
            "finding": _context_nonempty_string(finding.get("finding"), f"finding {index}", limit=CONTEXT_MAX_FINDING_CHARS),
            "uncertainty": _context_nonempty_string(finding.get("uncertainty"), f"finding {index} uncertainty", limit=CONTEXT_MAX_UNCERTAINTY_CHARS),
        }
        symbol = finding.get("symbol")
        if symbol is not None:
            item["symbol"] = _context_nonempty_string(symbol, f"finding {index} symbol", limit=500)
        for field in ("start_line", "end_line"):
            number = finding.get(field)
            if number is not None:
                if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                    raise ContextDelegationError(f"context worker finding {index} {field} must be a positive integer")
                item[field] = number
        if item.get("start_line") and item.get("end_line") and item["end_line"] < item["start_line"]:
            raise ContextDelegationError(f"context worker finding {index} end_line precedes start_line")
        normalized.append(item)
    return {"confidence": confidence, "synthesis": synthesis, "findings": normalized}


def _context_prompt(request: dict[str, Any]) -> str:
    """Bound the worker's task and forbid source/transcript output explicitly."""
    scope = "\n".join(
        f"- {item['path']}"
        + (f":{item['start_line']}-{item.get('end_line', 'EOF')}" if "start_line" in item else "")
        for item in request["scope"]
    )
    return (
        "You are a read-only repository context worker. Answer only the stated question from the bounded "
        "repository scope. Do not edit files, run write commands, inspect paths outside the scope, or return "
        "source excerpts/transcripts. Return compact JSON matching the supplied schema. Each finding must cite a "
        "scoped path and state uncertainty.\n\nQuestion:\n"
        f"{request['question']}\n\nAllowed scope:\n{scope}"
    )


def _context_result_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["confidence", "synthesis", "findings"],
        "properties": {
            "confidence": {"type": "string", "enum": list(CONTEXT_CONFIDENCES)},
            "synthesis": {"type": "string", "maxLength": CONTEXT_MAX_SYNTHESIS_CHARS},
            "findings": {
                "type": "array",
                "maxItems": CONTEXT_MAX_EVIDENCE_ITEMS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path", "finding", "uncertainty"],
                    "properties": {
                        "path": {"type": "string"}, "symbol": {"type": "string", "maxLength": 500},
                        "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1},
                        "finding": {"type": "string", "maxLength": CONTEXT_MAX_FINDING_CHARS},
                        "uncertainty": {"type": "string", "maxLength": CONTEXT_MAX_UNCERTAINTY_CHARS},
                    },
                },
            },
        },
    }


def _append_context_observation(root: Path, route: Route, observation: dict[str, Any]) -> None:
    route_path = _record_path(root, route.change)
    next_route = Route(**{**asdict(route), "context_delegations": route.context_delegations + (observation,)})
    _write_route(route_path, next_route)
    # Context observations may be useful after task-worktree cleanup just as
    # execution evidence is. This is a mirror of the same record, not a new
    # store, and it is safe even when no writer executor launched.
    _write_route(_durable_record_path(next_route), next_route)


def delegate_codex_context(root: Path, request_input: dict[str, Any], *, codex_bin: str | None = None) -> dict[str, Any]:
    """Launch a routine-profile Codex worker with the native read-only sandbox.

    Failure is intentionally represented as a completed local observation and
    an available direct-read fallback. A missing executable, failed process,
    malformed answer, or low confidence never masquerades as delegation.
    """
    route, _ = _read_route(root)
    request = context_request(root, request_input)
    if route.provider != "codex":
        raise ContextDelegationError("a Codex context worker requires a Codex parent route")
    if not _context_enabled(root):
        observation = _context_observation(route, root, request, outcome="runtime-unavailable", limitation="context delegation is not enabled in this repository")
        _append_context_observation(root, route, observation)
        return observation
    started_at = _platform_timestamp()
    started_tick = time.perf_counter_ns()
    worker = codex_bin or "codex"
    try:
        with tempfile.TemporaryDirectory(prefix="dev-platform-context-") as temporary:
            temporary_root = Path(temporary)
            schema_path = temporary_root / "context-result-schema.json"
            result_path = temporary_root / "context-result.json"
            schema_path.write_text(json.dumps(_context_result_schema()), encoding="utf-8")
            argv = [
                worker, "exec", "--sandbox", "read-only", "--cd", str(root.resolve()), "--ephemeral", "--json",
                "--model", _model_for(read_platform_config(root), "codex", "routine"), "--output-schema", str(schema_path),
                "--output-last-message", str(result_path), _context_prompt(request),
            ]
            completed = subprocess.run(argv, text=True, capture_output=True, check=False, timeout=120)
            raw = result_path.read_bytes() if result_path.is_file() else None
    except FileNotFoundError:
        elapsed = max(0, round((time.perf_counter_ns() - started_tick) / 1_000_000))
        observation = _context_observation(route, root, request, outcome="runtime-unavailable", limitation=f"Codex context runtime is unavailable: {worker}", started_at=started_at, elapsed_ms=elapsed)
    except subprocess.TimeoutExpired:
        elapsed = max(0, round((time.perf_counter_ns() - started_tick) / 1_000_000))
        observation = _context_observation(route, root, request, outcome="fallback", limitation="Codex context worker timed out; use a direct targeted read", started_at=started_at, elapsed_ms=elapsed)
    except OSError as exc:
        elapsed = max(0, round((time.perf_counter_ns() - started_tick) / 1_000_000))
        observation = _context_observation(route, root, request, outcome="runtime-unavailable", limitation=f"Codex context runtime could not start: {exc}", started_at=started_at, elapsed_ms=elapsed)
    else:
        elapsed = max(0, round((time.perf_counter_ns() - started_tick) / 1_000_000))
        if completed.returncode != 0 or raw is None:
            # Do not retain worker stdout/stderr: it can contain repository
            # context or an echoed prompt. The bounded exit condition is
            # sufficient to explain why the parent must read directly.
            detail = (
                f"Codex context worker exited with status {completed.returncode}"
                if completed.returncode != 0
                else "Codex context worker did not produce structured evidence"
            )
            observation = _context_observation(route, root, request, outcome="fallback", limitation=detail, started_at=started_at, elapsed_ms=elapsed)
        else:
            try:
                result = _context_result(raw, request["scope"])
            except ContextDelegationError as exc:
                observation = _context_observation(route, root, request, outcome="fallback", limitation=str(exc), started_at=started_at, elapsed_ms=elapsed)
            else:
                outcome = "low-confidence" if result["confidence"] == "low" else "completed"
                limitation = "worker evidence is low confidence; use a direct targeted read" if outcome == "low-confidence" else None
                usage_events = [
                    usage_event
                    for line in getattr(completed, "stdout", "").splitlines()
                    if (usage_event := _codex_usage_from_line(line)) is not None
                ]
                observation = _context_observation(route, root, request, outcome=outcome, limitation=limitation, result=result, result_raw=raw, started_at=started_at, elapsed_ms=elapsed, usage=_codex_usage_evidence(usage_events))
    _append_context_observation(root, route, observation)
    return observation


def delegate_claude_context(root: Path, request_input: dict[str, Any]) -> dict[str, Any]:
    """Record the current Claude Code limitation without inventing a boundary.

    The native Agent handoff can run in place but does not expose a supported
    read-only permission/sandbox parameter. An instruction alone is not a
    write boundary, so this version deliberately falls back instead of
    producing an unsafe handoff definition.
    """
    route, _ = _read_route(root)
    request = context_request(root, request_input)
    if route.provider != "claude":
        raise ContextDelegationError("a Claude context worker requires a Claude parent route")
    limitation = (
        "Claude Code's current native Agent handoff has no supported read-only permission boundary; "
        "the platform retained direct targeted reading rather than launching a write-capable child"
    )
    if not _context_enabled(root):
        limitation = "context delegation is not enabled in this repository"
    observation = _context_observation(route, root, request, outcome="runtime-unavailable", limitation=limitation)
    _append_context_observation(root, route, observation)
    return observation


def record_context_reread(root: Path, observation_id: str, scope_input: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach an explicitly observable later direct-read volume to one observation."""
    route, route_path = _read_route(root)
    if not observation_id.strip():
        raise ContextDelegationError("context reread recording requires a non-empty observation id")
    scope = _context_scope(root, scope_input)
    observations = list(route.context_delegations)
    for index, observation in enumerate(observations):
        if observation.get("id") != observation_id.strip():
            continue
        updated = dict(observation)
        updated["reread_payload"] = _context_payload(root, scope)
        observations[index] = updated
        next_route = Route(**{**asdict(route), "context_delegations": tuple(observations)})
        _write_route(route_path, next_route)
        _write_route(_durable_record_path(next_route), next_route)
        return updated
    raise ContextDelegationError(f"no context delegation observation has id {observation_id!r}")


def _context_json_file(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextDelegationError(f"{label} file does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextDelegationError(f"{label} file is not readable JSON: {path}") from exc


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
    retained_parser = subparsers.add_parser(
        "record-retained-execution",
        help="record a completed policy-valid parent-retained execution with containment evidence",
    )
    retained_parser.add_argument("--reason", required=True)
    recover_parser = subparsers.add_parser(
        "recover-external-advance",
        help="narrowly reviewed recovery for a historic pure-head-move containment false positive",
    )
    recover_parser.add_argument("--friction-event", required=True, help="exact machine-local friction log entry id, never a GitHub issue number")
    recover_parser.add_argument("--before-head", required=True)
    recover_parser.add_argument("--after-head", required=True)
    verify_parser = subparsers.add_parser(
        "verify-routing",
        help="verify durable exact-task routing evidence without preparing or dispatching a route",
    )
    verify_parser.add_argument("--source-issue", required=True)
    verify_parser.add_argument("--change", required=True)
    codex_context_parser = subparsers.add_parser(
        "context-codex",
        help="softly delegate one bounded repository question to a routine read-only Codex worker",
    )
    codex_context_parser.add_argument("--request", type=Path, required=True, help="JSON object with question and bounded scope")
    codex_context_parser.add_argument("--codex-bin")
    claude_context_parser = subparsers.add_parser(
        "context-claude",
        help="record the native Claude read-only-context capability or its truthful direct-read fallback",
    )
    claude_context_parser.add_argument("--request", type=Path, required=True, help="JSON object with question and bounded scope")
    reread_context_parser = subparsers.add_parser(
        "context-reread",
        help="attach an explicitly observed targeted direct re-read volume to a context observation",
    )
    reread_context_parser.add_argument("--id", required=True, help="context observation id")
    reread_context_parser.add_argument("--scope", type=Path, required=True, help="JSON list of bounded path/range objects")
    subparsers.add_parser("postcheck", help="verify the prepared native worktree route did not mutate integration")
    subparsers.add_parser("efficiency-baseline", help="report bounded local execution-efficiency evidence without changing routing")
    subparsers.add_parser("routing-calibration", help="report bounded read-only R2/R3 routing calibration evidence without changing routing")
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
        elif args.command == "record-retained-execution":
            output = record_retained_execution(root, reason=args.reason)
        elif args.command == "recover-external-advance":
            output = recover_external_advance(
                root, friction_event=args.friction_event, before_head=args.before_head, after_head=args.after_head
            )
        elif args.command == "verify-routing":
            output = asdict(require_routing_gate(root, args.source_issue, args.change))
        elif args.command == "context-codex":
            output = delegate_codex_context(root, _context_json_file(args.request, "context request"), codex_bin=args.codex_bin)
        elif args.command == "context-claude":
            output = delegate_claude_context(root, _context_json_file(args.request, "context request"))
        elif args.command == "context-reread":
            output = record_context_reread(root, args.id, _context_json_file(args.scope, "context reread scope"))
        elif args.command == "efficiency-baseline":
            output = efficiency_baseline(root)
        elif args.command == "routing-calibration":
            output = routing_calibration(root)
        else: output = postcheck(_read_route(root)[0])
    except (ContainmentError, RoutingError) as exc:
        print(f"Model routing blocked: {exc}", file=sys.stderr); return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.command == "run-codex" and _failed_codex_execution(output):
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
