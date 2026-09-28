## Why

Protected main correctly rejects a stale PR while independent Dev Platform tasks finish concurrently. Waiting agents currently repeat reconcile and final validation as other PRs land. The personal-account repository cannot use GitHub's native merge queue, so a source-owned queue is needed to coordinate final publication without serializing implementation.

## What Changes

- Admit locally verified, archived, exact-head task PRs into a durable GitHub-backed ordered queue.
- Add a single GitHub Actions coordinator with scheduled recovery and observable per-PR status. It prepares one candidate on latest main, runs required GitHub CI on that head, and requests a guarded protected merge.
- Integrate admission and status into existing finish recovery so waiting agents resume terminal reconciliation without manually refreshing their branches for ordinary preceding queue merges.
- Block or retry when task content or relevant base changed, checks fail, a conflict occurs, or external main movement prevents proving the candidate.

## Impact

Central `lehard/dev-platform` publication lifecycle, one repository workflow, GitHub App permissions, queue tests and operating guidance. Task worktrees remain independent. Branch protection and mandatory CI remain authoritative.
