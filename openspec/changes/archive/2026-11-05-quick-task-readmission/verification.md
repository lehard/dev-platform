# Verification: quick-task-readmission

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Fix of a red required check: `admit` without a handoff takes the shared `_supersession` for a quick identity. `tests/test_pr_review_gate.py` proves `supersedes` with head, state and reason, `ready` on the same PR, no review job and kept attempts.
- Red CI to merged: a real `queue.worker` run in the queue fixture merges the new head on the same PR.
- Head already pushed and interrupted finish: the queue worker skips the head, status reports developer re-admission, and `admit` records the transition for the same head.
- Refusals: live claim, non-descendant head and another branch fail by name and write no comment. `finish` observes the same refusals before pushing through `local_status`.
- Managed path: `admit` without a handoff still refuses a managed identity, and existing re-admission tests pass unchanged. A managed red status keeps its job action.
- Status: `_quick_red_action` covers a recorded red check and one the queue has not recorded. A pushed head gets `developer re-admission`. No quick case names a coordinator decision. `next_job` stays in the record.
- Local head off the proven head: `local_status` names the proven head and the fetch and rebase, also when the proven commit is not yet local. `finish` and `--status` both go through it.
- Reconcile: for an admitted quick head it merges main locally, pushes nothing and prints the note. Tests use real git remotes. A task without a live admission and a managed task still push. A portable checkout stops at `queue_integrated` before any queue import.
- Raw push: a pushed head in a re-admission state is skipped, proven by a test. In other states the existing `_prepare` refusal blocks a head that is not a coordinator merge; that code is unchanged and this change adds no test for the quick case.

## Evidence

- `tests/test_pr_review_gate.py`, `tests/test_publication_queue.py`, `tests/test_task_reconciliation.py` pass; selected checks are recorded in `automated-checks.json`.

## Not verified

- No live run. Queue admission has no proof on real GitHub until the live scenario child of this Requirement.
- `ensure_pr` reaches the existing PR after the push through its create-race recovery, as a managed re-admission does; that path is read in code only.
