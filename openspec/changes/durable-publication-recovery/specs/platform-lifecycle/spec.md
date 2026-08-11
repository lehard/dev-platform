## MODIFIED Requirements

### Requirement: Automatic task PR merge preserves zero-hand-off delivery

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy. For a platform-owned automatic task, a completed local validation/archive candidate SHALL be sealed and remain recoverable until it is remotely merged or reaches an actionable terminal failure; an interrupted attempt SHALL resume the same safe candidate rather than require a human to remember or relay publication.

#### Scenario: Required checks are not registered immediately

- **GIVEN** `pr_merge_mode=auto`
- **AND** the task PR was just created or updated
- **WHEN** GitHub temporarily reports that required checks are not yet present
- **THEN** the platform waits for check registration for a bounded period
- **AND** continues waiting for the required checks once they appear
- **AND** does not require a manual rerun solely because registration was delayed

#### Scenario: Automatic task PR succeeds

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** required PR checks succeed
- **THEN** the platform merges the PR through GitHub
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

#### Scenario: Automatic publisher is interrupted before merge

- **GIVEN** `pr_merge_mode=auto` and a sealed task candidate
- **WHEN** the publishing process ends before its PR merges
- **THEN** a supported later lifecycle invocation detects the recoverable publication
- **AND** resumes or clearly reports the same branch and PR without creating duplicate delivery work

#### Scenario: Manual task PR is requested

- **GIVEN** `pr_merge_mode=manual`
- **WHEN** the task is published
- **THEN** the platform creates or reuses the PR and stops without merging it

### Requirement: Publication prerequisites fail early

Platform-owned PR publication SHALL validate GitHub CLI/API availability before work reaches the remote merge stage. It SHALL independently evaluate supported credential sources so an invalid exported credential cannot mask a valid local authenticated session.

#### Scenario: Stale environment token shadows persistent credentials

- **GIVEN** `GH_TOKEN` or `GITHUB_TOKEN` is present but invalid
- **AND** a valid persistent `gh` login or reusable Git HTTPS credential exists
- **WHEN** platform PR publication resolves GitHub API authentication
- **THEN** it ignores the invalid token source after validation fails
- **AND** continues with the valid persistent credential
- **AND** does not require the user to run `gh auth login` again

#### Scenario: GitHub CLI is unavailable or unauthenticated

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **WHEN** doctor runs
- **THEN** it fails with an actionable authentication/setup message
- **AND** no local-main integration is attempted

#### Scenario: Invalid exported credential masks no valid local session

- **GIVEN** an exported GitHub credential is invalid
- **AND** a supported local GitHub CLI session is valid
- **WHEN** doctor or publication preflight runs
- **THEN** it selects the valid session without logging a credential value
- **AND** it does not report the repository unauthenticated
