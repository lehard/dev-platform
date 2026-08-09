# Platform rollout delta

## ADDED Requirements

### Requirement: Managed repositories are explicitly allowlisted

The platform SHALL keep an explicit central registry of downstream repositories and SHALL automatically mutate only entries whose state is `managed`.

#### Scenario: Candidate repository is present in the registry

- **GIVEN** a repository is recorded as `candidate`
- **WHEN** automated rollout builds its project matrix
- **THEN** that repository is excluded from all cross-repository write operations

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
