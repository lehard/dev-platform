# Tasks

- [x] 1. Implement a structured required-check state helper for the current PR head (`not_registered|pending|passed|failed|unknown`) without human-readable `gh` message matching; add focused unit tests for state normalization and head-SHA correctness.
- [x] 2. Refactor platform-owned PR finish/recovery so remote waits occur without `main_merge_lock`, then acquire the existing integration lock only for post-`MERGED` local main/board/worktree reconciliation; re-fetch remote main after lock acquisition.
- [x] 3. Make registration, pending-check, and merge/queue timeouts explicitly resumable and idempotent; preserve PR/branch and leave local main unchanged when remote completion is not proven.
- [x] 4. Add concurrency regression tests that drive two independent merged task heads through one shared integration checkout and prove no Git/index race, plus already-merged retry while another reconciliation holds the lock.
- [x] 5. Update generated agent-workflow documentation and any user-facing finish diagnostics so timeout/retry semantics and the narrow lock scope are accurate.
- [x] 6. Run Project Factory render/compile and an existing-platform-consumer Copier update smoke in addition to the platform unit suite; verify no project-owned harness behavior is silently replaced.
- [x] 7. Run platform validation and semantic OpenSpec verification, record `OpenSpec-Verify: PASS` with the real method in `verification.md`, archive via `python3 template/scripts/openspec_lifecycle.py archive harden-pr-reconciliation-concurrency`, then publish through protected main.

## Logical commit boundaries

1. Structured remote-state model + tests.
2. PR reconciliation serialization + recovery/timeouts + tests.
3. Generated docs/render compatibility + verification/archive.
