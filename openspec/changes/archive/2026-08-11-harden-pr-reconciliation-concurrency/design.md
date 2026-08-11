# Design: concurrent protected-PR reconciliation

## Ownership boundary

GitHub remains authoritative for protected-branch merge state. The integration checkout remains a single local mutable resource shared by task worktrees. The design therefore separates the lifecycle into two concurrency domains:

1. **Remote wait domain (parallel):** feature-branch push, PR creation/reuse, required-check discovery/wait, and merge/queue waiting. No integration lock is held here.
2. **Local reconciliation domain (serialized):** after GitHub confirms `MERGED` for the exact task head, acquire the configured `main_merge_lock`, re-fetch remote main, synchronize the integration checkout, reconcile the board, and optionally remove the completed task worktree/local branch.

This preserves useful agent concurrency while making the one shared mutable checkout deterministic.

## Local reconciliation algorithm

For PR-mode auto merge and already-merged recovery:

1. Resolve and validate the exact task branch/head and authoritative GitHub PR state.
2. If the PR is not yet merged, continue the existing remote wait/merge negotiation without holding the integration lock.
3. Once the exact task PR is confirmed `MERGED`, acquire `serialized_integration(...)` using the same configured lock as direct mode.
4. Under the lock, fetch `origin/<main>` again. Do not reuse a remote-main observation made before acquiring the lock.
5. Require the integration checkout to be on the configured main branch and free of unrelated local mutations. Never stash/reset/clean another agent's state.
6. Recompute local-main vs remote-main relation. Fast-forward when safely behind; succeed when already equal; fail closed on ahead/diverged state.
7. Reconcile multi-agent board state idempotently.
8. If cleanup was requested, remove only this task's registered worktree and local branch from the integration checkout. Cleanup failure after a confirmed remote merge remains warning-only unless it prevents truthful board/task state from being represented.
9. Release the lock.

A second task that merged while the first reconciliation was running simply acquires the lock afterward, re-fetches the newer remote main, and fast-forwards from the state left by the first task.

## Structured required-check state

Human-readable `gh pr checks` output is not a stable state interface. Introduce one helper that queries structured PR/check data and normalizes it to a small internal state model:

- `not_registered`: required check contexts expected by repository protection are not represented for the current PR head yet;
- `pending`: required checks are present but at least one has not completed;
- `passed`: every required check for the current head has a successful terminal result;
- `failed`: at least one required check has a failing/cancelled terminal result;
- `unknown`: the platform cannot prove one of the above states from supported structured data.

The implementation may use `gh api`, GraphQL, or a stable `gh ... --json` surface, but state classification must come from structured fields. Arbitrary stderr/stdout wording may be included only as diagnostic detail. `unknown` fails closed and remains resumable.

Repository required-check configuration and the PR head SHA must be considered together so a passing check from an older head cannot satisfy the current task.

## Bounded waits and resumability

Waits remain bounded; zero-hand-off cannot mean waiting forever for an external service.

- **Registration timeout:** PR/branch remain open, local main is unchanged, and the result explicitly says checks are still not registered for the current head. Same-input rerun is safe because it re-queries remote state.
- **Pending-check timeout:** same behavior; no merge attempt occurs.
- **Merge/queue timeout:** if GitHub has not yet reported `MERGED`, local reconciliation does not start. Rerun first checks whether the exact head is now merged and resumes from there.
- **Remote API ambiguity/outage:** fail closed with an explicit remote-state-unavailable result; do not infer success/failure from text.

No timeout path requests rebase unless the branch is actually stale against a still-unmerged current remote main.

## Project-owned harnesses

This change does not replace repository-owned merge scripts. `harness_mode=project` may adopt the same pattern independently, but central template behavior only mutates the platform-owned lifecycle. `platform_doctor.py` continues to validate ownership boundaries.

## Upgrade and rollback

The change updates managed template lifecycle code and therefore affects fresh renders plus Copier updates of platform-owned harnesses. Rollback to the previous release restores non-serialized PR reconciliation and text-sensitive registration detection, so rollback is safe from a data-format perspective but reintroduces the race/fragility and is not the preferred steady state.

## Validation

Regression tests must include:

- two independent task heads confirmed merged close together, both reconciling through one integration checkout without Git/index races;
- the second reconciler observing local main already advanced by the first and still completing successfully;
- already-merged retry acquiring the same lock and remaining idempotent;
- structured `not_registered -> pending -> passed` progression without matching English CLI phrases;
- failing required check for the current head blocks merge;
- registration and merge timeout followed by successful rerun/recovery;
- generated-template render/compile plus an upgrade smoke for an existing platform-owned consumer.