# Design: Authoritative completion for scope claims

## 1. Exact identity first

For a managed board entry, the platform reuses the existing task/source/branch/publication identity to find the exact PR associated with that task. Similar names or unrelated merged PRs are not sufficient.

## 2. GitHub merge state outranks ancestry for squash publication

Branch ancestry remains a useful local signal for non-squash cases, but an exact GitHub `MERGED` state is authoritative evidence that a managed sibling no longer owns an active scope claim even when its feature commit is not an ancestor of `main`.

## 3. Conservative failure mode

If GitHub state cannot be read, the exact PR is ambiguous, or task identity is inconsistent, the platform retains the claim and keeps the existing fail-closed overlap behavior.

## 4. Coordination-only reconciliation

The operation may mark/remove only stale coordination metadata proven completed. It never cleans, resets, switches, deletes or writes inside the sibling worktree.

## 5. Idempotence

Repeated reconciliation of a proven merged sibling converges without repeated side effects.
