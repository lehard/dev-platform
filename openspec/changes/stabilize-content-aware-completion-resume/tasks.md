## 1. Content-aware freshness

- [x] 1.1 Reconcile current friction checkpoint, automated-check, reconciliation and publication evidence formats against `main`.
- [x] 1.2 Define a deterministic auditable task-content identity/equivalence proof that distinguishes lifecycle-only HEAD movement from task-content mutation.
- [x] 1.3 Apply that proof to retrospective/check freshness while preserving exact SHA provenance and fail-closed fallback.

## 2. Validation reuse

- [x] 2.1 Allow archive/finish to reuse successful evidence only when task-content equivalence is mechanically proven.
- [x] 2.2 Ensure actual task-owned content mutation or ambiguous/relevant upstream change invalidates reuse and selects appropriate validation again.
- [x] 2.3 Remove redundant full-suite execution caused solely by clean lifecycle/reconcile commits where policy permits proven reuse.

## 3. Cheap publication resume

- [x] 3.1 Detect an existing exact-head PR and durable auto-merge intent before entering first-publication work.
- [x] 3.2 Add a cheap status/reconcile path for pending checks, armed auto-merge and bounded wait exhaustion without republish/revalidation.
- [x] 3.3 Convert expected nonterminal subprocess outcomes into bounded structured diagnostics and eliminate raw traceback for those states.
- [x] 3.4 Preserve fail-closed recovery when PR head, required checks, merge intent or base relationship materially changes.

## 4. Regression coverage

- [x] 4.1 Cover checkpoint/check freshness across an archive-only commit and clean irrelevant reconcile.
- [x] 4.2 Cover task-content mutation forcing fresh validation.
- [x] 4.3 Cover existing exact-head PR with auto-merge armed, repeated finish/status, bounded wait and eventual merged reconciliation.
- [x] 4.4 Prove required GitHub checks and exact-head publication safety remain unchanged.

## 5. Verification and delivery

- [x] 5.1 Run relevant completion, publication recovery, Git lifecycle and friction groups.
- [x] 5.2 Semantically verify against the linked process evidence, archive normally and publish through the standard lifecycle.
