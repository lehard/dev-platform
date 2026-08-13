# Design: Truthful local failure signals

## Part A: Contention-tolerant concurrency tests

Audit only the timeout/readiness points implicated by process issues #194 and #215. Where a test assumes a child has started within a tiny fixed wall-clock interval, synchronize on an explicit readiness signal. Keep an outer bounded deadline large enough for normal loaded CI/local execution but small enough to detect a genuine hang.

Production subprocess timeout changes are allowed only where the same confirmed contention-sensitive deadline affects runtime classification; do not globally inflate unrelated timeouts.

Retries are not a correctness mechanism.

## Part B: Dogfood finish cleanup

Terminal delivery remains GitHub `MERGED` plus required local reconciliation/Project state. Worktree cleanup is housekeeping after that authority is established.

A child process calling `chdir(integration)` does not move the parent shell/runner out of the task worktree. Therefore synchronous deletion of the caller's cwd can still poison the wrapper after a successful Python exit.

The safe design should detect when the invocation/caller context is rooted in the worktree that would be removed. In that case, do not make successful delivery depend on deleting that directory immediately. Persist one machine-local deferred-cleanup record bound to the exact worktree path, branch and Git head, then let `worktree_cleanup.py cleanup` remove it only from a surviving integration context after checking that it is inactive, board-free, clean and identity-matched. Repeated cleanup must converge after deleting the record. If cleanup can safely happen synchronously, keep the current direct cleanup path.

A real merge, reconciliation or required-check failure remains terminally non-zero. Only post-authority housekeeping may be downgraded to a truthful cleanup-pending warning/state.
