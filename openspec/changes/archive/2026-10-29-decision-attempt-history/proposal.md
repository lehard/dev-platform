## Why

The problem "main advanced, so reconcile and rerun full validation" was attacked at least eight times (recover-shared-candidate-after-main-advance, relevant-drift-and-transient-retry, finalize-proven-base, handoff-behind-disjoint-main, reuse-archive-check-evidence-at-portable-finish, handoff-mergeable-task-base, queue-regenerates-generated-files, reuse-check-evidence-unchanged-task-content, plus BR-774 and BR-777), and no change links the earlier ones. Quick tasks were excluded from scope twice and the agent board was never considered, which OpenSpec archives do not show. `docs/decisions/` held three records, and an owner's choice between variants survived only as a quote in a `design.md`, without the rejected option. The owner chose on 2026-10-23 to link the existing surfaces (variant A) instead of a separate problems registry or a fifth OpenSpec artifact.

## What Changes

- Rule 1 (problem record): a second or later attempt links the friction root issue in its Requirement and appends to it the change, what it did, why it was not enough and what stayed out of scope. Written in `docs/engineering/agent-workflow.md`, `docs/engineering/task-intake.md` and the `requirement-authoring` capability.
- Rule 2 (decision record): an owner choice between options or a hard-to-reverse decision goes to `docs/decisions/` with rejected options and revisit triggers; `design.md` links the record. The record threshold in `docs/decisions/README.md` says so.
- Rule 3 (look before proposing): before a proposal the agent searches the related root issue and decision records and links them in `proposal.md`. Written in `docs/engineering/openspec-workflow.md`.
- `docs/decisions/0004-main-advance-revalidation.md`: every attempt with links, the current choice (one task-base classifier for every gate), rejected options, revisit triggers.
- Root issue lehard/dev-platform#553 receives the list of attempts.
- Specs gain no rationale and DEC records restate no requirement.

## Impact

- Docs only: `docs/engineering/agent-workflow.md`, `docs/engineering/task-intake.md`, `docs/engineering/openspec-workflow.md`, `docs/decisions/README.md`, `docs/decisions/0004-main-advance-revalidation.md`, `dev-platform/capabilities/requirement-authoring.md` and its template copy, `template/dev-platform/platform-manifest.json`.
- One GitHub comment on the public root issue, with no private Backlog references.
