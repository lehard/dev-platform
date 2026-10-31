## Context

`_supersession` (admission with a handoff over an earlier admitted head) requires the newest trusted record to be bound to the proven head in a `READMISSION_STATES` state, the same task identity, no live claim on the record's offered job (`lifecycle_workers.build_job` + `winning_claim`), and ancestry of the new head. `_awaiting_readmission` uses the same set to report a moved head as waiting for developer re-admission instead of integrating or blocking it. `local_status` and `semantic_readmission` use `_awaits_developer_fix` (`DEVELOPER_FIX_STATES`) to accept a local descendant fix and to re-open an archived change for `finish` (`pr_review_gate.archived_readmission`).

## Decisions

- **Add the state, keep the guards.** `finalize-pending` is added to both sets. `build_job` already derives the finalize job for a `finalize-pending` record, so a live finalize claim refuses the handoff by name; ancestry and same-task checks are unchanged. Rejected: a separate finalize-only supersession path (duplicates the guards) and a coordinator-only admit (the developer path must work).
- **Finalize is head-bound.** A finalize job for the proven head can never apply once the PR head moved, so superseding it loses no work; a finalize push that already landed is contained in the descendant head.
- No change to finding-level rules: a `finalize-pending` record follows a passed review, so it carries no material findings.

## Risks

- During a normal in-flight finalize (claimed, push landed, update not yet recorded) the moved head is reported as awaiting developer re-admission; the coordinator only skips it, and a developer handoff is refused while the claim is live.
