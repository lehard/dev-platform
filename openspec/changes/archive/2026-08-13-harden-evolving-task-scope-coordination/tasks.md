## 1. Add bounded overlap acknowledgment

- [x] 1.1 Extend the existing admission contract with an explicit acknowledgment carrying task identities, exact conflicting paths and a bounded reason.
- [x] 1.2 Preserve truthful declared scope instead of requiring users to omit contested files.
- [x] 1.3 Ensure acknowledgment is narrow: new paths or materially changed conflicting identity require a new decision.

## 2. Recheck evolving factual scope

- [x] 2.1 Reuse existing changed-file/claim comparison before costly protected validation.
- [x] 2.2 Recheck immediately before publication.
- [x] 2.3 Block new unacknowledged hard overlap while the sibling task remains active; keep soft overlap advisory.
- [x] 2.4 Ignore stale claims from completed tasks through normal board lifecycle.

## 3. Managed lifecycle integration

- [x] 3.1 Reconcile genuine WAIT to `Blocked` with a bounded reason when managed provenance is available.
- [x] 3.2 Recheck on resume and return to `In progress` when the conflict clears or is explicitly acknowledged.

## 4. Verification

- [x] 4.1 Add regression coverage for process issues #203, #220 and #224.
- [x] 4.2 Preserve existing atomic claim race-safety and independent-task concurrency.
- [x] 4.3 Run relevant worktree/lifecycle/OpenSpec/template checks, semantic verification and archive normally.
