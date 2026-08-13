## ADDED Requirements

### Requirement: Terminal dogfood success is not invalidated by self-cleanup of the caller cwd

After GitHub merge and required local reconciliation establish terminal task success, worktree cleanup SHALL NOT cause the invoking shell/runner to report the completed task as failed merely because the task worktree was its current directory. The lifecycle SHALL account for the caller context, not only the child Python process cwd.

#### Scenario: Finish is invoked from the task worktree

- **GIVEN** `dogfood_task.py finish` is launched while the caller's current directory is inside the task worktree
- **AND** the exact task PR is merged and local reconciliation succeeds
- **WHEN** post-delivery cleanup would remove that worktree
- **THEN** the lifecycle preserves a truthful terminal success result for the caller
- **AND** it does not synchronously invalidate the caller cwd in a way that produces a false `getcwd`/exit failure
- **AND** cleanup may be recorded/deferred for a later safe integration-root context if immediate removal is unsafe

#### Scenario: Deferred cleanup is retried safely

- **GIVEN** terminal delivery succeeded but worktree cleanup was deferred
- **WHEN** the supported cleanup/recovery path runs from a surviving context
- **THEN** it removes only the exact completed task worktree/branch when still safe
- **AND** repeated cleanup converges idempotently

#### Scenario: Delivery itself fails

- **WHEN** required checks, remote merge or local reconciliation has not successfully completed
- **THEN** finish remains non-zero/blocked according to the existing lifecycle
- **AND** caller-safe cleanup handling does not mask the real delivery failure
