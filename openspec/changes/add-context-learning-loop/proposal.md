# Proposal: Add a context learning loop on existing friction evidence

## Why

Dev Platform already captures high-signal friction, deduplicates process evidence, requires a post-task retrospective, and runs Process Health Review. After a bounded project context pack exists, the missing step is to identify when an agent failure or user correction is specifically evidence of missing/incorrect project context and route that evidence toward a reviewed context improvement.

Creating a separate `failure-log.md` or automatically rewriting context after repeated failures would introduce competing state and unsafe self-modifying policy. The platform should extend the existing friction lifecycle instead.

## What Changes

- Allow existing friction evidence to classify a high-signal event as a `context-gap` with a bounded context concern/destination.
- Preserve sanitized evidence and a proposed improvement candidate without automatically changing canonical context.
- Keep repetition/deduplication provider- and model-independent so recurring root causes strengthen one signal.
- Teach Process Health Review to distinguish context gaps from tooling/process friction and surface bounded context-improvement candidates.
- Route accepted context improvements through the ordinary managed-task/OpenSpec lifecycle; no automatic task creation.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: process learning can represent and review project-context gaps without adding a second failure log or task system.

## Impact

- `agent_friction.py` event schema/classification and sanitization.
- Retrospective guidance and bounded evidence fields.
- Process Health Review grouping/classification.
- Regression coverage for deduplication, provider/model independence, and no automatic canonical writes/tasks.
