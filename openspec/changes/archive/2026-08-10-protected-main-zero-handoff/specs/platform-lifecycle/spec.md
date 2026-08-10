## ADDED Requirements

### Requirement: Protected integration branches use remote PR integration

A platform-owned lifecycle SHALL NOT publish directly to an integration branch declared as protected. Protected-main publication SHALL use a feature branch and GitHub pull request so required status checks remain authoritative.

#### Scenario: Protected main is configured with direct publication

- **GIVEN** `protected_main=true`
- **AND** `harness_mode=platform`
- **WHEN** doctor or finish preflight evaluates `publish_mode=direct`
- **THEN** the lifecycle fails before local integration or remote push
- **AND** it explains that protected main requires PR publication

#### Scenario: Protected task is ready to publish

- **GIVEN** `protected_main=true`, `publish_mode=pr`, and `pr_merge_mode=auto`
- **WHEN** validated feature work is finished
- **THEN** the platform pushes the feature branch, creates or reuses its PR, waits for required checks, merges through GitHub, and synchronizes local main afterward
- **AND** it never force-pushes or bypasses branch protection

### Requirement: Automatic task PR merge preserves zero-hand-off delivery

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy.

#### Scenario: Automatic task PR succeeds

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** required PR checks succeed
- **THEN** the platform merges the PR through GitHub
- **AND** updates the local integration copy to the merged remote state
- **AND** completes normal board/worktree cleanup

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

For PR publication, local integration branch mutation SHALL occur only after the remote PR has been successfully merged.

#### Scenario: Remote PR merge is rejected

- **WHEN** GitHub rejects merge because protection requirements are not satisfied
- **THEN** the feature branch and PR remain available
- **AND** local main remains at its pre-publication commit

### Requirement: Publication prerequisites fail early

Platform-owned PR publication SHALL validate GitHub CLI/API availability before work reaches the remote merge stage.

#### Scenario: GitHub CLI is unavailable or unauthenticated

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **WHEN** doctor runs
- **THEN** it fails with an actionable authentication/setup message
- **AND** no local-main integration is attempted

### Requirement: Git branch publication is independent from PR API operations

The platform SHALL treat pushing a validated feature branch and performing GitHub PR API operations as separate publication steps.

#### Scenario: Direct invocation lacks PR API authentication

- **WHEN** a validated feature branch can be pushed using git credentials but GitHub PR API authentication is unavailable
- **THEN** the platform may leave the branch safely published
- **AND** it reports that PR creation/merge is incomplete
- **AND** it does not mutate local main

## MODIFIED Requirements

### Requirement: Configurable publication modes

The platform SHALL support `pr` and `direct` publication modes. PR mode SHALL publish a feature branch and create or reuse a GitHub PR; its completion behavior SHALL be controlled by `pr_merge_mode=auto|manual`. Direct mode SHALL publish only a safe fast-forward of an integration branch that is explicitly not protected.

#### Scenario: Project uses PR publication

- **WHEN** `publish_mode=pr` and validated feature work is completed
- **THEN** the platform pushes the feature branch and creates or reuses a PR
- **AND** follows the configured PR merge policy

#### Scenario: Project uses direct publication

- **GIVEN** `protected_main=false`
- **WHEN** `publish_mode=direct` and the integration branch safely descends from current origin/main
- **THEN** the platform may push the fast-forward update and SHALL abort on divergence