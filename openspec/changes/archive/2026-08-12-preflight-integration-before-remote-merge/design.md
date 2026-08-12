## Context

The existing publication model deliberately keeps long remote waits outside the shared integration lock and acquires serialization for post-merge local mutation. That is correct for concurrency, but creates a time window in which another local actor can dirty integration after task start. Today the lifecycle may then merge remotely and only discover the local blocker during reconciliation.

## Decisions

### Add a last-safe-point guard, not a long-lived lock

Do not hold the integration lock while CI or merge queue waits. Instead, when the exact PR reaches the point where the platform is about to ask GitHub for merge/auto-merge/queue mutation, acquire the existing serialization, re-observe integration, decide, then release as appropriate. This keeps remote waits scalable while preventing known dirty state from being ignored.

### Divergent dirty state blocks; path overlap is insufficient

Any uncommitted state that cannot be proven safe should block before merge. Do not infer equivalence from filenames or from the fact that the task would eventually create similar content.

### Remote-confirmed merge changes the safety objective

After GitHub has merged the exact head, rollback is not the platform's job. Recovery must preserve the remote truth and protect local data. If local content is provably equivalent to remote target, bounded reconciliation is allowed; if not, report `merged / reconciliation blocked` and wait for safe user/owner resolution.

### Prove equivalence with a disposable Git index

Recovery constructs a disposable index from the authoritative remote target, stages the observed working tree into that index, then compares the resulting index tree to the target. This covers tracked, untracked, content and mode differences without mutating the real index or worktree. Only after that proof may recovery use a mixed reset to align local branch/index; it never uses a hard reset, clean, stash or overwrite operation.

### Keep the guard at each protected mutation attempt

The ordinary merge, native auto-merge, and merge-queue enrollment forms each take the same short integration lock, re-fetch and inspect the integration copy immediately before the GitHub command. Required-check and queue waiting remains outside this lock. This also re-checks state before a fallback attempt after the foreground check wait.

## Risks / Trade-offs

- A conservative pre-merge block may delay a safe merge when local dirty state is harmless; false blocking is preferable to merging while known local divergence exists.
- Equivalence reconciliation must not turn into an implicit reset/clean path; tests must prove distinct local content survives untouched.
