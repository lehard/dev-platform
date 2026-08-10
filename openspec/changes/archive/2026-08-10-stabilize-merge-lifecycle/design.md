# Design: resilient protected-main publication

## Goals

The normal platform-owned PR lifecycle should be a resumable sequence rather than a chain of one-shot commands. Transient GitHub states may delay completion, but they should not require the user to understand or manually resume the underlying stages.

## Credential resolution

`github_cli_env()` remains the single credential resolver used by platform-owned GitHub CLI calls. Resolution is ordered and validated:

1. Try the current process environment as-is. A valid explicit `GH_TOKEN`/`GITHUB_TOKEN` keeps its existing precedence.
2. If that fails, remove GitHub token environment variables and test the persistent `gh` login/keyring. This prevents a stale environment token from shadowing a valid stored login.
3. If persistent `gh` auth is still unavailable, query the reusable Git HTTPS credential and validate it in an isolated environment by exposing only that password as `GH_TOKEN`.
4. Return `None` only after all usable sources fail validation.

No token is printed or persisted by the platform.

## Required-check registration

A PR can exist for a short period before GitHub Actions/check-runs are registered. `gh pr checks --watch` can return non-zero during that gap. The lifecycle therefore treats well-known "no checks reported / no required checks yet" results as a bounded registration wait state. Once checks are registered, `--watch --fail-fast` remains authoritative. A real failing check still terminates the lifecycle without changing local main.

The registration wait is bounded so a misconfigured repository cannot hang indefinitely.

## Merge-policy negotiation

After required checks pass, GitHub remains the source of truth for whether the PR is merged. The platform attempts compatible merge forms without bypassing protection:

1. ordinary squash merge;
2. GitHub auto-merge with squash;
3. auto/queue enrollment without forcing a merge strategy, for repositories whose merge queue owns the method.

A non-zero CLI exit is not itself authoritative. After every attempt, the lifecycle checks PR state. If GitHub accepted an async auto-merge/queue operation, the platform waits for the PR to become `MERGED` within a bounded timeout. If every supported form is rejected and the PR is not merged, publication fails closed.

Remote branch deletion is a post-merge cleanup phase and is never allowed to redefine a confirmed merge as failed.

## Idempotent recovery

`finish_task` performs a remote-merge recovery check before rejecting a feature branch merely because `origin/main` advanced. If the branch's PR is already `MERGED`, it skips re-publication, synchronizes local main, closes board state, and optionally removes the completed worktree/branch. If the PR is not merged, the existing stale-branch protection remains unchanged.

This specifically covers process interruption between GitHub merge and local reconciliation.

## Downstream compatibility

Platform-owned harness projects receive the behavior through normal Copier rollout. Project-owned harnesses keep their repository-owned merge implementation; common credential resolution can still roll out, but any project-owned merge state machine must be aligned separately. Jara_Fin therefore needs a downstream project-owned patch after this platform change is released.

## Safety invariants

- required checks are never bypassed;
- local main does not move until GitHub confirms the PR is merged;
- no force push is introduced;
- stale open PR branches still require explicit update/rebase;
- all waits are bounded and end with actionable failure rather than silent success.
