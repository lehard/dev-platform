## Why
ADD freshness is exact HEAD equality, so any main commit makes an approved ADD stale and forces a re-approval. After children are materialized, Requirement advance and terminal reconciliation still require fresh pre-authoring; in BR-341 and BR-354 the delivery itself changed bound sources and blocked the terminal step, which was completed manually with `requirement_terminal.py reconcile`. Transient GitHub errors (connection reset, TLS timeout) stopped `advance` twice and needed manual reruns.

## What Changes
- ADD/intents/handoff freshness follows the snapshot's bound source identities instead of exact HEAD equality; irrelevant main movement keeps them fresh, a relevant source change still invalidates the dependent closure.
- Once a Requirement's children are materialized from handoffs, `execute_requirement.py advance` and terminal reconciliation use the linked children and their OpenSpec as canonical and no longer require fresh pre-authoring; a real contract conflict is reported explicitly.
- A shared bounded retry for classified transient GitHub/network failures in Requirement advance, terminal reconciliation and the publication queue.

## Capabilities
### Modified Capabilities
- `openspec-authoring`: pre-authoring freshness is source-bound.
- `platform-lifecycle`: post-handoff Requirement execution independence; transient GitHub retry.

## Impact
`add_intents.py`, `orchestrate_pre_authoring.py`, `execute_requirement.py`, `requirement_terminal.py`, `publication_queue.py`, a shared retry helper in `_platform_common.py`.

## Outcome and Evidence
Tests show an unrelated main commit keeps an approved ADD fresh while a change to a bound source makes it stale; a materialized Requirement advances and reaches terminal reconciliation after its own delivery changed bound sources; injected transient failures are retried within a bound and non-transient failures still fail closed.

## Non-goals
Coordinator states, workers and review placement (later children of BR-353).
