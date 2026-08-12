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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from _platform_common import atomic_write_text, current_worktree_root, main_root, read_platform_config, utc_now
from delegated_write_guard import EnforcementTier, build_codex_argv, determine_codex_tier, run_observed_delegation
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
    escalations: tuple[dict[str, str], ...] = ()


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


def _managed_identity(root: Path) -> tuple[str, str]:
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
    return source_issue, change


def _record_path(root: Path, change: str) -> Path:
    return root / ".claude" / "model-routing" / f"{change}.json"


def _model_for(config: dict[str, Any], provider: str, profile: str) -> str:
    routing = config.get("model_routing", {})
    provider_policy = routing.get(provider, {}) if isinstance(routing, dict) else {}
    model = provider_policy.get(f"{profile}_model") if isinstance(provider_policy, dict) else None
    return model.strip() if isinstance(model, str) and model.strip() else DEFAULT_MODELS[provider][profile]


def _read_route(root: Path) -> tuple[Route, Path]:
    source_issue, change = _managed_identity(root)
    path = _record_path(root, change)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        route = Route(source_issue=payload["source_issue"], change=payload["change"], task_worktree=payload["task_worktree"], integration_root=payload["integration_root"], provider=payload["provider"], profile=payload["profile"], executor_model=payload["executor_model"], rationale=payload["rationale"], evidence=tuple(payload.get("evidence", [])), prepared_at=payload["prepared_at"], pre_snapshot=payload["pre_snapshot"], escalations=tuple(payload.get("escalations", [])))
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RoutingError(f"no readable routing record for managed change {change}; run prepare first") from exc
    if route.source_issue != source_issue or route.change != change:
        raise RoutingError("routing record provenance does not match the materialized managed task")
    return route, path


def _write_route(path: Path, route: Route) -> None:
    atomic_write_text(path, json.dumps(asdict(route), indent=2, sort_keys=True) + "\n")


def prepare(root: Path, *, provider: str, profile: str, rationale: str, evidence: list[str]) -> Route:
    if provider not in PROVIDERS or profile not in PROFILES:
        raise RoutingError("unknown provider or execution profile")
    if not rationale.strip():
        raise RoutingError("semantic routing preflight requires a non-empty rationale")
    source_issue, change = _managed_identity(root)
    integration = main_root().resolve()
    assigned = resolve_assigned_worktree(integration, root)
    route = Route(source_issue=source_issue, change=change, task_worktree=str(assigned), integration_root=str(integration), provider=provider, profile=profile, executor_model=_model_for(read_platform_config(root), provider, profile), rationale=rationale.strip(), evidence=tuple(evidence), prepared_at=utc_now(), pre_snapshot=_snapshot_to_dict(snapshot(integration)))
    _write_route(_record_path(root, change), route)
    return route


def escalation_context(route: Route) -> dict[str, Any]:
    return {"source_issue": route.source_issue, "change": route.change, "task_worktree": route.task_worktree, "profile": route.profile, "executor_model": route.executor_model, "rationale": route.rationale, "evidence": list(route.evidence), "escalations": list(route.escalations), "required_parent_actions": ["Review the child diff and all required check evidence in the assigned task worktree.", "Run postcheck after native Claude worktree delegation before reporting containment success.", "Escalate rather than broaden routine/standard work on material contract conflict, cross-cutting scope, low confidence, or bounded substantive verification failures."]}


def escalate(root: Path, reason: str) -> Route:
    route, path = _read_route(root)
    if route.profile == "complex":
        raise RoutingError("the route is already complex; retain the strong parent instead of escalating again")
    if not reason.strip():
        raise RoutingError("escalation requires a concrete reason")
    next_route = Route(**{**asdict(route), "profile": "complex", "executor_model": _model_for(read_platform_config(root), route.provider, "complex"), "escalations": route.escalations + ({"at": utc_now(), "from": route.profile, "reason": reason.strip()},)})
    _write_route(path, next_route)
    return next_route


def codex_argv(route: Route, prompt: str, codex_bin: str | None = None) -> tuple[list[str], str]:
    if route.provider != "codex":
        raise RoutingError("the prepared route is not a Codex route")
    decision = determine_codex_tier(codex_bin=codex_bin, integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree))
    if decision.tier is not EnforcementTier.HARD:
        raise RoutingError("native Codex containment is not provable for this route; retain execution on the parent or use an explicitly reviewed fallback: " + decision.detail)
    return build_codex_argv(codex_bin or "codex", Path(route.task_worktree), decision.tier, ["--model", route.executor_model, prompt]), decision.mechanism


def run_codex(route: Route, prompt: str, codex_bin: str | None = None) -> dict[str, Any]:
    argv, mechanism = codex_argv(route, prompt, codex_bin)
    # Codex workspace-write is the prevention layer. The legacy helper only
    # validates the assignment and observes/records the required post-check.
    decision = determine_codex_tier(codex_bin=codex_bin, require_hard=True, integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree))
    result = run_observed_delegation(integration_root=Path(route.integration_root), assigned_worktree=Path(route.task_worktree), argv=argv, tier_decision=decision, task=route.source_issue)
    return {"mechanism": mechanism, "returncode": result.returncode, "violation": result.violation}


def claude_agent(route: Route) -> dict[str, Any]:
    if route.provider != "claude":
        raise RoutingError("the prepared route is not a Claude route")
    return {"description": "Managed task executor; use only after supervisor routing preflight.", "model": route.executor_model, "effort": "medium" if route.profile == "routine" else "high", "isolation": "worktree", "maxTurns": 24, "prompt": "Work only in the native worktree assigned by Claude Code. Preserve the canonical OpenSpec and return the exact diff, checks run, uncertainty, and any escalation trigger to the supervisor. Managed source: " + route.source_issue + "; change: " + route.change + "; supervisor worktree: " + route.task_worktree + "."}


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
    prepare_parser.add_argument("--profile", choices=PROFILES, required=True)
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
    subparsers.add_parser("claude-agent", help="emit a native Claude Code worktree-agent definition")
    subparsers.add_parser("postcheck", help="verify the prepared native worktree route did not mutate integration")
    args = parser.parse_args()
    root = current_worktree_root()
    try:
        if args.command == "prepare": output: Any = asdict(prepare(root, provider=args.provider, profile=args.profile, rationale=args.rationale, evidence=args.evidence))
        elif args.command == "context": output = escalation_context(_read_route(root)[0])
        elif args.command == "escalate": output = asdict(escalate(root, args.reason))
        elif args.command == "codex-argv":
            argv, mechanism = codex_argv(_read_route(root)[0], args.prompt, args.codex_bin); output = {"argv": argv, "mechanism": mechanism}
        elif args.command == "run-codex": output = run_codex(_read_route(root)[0], args.prompt, args.codex_bin)
        elif args.command == "claude-agent": output = claude_agent(_read_route(root)[0])
        else: output = postcheck(_read_route(root)[0])
    except (ContainmentError, RoutingError) as exc:
        print(f"Model routing blocked: {exc}", file=sys.stderr); return 2
    print(json.dumps(output, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
