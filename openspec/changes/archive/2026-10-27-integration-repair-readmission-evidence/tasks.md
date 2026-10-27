## 1. Developer re-admission
- [x] 1.1 Add `integration-repair-pending` to `READMISSION_STATES` and keep every existing supersession refusal.
- [x] 1.2 Re-open an archived managed task for handoff when its PR waits in `integration-repair-pending` and the local head strictly descends from the proven head (`local_status`, `semantic_readmission`, archived handoff wording).

## 2. Failed-check evidence
- [x] 2.1 Record each failed required check (name, workflow, state, link) in the required-checks red gate evidence.
- [x] 2.2 Build the integration-repair writer brief with a bounded failed-log excerpt per failed check; refuse before the writer starts when the identity or log is missing.

## 3. Verification
- [x] 3.1 Tests: re-admission accepted from `integration-repair-pending`; refused for a live claim and for a non-descendant head, each naming its reason; archived task re-opened; brief carries the excerpt; brief without evidence refused without spending an attempt.
- [x] 3.2 Run full validation and semantic OpenSpec verification.
