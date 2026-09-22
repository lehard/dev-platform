# Tasks

## 1. Specify the materialization boundary

- [x] Add idempotency, exact-reuse, interrupted-link, invalid-input, and ambiguity scenarios.

## 2. Implement

- [x] Validate and render ready handoffs as managed-task bundles.
- [x] Create or reuse an exact child and repair immediate parent/child linkage on retry.
- [x] Return explicit incomplete/ambiguous failures without false success.

## 3. Verify

- [x] Add isolated integration tests using mocked GitHub/intake boundaries.
- [x] Run relevant platform checks and semantic verification; record truthful evidence before archive.
