## Why
The queue knows only queued/active/blocked for archived PRs. The new lifecycle needs review, repair, finalization and integration states that survive agent loss, plus a record of what was verified so the next executor does not reconstruct it from chat (BR-341 retrospective item 5).

## What Changes
- Extend the GitHub-backed queue with durable candidate states: review-pending, reviewing, repair-pending, repairing, finalize-pending, ready, integrating, integration-repair-pending, merged, blocked-retryable, blocked-escalation; existing queued/active/blocked map onto them with v1 compatibility.
- Every transition writes an immutable versioned marker comment that is also the handoff record: candidate head, task-content identity, satisfied gates with bound identity, red gate and evidence, not re-verified items, attempt counters, next job.
- A read-only status per candidate and per Requirement.

## Capabilities
### Modified Capabilities
- `publication-queue`: candidate state model, handoff record, status.

## Impact
`publication_queue.py`, `publication_state.py`, `dogfood_task.py status`, queue workflow labels. Merge behavior is unchanged in this child.

## Outcome and Evidence
State derivation tests from GitHub fixtures cover every state, restart recovery and v1 markers; status shows the handoff record.

## Non-goals
Launching jobs (bounded-worker-contract), changing review placement or integration semantics.
