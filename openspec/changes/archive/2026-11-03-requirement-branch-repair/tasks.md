## 1. Repair entry
- [x] 1.1 Command that enqueues a `repair` job on a composition PR with a reason; refuses non-composition branches.
- [x] 1.2 Repair job on a composition: regenerate declared files, then `validate_children`; explicit failure on receipt mismatch.

## 2. Tests and docs
- [x] 2.1 Tests: request enqueues one job; receipt edit fails the job before push; manifest regenerated.
- [x] 2.2 chat-coordinator runbook: repair a Requirement branch only through the command; manifest.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification.
