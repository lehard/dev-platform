## Context

- `_early_routing_gate` fails when a `delegated-child` plan has no real delegation and `_task_content_diverged` is non-empty; a `supervisor-retained` plan passes.
- `escalate` refuses that state; `record_retained_execution` requires a retained plan whose `policy` equals `_retention_policy(route)` (derived from profile and topology); `require_routing_gate` checks the retained execution's policy the same way.
- `_validate_execution_plan` validates the plan shape on every read.

## Decisions

1. **One explicit command.** `approve_supervisor_diff(root, *, approval, reason)` requires: a plan; non-empty `approval` and `reason`; mode `delegated-child`; no execution recorded; no real delegation (`_has_real_delegation` false; with a real delegation `escalate` is the path); `_require_recovery_safety` (integration containment still clean); and non-empty divergence (unchanged content means ordinary `escalate`). It writes `mode: supervisor-retained`, `policy: owner-approved`, `switched_from: {mode: delegated-child, at, delegation_recorded: false}` and `owner_approval: {approval, reason, approved_at, diverged_paths}`. Profile, escalations and delegation stay untouched, so nothing claims an escalation trigger or launch that did not happen. Every refusal writes nothing.
2. **Policy resolution.** `_retention_policy(route)` returns `owner-approved` when the plan carries that policy, otherwise the existing profile/topology policy. `_validate_execution_plan` accepts `owner-approved` only on a retained plan with a complete `owner_approval` (non-empty strings, non-empty path list) and a `switched_from` from a delegated-child plan without a recorded delegation; any other plan carrying `owner_approval` is invalid.
3. **Finalization.** `record_retained_execution` is unchanged except that for `owner-approved` it copies `owner_approval` into `execution.retained`. The archive gate then accepts the retained execution by the same policy equality check and additionally requires `execution.retained.owner_approval` to equal the plan's `owner_approval`; a record whose policy says `owner-approved` without the approval fails plan validation.
4. **Visibility.** `_actual_route_of` adds `owner_approved` (plan policy is `owner-approved`). The early gate, `escalate` and `record-retained-execution` refusals name `approve-supervisor-diff` as the explicit owner-decision path.

## Risks

- An agent could record an approval the owner did not give. The command cannot verify a human decision; the record is explicit, carries the owner's statement and is visible in reports, and the documentation requires an explicit owner decision in chat.

## Verification

Tests: success path then `record-retained-execution` and the archive gate pass with the approval in the execution; early gate passes after approval; refusals for empty approval, empty reason, already retained plan, real delegation, unchanged content, existing execution; invalid plan with `owner-approved` but no approval; report exposes `owner_approved`. Full platform checks.
