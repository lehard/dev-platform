## 1. Re-base
- [x] 1.1 `merge_reviewed_contribution`: on a target head that differs from the job's `target_head`, or moves before the merge, re-offer the job bound to the moved head when it contains the contribution base; otherwise raise naming the base.

## 2. Verification
- [x] 2.1 Tests: re-offer on moved head (both points), refusal without base, no re-offer on a lost claim, unchanged merge on a matching head.
- [x] 2.2 Regenerate the platform manifest; run full validation and semantic OpenSpec verification.
