## Why
Today the developer session runs review during archive, then archive, then publication, and stays responsible until merge. The developer should hand off at a verified PR and be free; review and repair must continue without that session.

## What Changes
- Developer completion becomes a handoff: selected/affected checks, semantic verify receipt for the active change, exact-head PR, developer friction checkpoint at the handoff head, admission as review-pending, writer claim released.
- Independent Review runs as a review job on the PR candidate with unchanged fresh-context read-only proof and two perspectives; fixable findings become repair jobs; a proposed rejection of a material finding or exhausted attempts become blocked-escalation.
- `[independent_review] providers = [...]` ordered fallback with requested/executed/reason evidence; all unavailable → blocked-retryable.
- Gate evidence (required checks, review) is bound to task-content identity and reused for unchanged content.
- AGENTS.md, openspec-workflow and agent-workflow describe the new order.

## Capabilities
### Modified Capabilities
- `completion-lifecycle`: reviewer readiness with explicit fallback; developer handoff; review and repair as candidate jobs; identity-bound evidence reuse.

## Impact
`finish_task.py`, `dogfood_task.py`, `independent_review*.py`, `openspec_lifecycle.py` (review no longer in archive preflight for coordinator-managed candidates), worker job kinds, AGENTS.md and docs.

## Outcome and Evidence
A developer finishes at PR and a later worker completes review; a fixable finding is repaired without the developer; provider fallback evidence is recorded; unchanged content reuses evidence.

## Non-goals
Finalization/archive placement (post-review-finalization), integration repair.
