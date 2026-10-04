# Design: Claim the Requirement card at start

## Decision

Both seams call one shared helper, `requirement_board.claim_started`, which skips a terminal `Done` card and wraps failures with the kept-state and rerun message. It reuses `requirement_board.reconcile_nonterminal` (stage `pre-authoring` already maps to `In progress`). Call it from two seams:

1. `requirement_intake.main` for `start`, after `start_pre_authoring` returns, i.e. after `orchestrate_pre_authoring.init` wrote durable state. Validation (Issue fetch, body parse, target lifecycle) stays before the claim, so an invalid or unsupported Requirement is not claimed.
2. The beginning of `execute_requirement.advance`, before child discovery, duplicate checks and materialisation.

`requirement_board` imports `requirement_intake`, so the call is made from the CLI layer (`main`) rather than from `start_pre_authoring`, avoiding an import cycle and keeping `start_pre_authoring` free of Project side effects for callers that only need state.

## Failure semantics

- The reconcile is a no-op when the card already shows the desired status.
- If it fails after state init, `start` exits non-zero with a message that the Requirement has started and the command is safe to rerun; local state is not removed and nothing writes `Ready`.
- The projection only ever writes `In progress` or `Blocked`, never `Ready`, so a later error cannot restore a free-looking card.

## Alternatives rejected

- New intermediate status: excluded by the Requirement.
- Claiming before validation: would hold cards for Requirements that fail validation.
- Refusing a second `start` by card status alone: indistinguishable from the same agent resuming on another machine; the card status hides the item from the free queue, and resume stays idempotent.
