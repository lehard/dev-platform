## Why
Today path overlap blocks a candidate and the original agent must correct and re-finish; retrospective, friction attribution, terminal reconciliation and cleanup require the developer session (BR-341 items 2 and 6).

## What Changes
- Ready candidates integrate sequentially: clean merge of current main, required checks on the actual candidate, expected-head merge; overlap alone no longer blocks.
- Real conflicts or failing integration checks create bounded integration-repair jobs; changed task content returns through review and finalization; unchanged identity reuses evidence.
- After the bound a candidate is blocked and the queue continues with the next ready candidate.
- Review/repair/integration/fallback/retry events are recorded automatically as friction attributed to the candidate task and its Requirement; a retrospective job produces checkpoints; terminal reconciliation and safe local cleanup run as worker jobs.

## Capabilities
### Modified Capabilities
- `publication-queue`: integration contour, non-blocking queue.
- `platform-lifecycle`: inherited finish obligations.

## Impact
`publication_queue.py` worker, `agent_friction.py`, `requirement_retrospective.py`, `requirement_terminal.py`, `worktree_cleanup.py` jobs.

## Outcome and Evidence
Fixtures: overlapping but clean candidates merge; a conflict is repaired and re-reviewed; a blocked candidate does not stop the next; terminal state and retrospectives are complete without manual passes.

## Non-goals
Speculative or batched integration.
