# Platform Rollout Specification

## Purpose

Platform rollout SHALL keep shared workflow releases and downstream upgrades reproducible, reviewable and recoverable across new and existing repositories.

## Requirements

### Requirement: Copier upgrades are tested, not assumed

Before a platform release is published, CI SHALL exercise a real Copier update from the latest stable platform template or an explicit bootstrap baseline to the candidate template. The smoke project SHALL contain project-owned modifications before update and SHALL fail validation if those modifications are lost or unresolved conflicts remain.

#### Scenario: Candidate platform is tested against existing project state

- **WHEN** platform CI evaluates an update from the stable baseline
- **THEN** it performs a real Copier update on a smoke project containing project-owned customization and verifies that customization survives without unresolved conflicts

### Requirement: Unresolved template-update conflicts block completion

Generated project doctor SHALL report a blocking failure when a non-ignored `*.rej` file exists or Git reports leftover conflict markers in staged or working-tree changes.

#### Scenario: Copier leaves a rejected patch

- **WHEN** a generated repository contains a non-ignored `*.rej` file after an update
- **THEN** platform doctor fails until the conflict is resolved

### Requirement: Platform tool versions are deliberate

The Project Factory SHALL declare a minimum Copier version and the platform SHALL record the version it was tested with. Platform CI SHALL use the exact tested Copier version rather than a floating compatible range.

#### Scenario: Platform CI installs Copier

- **WHEN** platform validation runs
- **THEN** CI installs the exact tested Copier version recorded by platform policy

### Requirement: GitHub Actions references are immutable

GitHub-owned Actions used by platform-managed workflows SHALL use full commit SHAs rather than mutable major tags.

#### Scenario: Platform-managed workflow references an Action

- **WHEN** a workflow uses an `actions/*` dependency
- **THEN** the dependency reference is a full immutable commit SHA

### Requirement: Platform releases use stable immutable versions

Published Project Factory versions SHALL use stable SemVer Git tags. A published version tag SHALL NOT be moved or reused, and automated publication SHALL fail closed when an existing tag points elsewhere.

#### Scenario: Existing release tag points to another commit

- **WHEN** release automation finds that the requested SemVer tag already exists at a different commit
- **THEN** publication fails instead of moving the tag

### Requirement: Downstream upgrades remain reviewed

Platform-managed files, including self-contained CI, SHALL propagate to downstream repositories through reviewed Copier updates rather than mutable remote execution. Downstream update PRs SHALL NOT auto-merge by default.

#### Scenario: Platform version changes downstream behavior

- **WHEN** an existing managed repository adopts a newer platform release
- **THEN** the platform-managed file changes arrive as a reviewable Copier diff or PR before they affect the project
