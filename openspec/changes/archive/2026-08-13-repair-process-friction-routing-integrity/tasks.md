## 1. Repair routed issue eligibility

- [x] 1.1 Apply and verify the `process` label on routed issue create/update paths.
- [x] 1.2 Add bounded idempotent reconciliation for clearly generated unlabeled process-friction issues.
- [x] 1.3 Prove router-created issues are eligible for weekly selection.

## 2. Harden dedupe

- [x] 2.1 Remove the single-page open-issue assumption and support pagination.
- [x] 2.2 Add bounded duplicate-candidate handling for same root cause described with different category slugs.
- [x] 2.3 Preserve deterministic exact-fingerprint updates where identity is already stable.

## 3. Align review diagnostics

- [x] 3.1 Change `agent_doctor` so routine weekly review is not presented as a current-task action.
- [x] 3.2 Keep local pending/review commands documented as recovery/diagnostic surfaces.

## 4. Verify

- [x] 4.1 Add >100-open-issues pagination coverage.
- [x] 4.2 Add router → process label → weekly-selection end-to-end coverage.
- [x] 4.3 Run relevant process-health/lifecycle tests and strict OpenSpec validation.
