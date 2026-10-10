# explorer-publication Specification

## Purpose
Define the platform-owned, reproducible build verification and GitHub Pages publication of the Dev Platform Explorer: a thin provider workflow that only orchestrates the repository build entrypoint, publishes from the default branch with least privilege, and fails explicitly when Pages is not enabled.

## Requirements

### Requirement: Explorer is built and published by a reproducible automated path

The platform SHALL verify on pull requests that the Explorer builds and SHALL publish it to GitHub Pages from the default branch, using a provider workflow that only orchestrates the repository-owned build entrypoint. Publication SHALL NOT require a separate CMS, site repository or manual update after platform changes.

#### Scenario: Pull request changes Explorer sources
- **WHEN** a pull request changes the Explorer, its build script or the canonical sources it renders
- **THEN** the build job runs the repository build entrypoint and fails the check if the build fails
- **AND** no deployment occurs

#### Scenario: Default branch is updated
- **WHEN** the default branch is updated
- **THEN** the Explorer is built with the repository build entrypoint and deployed to GitHub Pages

#### Scenario: Reviewer reproduces the published site
- **WHEN** a reviewer runs the documented local build command on the published commit
- **THEN** the output matches the published artifact

### Requirement: Publication fails explicitly and uses least privilege

The publication workflow SHALL fail explicitly when GitHub Pages is not enabled for the repository, SHALL NOT change repository settings or provide an alternate publication path, SHALL pin third-party actions by commit SHA, and SHALL grant write permissions only to the deployment job.

#### Scenario: Pages is not enabled
- **WHEN** the deploy job runs in a repository whose Pages source is not GitHub Actions
- **THEN** the job fails with an explicit error and nothing is published

#### Scenario: Workflow contract is checked
- **WHEN** the workflow-contract test runs
- **THEN** it verifies pinned actions, minimal permissions, default-branch-only deployment and that build logic is invoked from the repository entrypoint

### Requirement: Publication does not affect downstream distribution

The Explorer publication workflow SHALL NOT be rendered into downstream projects and SHALL NOT introduce any downstream reference to a mutable platform ref.

#### Scenario: New project is rendered
- **WHEN** a project is rendered from the template
- **THEN** it contains no Explorer publication workflow
