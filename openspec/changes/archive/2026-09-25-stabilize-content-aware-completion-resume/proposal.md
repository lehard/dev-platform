# Proposal: Make completion resume content-aware and cheap

## Why

The managed completion path currently treats exact HEAD movement as if task content necessarily changed. Normal lifecycle actions such as archive commits, clean reconciliation with a newer base, armed auto-merge waiting, and post-merge local synchronization can therefore invalidate retrospective/validation evidence or re-enter expensive validation and publication logic even when the task-owned content is unchanged.

Repeated friction shows two coupled problems: freshness identity is too HEAD-specific, and resumable remote publication states are routed back through first-publication work. The result is avoidable full-suite repetition, repeated checkpoints and raw exceptions in states that are documented as normal and resumable.

## What Changes

- Define bounded task-content identity for completion evidence so expected lifecycle-only HEAD movement does not automatically make evidence stale.
- Reuse fresh validation/retrospective evidence only when equivalence is mechanically proven; any material task-content change remains stale.
- After exact-head PR/auto-merge intent is durably known, resume through cheap status/reconciliation rather than repeating full validation or publish mutation.
- Classify normal nonterminal remote states explicitly and never surface them as uncaught subprocess tracebacks.
- Keep fail-closed behavior when content/base/remote intent equivalence cannot be proven.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: evidence freshness and terminal resume semantics become content-aware and idempotent across expected lifecycle transitions.

## Impact

- Friction checkpoint freshness.
- Automated-check evidence reuse between archive/reconcile/finish.
- `finish_task.py` / `dogfood_task.py` resume and status behavior for armed auto-merge.
- Publication recovery diagnostics and regression tests.
