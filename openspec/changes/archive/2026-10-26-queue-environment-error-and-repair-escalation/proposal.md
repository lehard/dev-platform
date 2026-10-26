## Why

PR #730 waited about three hours in `integration-repair-pending`. The derived merge on the queue runner failed because PyYAML was not installed (fixed separately in #733), and the queue turned that environment failure into an integration-repair job. No executor runs repair jobs automatically (the sandboxed writer is macOS-only, DEC-0003), and nothing told the operator that a repair was waiting. The owner decided on 2026-10-26: an environment failure is an explicit queue error, and a repair that needs a writer is escalated to the operator, who runs it from chat.

## What Changes

- `post_review_finalization`: a new `RederivationEnvironmentFailed` (not a `RederivationFailed`) for a missing OpenSpec CLI, a regeneration command that cannot start, and a regeneration command that fails on a pristine checkout of main as well as on the merged tree (environment probe, run only after a failure).
- `publication_queue`: the derived merge maps it to `QueueEnvironmentError`; `_integrate` re-raises it without blocking or offering repair; the worker records it per candidate, still tries the rest, and ends the run with state `environment-error` (non-zero exit) naming every cause.
- `publication_queue`: entering `repair-pending` or `integration-repair-pending` posts one attention comment per exact round, "Repair needed: PR #N", with the reason, head, attempts and the `work-next` command the operator runs; a lost comment is posted on the next observation of the same round.
- Docs: placement row of `repair`/`integration-repair` in `docs/engineering/hosted-lifecycle-workers.md`.

## Impact

- `template/scripts/post_review_finalization.py`, `template/scripts/publication_queue.py`.
- Spec: publication-queue (modified "Declared generated files are regenerated on integration"; added "A writer-needing repair is escalated to the operator").
- Tests: `tests/test_post_review_finalization.py`, publication-queue tests.
