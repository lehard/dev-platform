# Proposal: Claim the Requirement card at start

## Why

Requirement development-backlog#333: the human-facing Requirement card is projected to `In progress` only from `execute_requirement.py advance`, after pre-authoring, duplicate checks and child materialisation. During that interval, which can be long or hang on GitHub calls, the card still reads `Ready` and a parallel agent can claim the same Requirement.

## What Changes

- `requirement_intake.py start` reconciles the primary card through the existing nonterminal projection immediately after pre-authoring state is durably initialised.
- `execute_requirement.py advance` reconciles the card at entry, so resuming an already started Requirement repairs a card that is still `Ready`, before any slow step.
- The reconciliation is idempotent. A reconciliation failure after the durable start is reported and the state is kept; the card is never rewritten to `Ready` and a retry converges.
- No new Project status, no new lifecycle ledger.

## Impact

`template/scripts/requirement_intake.py`, `template/scripts/execute_requirement.py`, `template/scripts/requirement_board.py` (if the shared helper needs a small seam), tests, `docs/engineering/task-intake.md`, and the `agent-workflow` spec. The change ships through the normal release and rollout to managed projects.
