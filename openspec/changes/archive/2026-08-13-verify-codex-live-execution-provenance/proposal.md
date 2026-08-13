## Why

`adopt-gh-aw-process-automation` (`lehard/development-backlog#5`) implemented and archived truthful bounded execution provenance for model routing: `Route.supervisor`, `execution.participant`, explicit `selected`/`runtime-confirmed`/`unknown` source tracking for model/reasoning-effort, real `thread_id` extraction from `codex exec --json`, real `agent_id` capture from the Claude Agent tool, and friction/retrospective participant linking.

The Claude leg of real controlled acceptance was completed with a genuine live delegation. The Codex leg is implemented and unit-tested (the `--json` event-stream parser is exercised against realistic captured event lines) but was never exercised against a real `codex` CLI invocation, because the authenticated local account was rate-limited until 2026-08-18 -- confirmed live, not assumed. The owner decided not to hold the parent change open for this external wait and split it into this small, narrowly-scoped follow-up.

## What Changes

- No new behavior. This change performs one real controlled Codex delegation through the already-implemented `dogfood_task.py route-codex` -> `model_routing.py dispatch_codex()` -> `run_codex()` path and records the resulting truthful execution provenance as evidence.
- Extends the accepted `model-routing` spec with one explicit acceptance scenario for live Codex provenance capture (the requirement itself already exists; this adds the concrete scenario this change closes).

## Impact

- No runtime/template code changes are expected unless the live run surfaces a genuine defect in the already-implemented `--json` parsing path, in which case fix that defect as part of this change and record it truthfully rather than silently reinterpreting scope.
- Affected spec: `model-routing` (one added scenario, no requirement-text change).
