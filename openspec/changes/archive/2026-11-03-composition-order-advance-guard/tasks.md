## 1. Order and guard
- [x] 1.1 Order compositions by first admission and preserve the slot across re-admission.
- [x] 1.2 Refuse Requirement advance explicitly while the queue owns the composition, without starting checks or publication.

## 2. Spec boundary and docs
- [x] 2.1 Confirm T1 already contains the identical append-only requirement and all scenarios.
- [x] 2.2 Confirm T1 already contains the identical ready/finalized requirement and terminal checkpoint.
- [x] 2.3 Align task-intake and lifecycle-map; preserve post-merge ownership and portable lifecycle behavior.
- [x] 2.4 Keep `requirement_terminal.require_checkpoint` before terminal close; do not alter or bypass it.

## 3. Regression evidence
- [x] 3.1 Verify first admission survives re-admission, refused advance starts nothing, and both pre-ready spec paths need no retrospective.
- [x] 3.2 Verify terminal reconciliation still rejects missing/stale checkpoint and unrelated append-only scenarios remain intact.

## 4. Verification
- [x] 4.1 Run required validation and semantic OpenSpec verification; regenerate the platform manifest.
- [x] 4.2 Remove the portable shared-publication retrospective gate, preserving terminal reconciliation; test publication and terminal checkpoint absence and presence.
- [x] 4.3 Resolve or explain independent-review advisories and repeat validation and review.
