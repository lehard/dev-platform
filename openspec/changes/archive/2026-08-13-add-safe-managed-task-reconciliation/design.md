# Design: Resumable stale-task reconciliation

## Recovery contract

Reconciliation is an explicit lifecycle operation between task execution and authoritative validation/publication. It must never rewrite published history or guess task identity.

## State observation

The helper fetches authoritative main and classifies the exact managed task branch relative to it. Status exposes `current`, `behind/reconcile-required`, `conflict/blocked`, or an equivalent bounded state before costly validation.

## Update strategy

For an unpublished task, use the smallest safe non-destructive update compatible with current branch ancestry. For an already-published exact managed PR, preserve history: incorporate authoritative main through a normal merge (or another provably fast-forward-pushable operation), then push the resulting descendant head to the same PR branch. Rebase/history rewrite is not a supported automatic path.

The helper refuses to auto-stash or reset dirty work. A dirty worktree, merge conflict, unexpected remote head/base/owner, or managed provenance mismatch stops with explicit evidence.

## Validation and publication

A reconciled head is new execution state. Existing freshness and validation gates remain authoritative; reconciliation does not reuse stale PASS receipts. Publication resumes through the existing exact-head PR/recovery flow.

## Idempotence

Re-running reconcile against a task already containing current authoritative main is a no-op. Interrupted operations must either be safely resumable by Git's existing explicit conflict state or return a clear recovery instruction; they must not create a second task branch/PR.
