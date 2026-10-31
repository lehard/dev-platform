## MODIFIED Requirements

### Requirement: Platform-rendered CI runner is a declared project answer

The platform SHALL let a downstream project declare through its recorded Copier answers whether platform-rendered GitHub Actions jobs run on GitHub-hosted `ubuntu-latest` or on explicit self-hosted runner labels.

#### Scenario: GitHub-hosted default is unchanged

- **GIVEN** a project answers `ci_runner=github-hosted` or accepts the default
- **WHEN** the template renders the platform workflows
- **THEN** `platform-ci` and `provision` run on `ubuntu-latest`
- **AND** no shared-workspace repair step is rendered

#### Scenario: Self-hosted choice survives update

- **GIVEN** a project recorded `ci_runner=self-hosted` and `ci_runner_labels=alters`
- **WHEN** the project is rendered and later updated by Copier to a newer platform version
- **THEN** `platform-ci` and `provision` run on `alters`
- **AND** `platform-ci` runs the shared-workspace repair before `platform_doctor`

#### Scenario: Runner disagrees with the answer

- **WHEN** the committed `platform-ci` runner or the presence of the repair step differs from the recorded answer
- **THEN** `platform_doctor` fails naming the expected and found values

#### Scenario: Invalid self-hosted labels

- **WHEN** `ci_runner=self-hosted` and the labels are empty, contain an empty entry, a duplicate or a character outside `[A-Za-z0-9._-]`
- **THEN** rendering or `platform_doctor` fails naming `ci_runner_labels`
- **AND** no GitHub-hosted runner is substituted

## ADDED Requirements

### Requirement: Platform-rendered jobs follow the recorded runner answer

The rendered `runs-on` of every platform-rendered job SHALL follow the project's recorded CI runner answer, and a Copier update SHALL preserve it.

#### Scenario: Jobs are rendered and updated

- **WHEN** platform-rendered jobs are rendered and later updated by Copier
- **THEN** the rendered `runs-on` of every platform-rendered job follows the project's recorded CI runner answer
- **AND** the Copier update preserves it

### Requirement: A self-hosted platform-ci job repairs the shared workspace before platform_doctor

A self-hosted `platform-ci` job SHALL prepare the checkout with the repository-owned shared-workspace repair before `platform_doctor`.

#### Scenario: Self-hosted platform-ci job runs

- **WHEN** a self-hosted `platform-ci` job runs
- **THEN** it prepares the checkout with the repository-owned shared-workspace repair before `platform_doctor`

### Requirement: Platform-rendered jobs need no tooling a self-hosted runner need not provide

Platform-rendered jobs SHALL NOT depend on tooling that a self-hosted runner is not required to provide.

#### Scenario: Job runs on a self-hosted runner

- **WHEN** a platform-rendered job runs on a self-hosted runner
- **THEN** it does not depend on tooling that a self-hosted runner is not required to provide

### Requirement: platform_doctor fails on a missing, malformed or disagreeing runner answer

`platform_doctor` SHALL fail explicitly when the recorded answer is missing, self-hosted labels are empty or malformed, or the committed workflow's runner or preparation step disagrees with the answer.

#### Scenario: Runner answer is missing or inconsistent

- **WHEN** the recorded runner answer is missing, self-hosted labels are empty or malformed, or the committed workflow's runner or preparation step disagrees with the answer
- **THEN** `platform_doctor` fails explicitly
