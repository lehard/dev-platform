## ADDED Requirements

### Requirement: The runner label rule is the same in Copier and platform_doctor

The platform SHALL reject, at the Copier question for `ci_runner_labels`, every label value that `platform_doctor` rejects: a blank value, an empty entry (as in `a,,b`), a duplicate entry, or a character outside `[A-Za-z0-9._-]` (including whitespace inside an entry). Surrounding whitespace around an entry SHALL be ignored identically by both. A value accepted by Copier SHALL never be rejected by `platform_doctor` for label validity.

#### Scenario: Empty entry is rejected when the question is answered
- **WHEN** a project answers `ci_runner=self-hosted` and `ci_runner_labels=a,,b`
- **THEN** Copier rejects the answer naming `ci_runner_labels`
- **AND** no workflow is rendered

#### Scenario: Whitespace inside a label is rejected when the question is answered
- **WHEN** a project answers `ci_runner_labels` as `self hosted`
- **THEN** Copier rejects the answer naming `ci_runner_labels`

#### Scenario: Copier and the doctor agree on a table of values
- **GIVEN** a table of valid and invalid label values
- **WHEN** each is checked by the Copier validator and by `platform_doctor`
- **THEN** both accept exactly the same values

### Requirement: Runner answers are asked only of GitHub projects

The platform SHALL ask `ci_runner` and `ci_runner_labels` only when `scm_provider` is `github`. A project with `scm_provider=gitlab` SHALL NOT be asked either question and SHALL NOT have either answer recorded.

#### Scenario: GitLab project is not asked about a GitHub runner
- **WHEN** a project is rendered with `scm_provider=gitlab`
- **THEN** no `ci_runner` or `ci_runner_labels` question is asked
- **AND** `.copier-answers.yml` records neither answer
