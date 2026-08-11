## MODIFIED Requirements

### Requirement: Automatic task PR merge preserves zero-hand-off delivery

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy. Temporary check-registration delay and repository-supported async merge policy SHALL be handled inside the same lifecycle invocation. Required-check registration and terminal state SHALL be determined from structured GitHub state for the current PR head, not from human-readable CLI message matching.

#### Scenario: Required checks are not registered immediately

- **GIVEN** `pr_merge_mode=auto`
- **AND** the task PR was just created or updated
- **WHEN** structured GitHub state shows that required checks for the current PR head are not registered yet
- **THEN** the platform waits for check registration for a bounded period
- **AND** continues waiting for the required checks once they appear
- **AND** does not require a manual rerun solely because registration was delayed within that bound

#### Scenario: Required-check registration wait expires

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** the bounded registration wait expires before required checks are visible for the current head
- **THEN** the PR and feature branch remain intact
- **AND** local main remains unchanged
- **AND** the lifecycle reports a resumable remote-pending state rather than inferring failure from CLI text
- **AND** rerunning the same task finish operation re-queries authoritative remote state

#### Scenario: Structured required check fails

- **GIVEN** required checks are registered for the current PR head
- **WHEN** structured GitHub state reports a required check in a failing terminal state
- **THEN** the platform does not merge the PR
- **AND** local main remains unchanged
- **AND** the failing required check is reported without relying on arbitrary log text

#### Scenario: Merge queue remains pending past the bounded wait

- **GIVEN** GitHub accepted auto-merge or merge-queue enrollment
- **WHEN** the bounded merge confirmation wait expires before the exact task PR reaches `MERGED`
- **THEN** the platform does not begin local-main reconciliation
- **AND** leaves the PR available for GitHub to continue processing
- **AND** a later rerun checks whether the exact task head has since merged and resumes safely

#### Scenario: Automatic task PR succeeds

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** required PR checks succeed and GitHub accepts an ordinary protected merge
- **THEN** the platform confirms the PR is `MERGED`
- **AND** updates the local integration copy to the merged remote state
- **AND** completes normal board/worktree cleanup

#### Scenario: Repository requires auto-merge or merge queue

- **GIVEN** `pr_merge_mode=auto`
- **AND** required PR checks have succeeded
- **WHEN** GitHub rejects the ordinary merge form because repository policy requires asynchronous auto-merge or merge-queue enrollment
- **THEN** the platform tries supported non-bypass auto/queue merge forms
- **AND** waits for GitHub to report the PR as `MERGED` for a bounded period
- **AND** does not use an administrative bypass

#### Scenario: Automatic task PR check fails

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** a required PR check fails
- **THEN** the platform does not merge the PR
- **AND** local main remains unchanged
- **AND** the agent receives the failing-check result

#### Scenario: Manual task PR is requested

- **GIVEN** `pr_merge_mode=manual`
- **WHEN** the task is published
- **THEN** the platform creates or reuses the PR and stops without merging it

### Requirement: Remote merge precedes local integration for protected-main work

For PR publication, local integration branch mutation SHALL occur only after the remote PR has been successfully merged. A confirmed GitHub merge SHALL remain authoritative even if later local or remote-branch cleanup reports a non-zero convenience error. In platform-owned multi-agent PR mode, the shared integration checkout mutation phase SHALL be serialized through the configured integration lock.

#### Scenario: Two task PRs merge near the same time

- **GIVEN** two independent multi-agent task PRs have both been confirmed `MERGED` by GitHub
- **WHEN** both finish processes attempt local reconciliation against the same integration checkout
- **THEN** only one process mutates the integration checkout at a time
- **AND** each process re-fetches remote main after acquiring the integration lock
- **AND** both tasks may complete without Git/index lock races or manual synchronization solely because of concurrent reconciliation

#### Scenario: First reconciliation advances local main before second acquires the lock

- **GIVEN** task A reconciles and advances local main while task B waits for the integration lock
- **WHEN** task B acquires the lock
- **THEN** task B re-fetches and recomputes local-main versus remote-main state
- **AND** safely fast-forwards or accepts an already-equal state
- **AND** does not assume the pre-lock local-main observation is still current

#### Scenario: Remote wait is still in progress

- **WHEN** a task is waiting for required checks, auto-merge, or merge-queue completion
- **THEN** it SHALL NOT hold the shared integration lock during that remote wait

#### Scenario: Remote PR merge is rejected

- **WHEN** GitHub rejects every supported non-bypass merge form because protection requirements are not satisfied
- **THEN** the feature branch and PR remain available
- **AND** local main remains at its pre-publication commit

#### Scenario: Merge is confirmed but cleanup fails

- **WHEN** GitHub reports the task PR as `MERGED`
- **AND** remote branch deletion or local worktree/branch cleanup fails
- **THEN** the lifecycle treats the task as remotely merged
- **AND** continues safe local-main reconciliation where possible
- **AND** reports cleanup as a warning rather than redefining the merge as failed

### Requirement: Protected-main publication is resumable after remote merge

The platform-owned finish lifecycle SHALL recognize a task PR that was already merged by GitHub and SHALL resume only the remaining local reconciliation steps instead of requiring the feature branch to be republished or rebased. The resumed local reconciliation SHALL use the same integration serialization as a first-pass successful PR finish.

#### Scenario: Already-merged retry races another task reconciliation

- **GIVEN** a task PR is already merged for the exact local task head
- **AND** another task is currently reconciling the shared integration checkout
- **WHEN** the first task is retried
- **THEN** it waits for the integration lock rather than mutating the checkout concurrently
- **AND** re-fetches remote main after acquiring the lock
- **AND** completes idempotent local/board/worktree reconciliation without creating a second PR or requiring a rebase

#### Scenario: Process stops after GitHub merge before local synchronization

- **GIVEN** a task feature branch still exists locally
- **AND** its GitHub PR is already `MERGED`
- **AND** `origin/main` no longer has the feature branch as an ancestor because the PR was squash-merged
- **WHEN** the agent reruns `finish_task`
- **THEN** the platform recognizes the already-merged PR before applying stale-branch rejection
- **AND** synchronizes local main to the merged remote state
- **AND** reconciles board/worktree cleanup according to normal options
- **AND** returns success without creating a second PR or requesting a rebase
