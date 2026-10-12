## MODIFIED Requirements

### Requirement: Publication fails explicitly and uses least privilege

The publication workflow SHALL fail explicitly when GitHub Pages is not enabled for the repository, SHALL NOT change repository settings or provide an alternate publication path, SHALL pin third-party actions by commit SHA, and SHALL grant write permissions only to the deployment job and to the isolated post-merge editorial drift job, which SHALL receive only issue write permission.

#### Scenario: Pages is not enabled
- **WHEN** the deploy job runs in a repository whose Pages source is not GitHub Actions
- **THEN** the job fails with an explicit error and nothing is published

#### Scenario: Workflow contract is checked
- **WHEN** the workflow-contract test runs
- **THEN** it verifies pinned actions, minimal permissions per job, default-branch-only deployment and drift reporting, and that build and drift logic is invoked from repository entrypoints

## ADDED Requirements

### Requirement: Editorial drift is collected in one issue after merge

After the default branch is updated, the platform SHALL create or update exactly one open issue in the platform repository listing the editorial nodes whose bound sources changed since their last review, and SHALL close it when no such node remains. Pull requests SHALL show the same list as a non-failing annotation. Neither SHALL block build, deployment or merge.

#### Scenario: Stale nodes exist after merge
- **WHEN** the default branch is updated and one or more nodes are stale
- **THEN** one open drift issue lists them with the changed sections, without creating a second issue

#### Scenario: No stale nodes remain
- **WHEN** the default branch is updated and no node is stale
- **THEN** an open drift issue is closed

#### Scenario: Drift job fails
- **WHEN** the drift job cannot reach the issue API
- **THEN** the job fails visibly and the build and deployment results are unaffected
