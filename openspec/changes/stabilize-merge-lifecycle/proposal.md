# Stabilize protected-main merge lifecycle

## Why

Managed projects are still surfacing routine human hand-offs during protected-main publication even when the underlying work is valid and GitHub eventually accepts the PR. Repeated incidents in Cuby and Jara_Fin show three reusable failure classes: a stale `GITHUB_TOKEN` can shadow usable persistent credentials, newly-created PR checks can be temporarily absent and cause a premature stop, and repository merge policy can reject an immediate squash even though auto-merge/merge-queue completion is available. A fourth recovery gap appears when GitHub has already merged a PR but the local lifecycle retries from a stale feature branch.

These are platform lifecycle concerns, not application-specific failures. The ordinary `finish_task` path should remain zero-hand-off across these transient/recoverable states while continuing to fail closed on real CI failures, conflicts, divergence, or unavailable credentials.

## What changes

- Make GitHub CLI credential resolution deterministic: a broken `GH_TOKEN`/`GITHUB_TOKEN` must not prevent fallback to a valid stored `gh` login or reusable HTTPS credential.
- Treat temporarily unregistered required PR checks as a bounded wait state instead of an immediate failure.
- Make automatic PR merge tolerant of GitHub policy differences by trying a normal protected merge first, then supported auto-merge / merge-queue enrollment forms, and by treating GitHub PR state as authoritative.
- Make `finish_task` idempotently recover when the task PR is already merged remotely but local main/board/worktree reconciliation did not finish.
- Add regression coverage for stale-token fallback, delayed check registration, merge-policy fallback, and already-merged recovery.

## Out of scope

- Bypassing branch protection, required checks, reviews, or merge queues.
- Force-pushing or silently rebasing stale feature branches.
- Solving delegated-agent filesystem containment across Claude/Codex runtimes; that requires a separate cross-runtime execution contract.
