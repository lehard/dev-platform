# Design: Self-auditing completion feedback

## Decisions

1. **One verification contract.** Central and rendered workflow docs describe the same required verification receipt markers; parity is regression-tested.
2. **Preflight before archive mutation.** Missing required evidence is reported with the exact canonical requirement and actionable repair.
3. **Reuse lifecycle evidence.** Retrospective consumes existing bounded start/archive/publication/check outcomes where available; it does not create a transcript warehouse or duplicate task-status database.
4. **`none` requires review.** A known high-signal non-success in the current task must have a disposition: resolved-in-task, already-represented, or newly-recorded. Otherwise `none` is rejected.
5. **No duplicate friction.** Existing fingerprint/link evidence is reused rather than recording the same event twice.
6. **Clean path stays short.** Tasks with no meaningful non-success evidence can still complete a bounded retrospective and record `none` normally.
