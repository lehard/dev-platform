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

### Requirement: Managed repositories are explicitly allowlisted and known projects are classified

The platform SHALL keep an explicit central registry of known downstream project repositories and SHALL automatically mutate only entries whose state is `managed`. Known repositories intentionally outside adoption/rollout SHALL be recorded as `excluded` rather than silently omitted.

#### Scenario: Candidate repository is present in the registry

- **GIVEN** a repository is recorded as `candidate`
- **WHEN** automated rollout builds its project matrix
- **THEN** that repository is excluded from all cross-repository write operations

#### Scenario: Excluded repository is present in the registry

- **GIVEN** a repository is recorded as `excluded`
- **WHEN** automated rollout builds its project matrix
- **THEN** that repository is excluded from all cross-repository write operations and its registry note explains the intentional exclusion

#### Scenario: Managed repository is present in the registry

- **GIVEN** a repository is recorded as `managed`
- **WHEN** a target platform release is rolled out
- **THEN** the repository is included in the rollout matrix using its configured default branch

### Requirement: Successful releases dispatch reviewed downstream rollout

After publishing an immutable platform version, the central release workflow SHALL dispatch the managed-project rollout for that exact SemVer tag. Rollout SHALL also support an explicit manual retry path and SHALL reject versions that are not actually published platform releases.

#### Scenario: New platform version is published

- **WHEN** the release workflow successfully creates or confirms `vX.Y.Z` at the release commit
- **THEN** it dispatches the rollout workflow with target version `vX.Y.Z`

#### Scenario: Manual retry names an unpublished version

- **WHEN** a manually dispatched rollout requests a syntactically valid tag that is not a published immutable platform release
- **THEN** rollout fails before creating any downstream write token or mutation

### Requirement: Cross-repository rollout uses least-privilege GitHub App authentication

Automated rollout SHALL use a dedicated GitHub App rather than relying on the source repository `GITHUB_TOKEN` or a broadly reusable personal token. Each project job SHALL use separately down-scoped short-lived credentials for the private platform source and downstream target.

#### Scenario: Rollout job needs private template access

- **WHEN** Copier fetches the private `lehard/dev-platform` source
- **THEN** it uses a token scoped only to `dev-platform` with Contents read permission

#### Scenario: Rollout job writes one managed repository

- **WHEN** the job checks out, pushes or opens a PR in the downstream repository
- **THEN** it uses a different token scoped only to that repository with Contents write, Pull requests write, and Workflows write permissions so platform-managed `.github/workflows/*` changes can be delivered

### Requirement: Managed upgrades target exact immutable platform versions

Automated rollout SHALL run Copier against the exact published SemVer tag supplied by release orchestration and SHALL never update a downstream project from mutable `main`.

#### Scenario: Project is behind the target version

- **GIVEN** `.copier-answers.yml` identifies `lehard/dev-platform` and records an older platform tag
- **WHEN** rollout targets `vX.Y.Z`
- **THEN** Copier updates the project with `--vcs-ref vX.Y.Z` before validation and PR creation

### Requirement: Rollout fails closed on project ambiguity or conflicts

Automatic rollout SHALL leave the downstream default branch untouched when Copier metadata is missing or unexpected, a downgrade is requested, an unresolved Copier/Git conflict remains, project validation fails, or an unexpected rollout branch collision exists.

#### Scenario: Copier produces a rejected patch

- **WHEN** an exact-version update leaves any non-ignored `*.rej` file
- **THEN** the rollout job fails and does not push or merge changes to the downstream default branch

#### Scenario: An update PR for the same target already exists

- **WHEN** rollout finds the deterministic target branch already associated with an open pull request
- **THEN** it reports the rollout as already pending without force-pushing or opening a duplicate PR

### Requirement: Automatic rollout stops at a reviewable pull request

A clean managed-project update SHALL be committed to a deterministic automation branch and opened as a normal downstream pull request. The rollout system SHALL NOT auto-merge that pull request by default.

#### Scenario: Copier update and project checks succeed

- **WHEN** the managed project has a clean exact-version update
- **THEN** the platform opens a PR against the configured default branch and leaves merge to downstream review/CI policy

### Requirement: Existing project-owned files survive platform rollout

The Project Factory SHALL create default project-owned control files for fresh repositories but SHALL preserve existing downstream content for files explicitly classified as project-owned during Copier updates.

#### Scenario: Existing managed project customized its project contract

- **GIVEN** a managed project already contains a customized `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, or `openspec/config.yaml`
- **WHEN** Copier updates the project to a newer platform release
- **THEN** those existing files are preserved rather than patched or replaced by the platform template

### Requirement: Platform version metadata stays coherent

After Project Factory rendering or managed Copier update, `.dev-platform.toml` `platform_version` SHALL match the stable SemVer recorded by `.copier-answers.yml` `_commit` without the leading `v`.

#### Scenario: Managed rollout advances Copier version

- **WHEN** rollout updates `_commit` from `v1.0.2` to `v1.2.1`
- **THEN** `.dev-platform.toml` records `platform_version = "1.2.1"` before validation and commit

#### Scenario: Version metadata remains inconsistent

- **WHEN** rollout finishes Copier update but the two version records differ
- **THEN** rollout fails before pushing a branch or opening a PR

### Requirement: Project-specific doctor requirements are configuration data

Projects SHALL be able to declare additional required repository files in `.dev-platform.toml` without modifying the centrally managed `platform_doctor.py` implementation.

#### Scenario: Project requires a compatibility helper

- **GIVEN** `.dev-platform.toml` lists a project-specific required file
- **WHEN** `platform_doctor.py` runs
- **THEN** it verifies that file in addition to the shared platform requirements

### Requirement: Machine-owned Copier metadata is normalized before strict diff validation

Managed rollout SHALL normalize only `.copier-answers.yml` machine-owned trailing newline formatting after Copier update and before strict Git whitespace validation. Other downstream files SHALL remain subject to unmodified strict validation.

#### Scenario: Copier emits an extra blank line at EOF

- **WHEN** an exact-version Copier update leaves multiple trailing newlines in `.copier-answers.yml`
- **THEN** rollout rewrites that metadata file to exactly one terminating newline before running `git diff --check`

#### Scenario: Another project file contains a whitespace error

- **WHEN** the downstream update contains a whitespace error outside the explicit Copier metadata normalization
- **THEN** strict `git diff --check` still blocks rollout before push or PR creation
