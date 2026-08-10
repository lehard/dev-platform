## MODIFIED Requirements

### Requirement: Publication prerequisites fail early

Platform-owned PR publication SHALL validate GitHub CLI/API availability before work reaches the remote merge stage, and credential resolution SHALL fall back from invalid process token variables to other validated persistent GitHub credentials without requiring routine re-login.

#### Scenario: Stale environment token shadows persistent credentials

- **GIVEN** `GH_TOKEN` or `GITHUB_TOKEN` is present but invalid
- **AND** a valid persistent `gh` login or reusable Git HTTPS credential exists
- **WHEN** platform PR publication resolves GitHub API authentication
- **THEN** it ignores the invalid token source after validation fails
- **AND** continues with the valid persistent credential
- **AND** does not require the user to run `gh auth login` again

#### Scenario: GitHub CLI is unavailable or no credential source is usable

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **WHEN** all supported GitHub CLI/API credential sources fail validation
- **THEN** doctor/finish fails with an actionable authentication/setup message
- **AND** no local-main integration is attempted

### Requirement: Automatic task PR merge preserves zero-hand-off delivery

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy. Temporary check-registration delay and repository-supported async merge policy SHALL be handled inside the same lifecycle invocation.

#### Scenario: Required checks are not registered immediately

- **GIVEN** `pr_merge_mode=auto`
- **AND** the task PR was just created or updated
- **WHEN** GitHub temporarily reports that required checks are not yet present
- **THEN** the platform waits for check registration for a bounded period
- **AND** continues waiting for the required checks once they appear
- **AND** does not require a manual rerun solely because registration was delayed

#### Scenario: Automatic task PR succeeds through immediate merge

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

For PR publication, local integration branch mutation SHALL occur only after the remote PR has been successfully merged. A confirmed GitHub merge SHALL remain authoritative even if later local or remote-branch cleanup reports a non-zero convenience error.

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

## ADDED Requirements

### Requirement: Protected-main publication is resumable after remote merge

The platform-owned finish lifecycle SHALL recognize a task PR that was already merged by GitHub and SHALL resume only the remaining local reconciliation steps instead of requiring the feature branch to be republished or rebased.

#### Scenario: Process stops after GitHub merge before local synchronization

- **GIVEN** a task feature branch still exists locally
- **AND** its GitHub PR is already `MERGED`
- **AND** `origin/main` no longer has the feature branch as an ancestor because the PR was squash-merged
- **WHEN** the agent reruns `finish_task`
- **THEN** the platform recognizes the already-merged PR before applying stale-branch rejection
- **AND** synchronizes local main to the merged remote state
- **AND** reconciles board/worktree cleanup according to normal options
- **AND** returns success without creating a second PR or requesting a rebase
