## 1. Reviewer runtime readiness

- [x] 1.1 Add `preflight` to `independent_review_runner.py` (provider, exact model, binary, bounded probe through the launcher, actionable limitation, no fallback) and call it from `run_review` before any perspective launch.
- [x] 1.2 Add `independent_review.py preflight [change]` and point missing-review next-step guidance at it.

## 2. Reviewer context

- [x] 2.1 Build the reviewer diff from identity-included paths only, record excluded lifecycle paths in the request, and state the exclusion in the prompt.

## 3. Ready receipt supersession

- [x] 3.1 Let `requirement_integration.write_receipt` supersede an own receipt on proven strict-ancestor head advancement; keep refusing foreign, divergent, equal-head-different or unprovable receipts; report the supersession from advance.

## 4. Evidence and documentation

- [x] 4.1 Add unit tests and a representative happy-path regression (one review round, no manual cleanup) plus fail-closed regressions.
- [x] 4.2 Update the engineering workflow documentation for the preflight command and the review evidence boundary, keeping template mirrors in sync.
- [x] 4.3 Run selected and required platform checks, semantic OpenSpec verification, a truthful receipt, archive and managed publication.
