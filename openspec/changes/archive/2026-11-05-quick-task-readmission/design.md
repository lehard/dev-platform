## Decisions

- **Quick identity.** A quick candidate has a dict identity with no `change` and no `kind`, on an `agent/` branch. `_repair_route` already reads it that way. A contribution or a composition is never quick. A non-dict identity is refused by name.
- **Same task.** Old and new identity name the same branch, which is the PR head branch. The managed keys stay for managed candidates.
- **Shared checks.** The supersession keeps its refusals: latest record bound to the proven head, a re-admission state, no live claim, a descendant head. `admit` without a handoff takes the same supersession instead of refusing.
- **After supersession.** The record is `ready` with the quick identity of the new head and no gates. No review job is published. Integration and exact-head required CI run as for any quick task.
- **Budget.** Attempt counters carry over, as for managed. Exhausted integration repair still blocks, and `finish` after a block opens a new slot as it does today.
- **Integration-repair job.** It stays published as a coordinator tool. Its live claim refuses the supersession by name.
- **Status.** Three moments: red checks the queue has not recorded yet (wait for the record), a recorded red state at the PR head (commit on top of the proven head, run `finish`), a pushed head (run `finish`). A local head that does not descend from the proven head gets the proven head and how to reach it. `next_job` stays in the record for job consumers.
- **Reconcile.** Reconcile checks for an admitted quick candidate through the source-only queue module, only when the checkout selected coordinator mode. It then merges main locally, pushes nothing and names `finish`. A local descendant ahead of the remote stays local.
- **Unrecorded head.** A raw `git push` cannot be stopped. The queue already skips such a head in a re-admission state and blocks it as a change outside coordinator control otherwise. Both stay, with tests for the quick case.

## Risks

Admission is queue code and has no live proof until the live scenario child. Unit tests and offline acceptance carry this change; the report says so.
