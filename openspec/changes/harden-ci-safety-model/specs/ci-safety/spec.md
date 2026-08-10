# CI Safety

## ADDED Requirements

### Requirement: Manual full-suite runs are isolated from lightweight automation
A generated Dev Platform workflow SHALL ensure that `workflow_dispatch` full-suite executions use a different concurrency group from `push` or `pull_request` executions on the same branch/ref.

#### Scenario: Main changes while manual full suite is running
- **WHEN** a manual full-suite run is executing for `main`
- **AND** a new commit triggers the lightweight `push` health run on `main`
- **THEN** the manual run is not cancelled by the push run
- **AND** superseded push runs may still cancel earlier push runs

### Requirement: High-impact configuration files receive conservative checks
The platform-owned selected-check mechanism SHALL NOT treat dependency manifests, lockfiles, build configuration, schema/migration configuration, or check/workflow configuration as whitespace-only changes.

#### Scenario: Dependency manifest changes
- **WHEN** a project using the platform-owned harness changes a Python or Node dependency manifest/lockfile
- **THEN** the selected checks include the relevant test/build/install validation defined by the project check configuration

### Requirement: Direct publication cannot silently bypass validation
The platform-owned direct publication path SHALL require the validated `finish_task.py` lifecycle. Validation bypass SHALL require a separate explicit operator override rather than a normal command-line flag alone.

#### Scenario: Agent calls project_publish directly
- **WHEN** `project_publish.py --mode direct` is invoked without the validated lifecycle guard
- **THEN** publication is refused before any push

#### Scenario: Agent passes --no-checks casually
- **WHEN** `finish_task.py --no-checks` is invoked without the explicit validation-bypass environment override
- **THEN** publication is refused before integration or push

### Requirement: Managed rollout executes from the requested immutable release
Managed rollout SHALL execute rollout helper code from the same exact immutable release tag that is being applied downstream.

#### Scenario: Retry an older release after main advances
- **GIVEN** current dev-platform `main` is newer than `vX.Y.Z`
- **WHEN** an operator dispatches a rollout for `vX.Y.Z`
- **THEN** rollout helper scripts are checked out from `vX.Y.Z`
- **AND** Copier is also pinned to `vX.Y.Z`

### Requirement: Dynamic downstream CI exposes a stable aggregate gate
A repository whose CI dynamically skips/runs conditional jobs SHALL expose one stable gate job that reflects all selected required jobs and is suitable for branch protection.

#### Scenario: Selected backend check fails
- **WHEN** the selector requires backend validation
- **AND** the backend job fails
- **THEN** the stable aggregate gate fails

#### Scenario: Backend check is not selected
- **WHEN** the selector does not require backend validation
- **THEN** the backend job may be skipped
- **AND** the stable aggregate gate can still pass if every actually required job succeeded

### Requirement: Authoritative cloud QA is compatible with publication mode
If a repository declares that an Actions workflow is authoritative product/application QA, changes SHALL reach `main` through a publication mode that runs that workflow before merge unless an equivalent authoritative local gate is explicitly declared and enforced.

#### Scenario: Project-owned authoritative browser QA
- **GIVEN** repository documentation identifies browser/visual QA in GitHub Actions as authoritative
- **THEN** the repository does not use an unchecked direct-to-main publication path

### Requirement: Required check contexts are unambiguous
Repositories SHALL NOT rely on a required status context name that can be emitted by multiple active workflows for the same pull request.

#### Scenario: Legacy and platform workflows overlap
- **WHEN** two workflows both define a job with the same required check context
- **THEN** one context is renamed or removed before that context is relied on as a branch-protection gate
