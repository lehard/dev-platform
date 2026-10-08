## Why

Routing is currently only judged at the end. `route-claude` records a route and prints a native Agent hand-off, but nothing stops the supervisor from writing the implementation itself. The mismatch first surfaces at archive (`openspec_lifecycle.require_managed_routing_evidence` -> `model_routing.require_routing_gate`) after the expensive checks have run. The only way out then is to record a `claimed` child execution after the fact or to escalate to R3 without a real trigger, which launders finished supervisor work as delegated execution. For the policy-permitted retained cases (`complex`, `parent-only-topology`) the retained outcome is likewise declared only after implementation, so the platform has no truthful owner of the work while it happens.

## What Changes

- Route preparation (`route-claude`, `route-codex`, `model_routing.prepare`) records an explicit `execution_plan`: `delegated-child` (policy requires a child executor) or `supervisor-retained` (policy permits supervisor execution, with the policy reason). The plan is derived from existing `_retention_policy`, never chosen by the caller, and is distinct from the authored recommended tier and from the later actual execution outcome.
- Route time records a task-content pre-snapshot of the assigned task worktree and refuses to route if task content already diverged from the materialized managed package.
- Claude gains an explicit pre-launch step (`begin-claude-delegation`, via `dogfood_task.py` too) that opens a delegation before the native Agent call. `record-claude-execution` requires that open delegation and closes it; it never records after the fact and remains self-reported (`launched` never true).
- A shared early gate (`require_early_routing_gate`) fails closed when the plan is `delegated-child`, no delegation is open or closed with execution evidence, and task content differs from the pre-snapshot. It runs in `dogfood_task.py status`/`finish`, the check/test entrypoints, and `verify-routing`, in addition to the existing archive gate.
- A `supervisor-retained` plan declared up front is the precondition of `record-retained-execution`, which then only finalizes it with the postcheck. A late attempt to switch plans after content changed, or to escalate without a real recorded delegation, is refused.
- Codex stays platform-launched; its dispatch opens the delegation record itself, so the plan field is consistent across providers.
- `docs/engineering/model-routing.md` documents the plan, the mandatory pre-launch step and the early gate.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-routing`: execution path is fixed and gated before task-content mutation; retained execution is declared up front; recovery never fabricates delegation evidence.

## Impact

`template/scripts/model_routing.py` (plan, delegation, early gate, CLI), `scripts/dogfood_task.py` (new command, early gate in status/finish), the check/test entrypoint wiring, `docs/engineering/model-routing.md` and `tests/test_model_routing.py`/dogfood tests. Rendered downstream projects receive the template change through the normal Copier update; provider-specific editor hooks are not introduced.

## Success Criteria

A required child executor cannot be bypassed by supervisor-written implementation without a failing lifecycle command well before archive; a permitted supervisor path is a real retained outcome declared up front; no recovery path can legalize finished work with fabricated evidence.

## Non-goals

Hard proof of Claude launch, a provider-specific editor hook or sandbox, R1 economy routing, changing the start-tier rubric or `_retention_policy` rules, other BR-415 Requirements, stable tagging and fleet rollout.
