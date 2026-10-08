## 1. Job identity and selection
- [x] 1.1 Add the optional `reoffer` job field, its `job_id` suffix, `job_completed` handling of `unavailable` outcomes, and `only_prs`/`eligible` selection in `work_next`.
- [x] 1.2 Add worker provider readiness (scratch environment), `--pr`, `--providers` and `--repair-provider`, and require `--repair-provider` for repair `--run`.

## 2. Re-offer and unavailable-runtime handling
- [x] 2.1 Implement `reoffer` with provenance, budget neutrality and eligibility rules in `pr_review_gate`, record providers on escalation, and add `switch-provider` and `resume` to `publication_queue`.
- [x] 2.2 Classify an unavailable runtime in `execute_job`/`run_claimed` as a bounded retryable state, name the cause on the review retry state, and extend retry ownership to repair.

## 3. Evidence and delivery
- [x] 3.1 Add regression tests for switching an open candidate, selection by provider and PR, unavailable runtime during review and repair, and resuming an operational escalation.
- [x] 3.2 Update the operating guide, run selected checks and semantic verification, and complete the authorized lifecycle handoff.
