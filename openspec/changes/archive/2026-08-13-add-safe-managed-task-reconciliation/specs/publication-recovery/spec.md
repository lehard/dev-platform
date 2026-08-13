## MODIFIED Requirements

### Requirement: Existing exact-head PRs resume before first-publication stale-base rejection

A supported finish invocation SHALL distinguish a current task branch from one that is behind or diverged from freshly observed authoritative main before starting expensive validation. A first publication still obeys the platform's fresh-base safety preconditions. An existing exact-head PR whose base has advanced SHALL remain the one publication object, but delivery SHALL stop with the supported reconciliation operation before validation/publishing resumes.

The platform SHALL NOT silently rewrite/rebase/update the task branch merely to make recovery succeed. The explicit reconciliation operation SHALL preserve published ancestry through a normal merge and ordinary fast-forward push, and SHALL fail closed if dirty state, exact PR identity/base/owner, remote head, or authoritative main cannot be safely confirmed.

#### Scenario: Base advances while exact PR is waiting

- **GIVEN** an open exact-head task PR already exists for commit A
- **AND** the base branch advances after the PR was created
- **WHEN** finish is invoked again
- **THEN** it stops before expensive validation and points to the supported reconcile operation
- **AND** reconciliation preserves the same PR branch without force-push or rebase
- **AND** validation must rerun for the resulting descendant head before publication resumes

#### Scenario: New stale branch has never been published

- **GIVEN** no exact-head PR exists for local task commit A
- **AND** A does not satisfy the platform's first-publication fresh-base prerequisite
- **WHEN** finish attempts first publication
- **THEN** publication remains blocked until the branch is explicitly reconciled and revalidated

### Requirement: Publication status is read-only and actionable

The platform SHALL provide a supported read-only task publication status operation. Status SHALL not push branches, create/close PRs, arm merges, update boards, remove worktrees, or mutate local main.

Status SHALL report concise sanitized facts sufficient to distinguish at least: not published, PR open/checks pending, remote merge armed/queued, blocked/failed required checks, remotely merged but local reconciliation pending, and complete. It SHALL include the exact task SHA and PR URL/number when available and SHALL expose whether native remote auto-merge capability is available or the task is using foreground fallback. It SHALL also expose task-vs-authoritative-main freshness and the explicit reconciliation command when the task is behind or diverged, without updating local remote-tracking refs.

#### Scenario: Base advances before another validation run

- **GIVEN** an active task branch no longer contains the latest authoritative main
- **WHEN** read-only status runs
- **THEN** it reports reconciliation required and the supported command
- **AND** it does not update the local `origin/main` ref

#### Scenario: Caller loses output after remote merge was armed

- **GIVEN** GitHub accepted automatic integration for the exact task PR
- **WHEN** a later read-only status runs
- **THEN** it reports the current PR/check/merge state from GitHub
- **AND** it does not depend on the prior process having written a phase journal

#### Scenario: PR merged but local checkout was not reconciled

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration/board/worktree reconciliation has not completed
- **WHEN** status runs
- **THEN** it reports remote delivery as complete and local reconciliation as pending
- **AND** normal finish can perform only the remaining safe local reconciliation
