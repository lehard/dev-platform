# Design: One combined trigger for Process and Architecture Health Review

## Boundary

`platform-health-review` is a trigger/orchestration capability, not a review engine. It does not re-implement or change either existing review's reasoning; it only defines when both reviews run together and records that they are presented to a human as one combined function.

## Execution model

Two implementation shapes are both consistent with this design and left to implementation-time choice, provided the observable behavior (one schedule, one manual dispatch, both reviews run) holds:

- extend the existing `weekly-process-backlog-review` gh-aw workflow to also invoke the architecture-health job in the same run, or
- keep both as separate gh-aw workflows sharing one identical schedule/dispatch definition, started together.

Either way, each review keeps its own engine, tools, safe-outputs declaration, and cost/runtime guardrails unchanged; only the trigger is shared/aligned.

## Compatibility and rollback

Existing standalone manual dispatch of either review (if retained as a separate trigger) continues to work. Reverting this change restores two independently triggered reviews with no data/state migration.

## Risks and mitigations

- Risk: combining triggers could accidentally couple failure modes (one review's failure blocking the other). Mitigation: each review keeps its own job/workflow boundary and safe-outputs declaration; a failure in one must not prevent the other's run or its own safe output.
- Risk: doubled AI-credit spend per combined run. Mitigation: guardrails remain per-review as already accepted for each; this change does not raise either review's individual budget.
