## Why

When required CI fails on a coordinator's integrated candidate, the candidate becomes `integration-repair-pending` and an integration-repair job is published. Two gaps make a known one-line fix expensive:

- The developer cannot hand off the fix. Supersession accepts only `review-pending`, `repair-pending`, `blocked-retryable` and `blocked-escalation`, and the archived managed task (finalize archives before integration) is re-opened for handoff only when its record is a `blocked-retryable` semantic-verification stop. The developer has to let the repair rounds run out until `blocked-escalation`.
- The integration-repair writer gets only "required check failed on the integrated candidate: validate". The sandboxed writer has no GitHub access and cannot see the log, so it ends with "no change".

## What Changes

- `integration-repair-pending` joins the states a fresh developer handoff for a descendant head may supersede. The existing supersession rules apply unchanged: the same task, no live claim on the offered job, and the new head descends from the proven (integrated) head; each refusal names its reason.
- An archived managed task whose admitted PR record is `integration-repair-pending` at the proven head is re-opened for a developer handoff when the local head strictly descends from that proven head; the archived re-handoff still needs a re-recorded semantic verification receipt.
- The required-checks red gate records each failed required check as structured evidence: name, workflow, state and link.
- The integration-repair brief for a required-checks red gate carries, per failed check, its identity and a bounded excerpt of its failed log, fetched by the operator-side runner through `gh run view --log-failed`. A missing failed-check identity, an unparsable link or an unreadable log refuses the job before any writer starts, naming the cause.

## Impact

- `template/scripts/publication_queue.py` (`READMISSION_STATES`, `local_status`, `semantic_readmission`, required-checks `IntegrationRepairNeeded` evidence).
- `template/scripts/pr_review_gate.py` (archived re-handoff wording).
- `template/scripts/integration_contour.py` (writer brief evidence).
- Tests for publication queue readmission and integration repair.
- `docs/engineering/agent-workflow.md` (re-admissible states, archived re-handoff, integration-repair brief evidence).
- Spec: publication-queue.
- Candidates already in `integration-repair-pending` from before the change carry no structured failed-check evidence; their writer job is refused with a named reason, and the developer re-handoff is the supported path.
