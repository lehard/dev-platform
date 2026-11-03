## 0. Contract and event-driven continuation
- [x] 0.1 Update both shared-candidate readiness requirements with the approved proof-bound full-check and terminal-retrospective rules.
- [x] 0.2 Record exact-head CI waiting and full-check evidence on the candidate; have the existing publication-queue workflow resume it on CI completion without polling or repeating full checks. Explicitly block invalid, failed, unavailable or stale evidence.

## 1. Complete composition gate carry
- [x] 1.1 Reuse the accepted BR-969 proof and post-repair gate carry; add only the composition-specific evidence/validity binding.
- [x] 1.2 Update `requirement_composition.require_final_gates` to accept trusted proof-bound full checks for the new head without a fabricated rerun.
- [x] 1.3 `publication_queue.refresh_composition_checks`: carry gates for a proven clean main-only update without rerunning full checks.
- [x] 1.4 Require passed required CI on the exact new head before ready/admission; reject pending, failed, unavailable and stale-head CI.

## 2. Complete genuine integration repair
- [x] 2.1 Connect composition repair completion to one final-publication pass: full checks and admission without manual advance.
- [x] 2.2 Preserve full composition review for changed own content, followed by finalization and automatic final publication; keep pure main-only repair carry.

## 3. Regression evidence and docs
- [x] 3.1 Cover clean refresh without a rerun, proof/evidence rejection, exact-head CI readiness, one genuine-repair full-check pass, changed-content full review and preserved child receipts.
- [x] 3.2 Preserve queue environment-failure/real-conflict transitions and attempt accounting; update only the composition-gate runbook slice.
- [x] 3.3 Regenerate the platform manifest after code changes.

## 4. Verification
- [x] 4.1 Run required validation and semantic OpenSpec verification; record only actually executed checks.
