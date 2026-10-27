## 1. Fresh-main proof
- [x] 1.1 `managed_task.resolve_committed_lineage`: canonical lineage of a change from a commit's tree, same matching and fail-closed rules, private lineage against the checkout.
- [x] 1.2 `requirement_terminal.reconcile_parent`: fetch `origin/<main_branch>` once and require each child's archived verified contract in that commit.
- [x] 1.3 `execute_requirement._done_child_is_delivered`: same fresh-main proof.

## 2. Verification
- [x] 2.1 Tests: reconciliation passes when only `origin/main` has the archive; refuses when `origin/main` lacks it or lacks `verification.md`; foreign lineage fails closed.
- [x] 2.2 Regression test: post-merge finish of a queue-merged task completes with no board claim.
- [x] 2.3 Regenerate the platform manifest; run full validation and semantic OpenSpec verification.
