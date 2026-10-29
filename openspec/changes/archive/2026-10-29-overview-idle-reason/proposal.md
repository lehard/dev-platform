## Why

The overview reports exceptions and attempt counters, but a quiet candidate with no executing job shows only `expected automation`, which does not say who must move it. On 2026-10-28 PR #766 waited 8 h 41 min for an `integration-repair` job that only an operator-run local macOS node executes, and the cause was visible only after manual analysis (BR-889). The owner decided to take it.

## What Changes

- `assess_candidate` adds an `idle` object to every assessed candidate: `null` when the candidate is not open or a claim is executing; otherwise `{kind, waiting_for, moved_by, evidence}`.
- Reasons are derived only from fields the assessment already reads: lifecycle state, offered job and its claim, hosted-vs-local class of the job kind, attempt counters against their code limits, red gate and Requirement composition state. No new GitHub read.
- Known reasons: no coordinator record yet (developer), unclaimed/expired job executed by a hosted worker, unclaimed/expired job executed only by the local operator node (macOS), waiting for the publication queue, waiting for Requirement composition, retry pending, attempt limit exhausted, escalation awaiting a human.
- Anything else is `kind: unknown` with the state it could not explain.
- `render_candidate` prints one `idle:` line; JSON output carries the object.

## Impact

- `template/scripts/lifecycle_overview.py`, `tests/test_lifecycle_overview.py`.
- Spec: chat-coordinator (added requirement). Docs: `docs/engineering/chat-coordinator.md`.
