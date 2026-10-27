## ADDED Requirements

### Requirement: Requirement retrospective covers delivery by quick PRs

The Requirement retrospective checkpoint SHALL accept a Requirement with no linked managed children when the operator names the merged quick pull requests that delivered it, and SHALL record them in the receipt, which is then checked like any other Requirement retrospective. Each named pull request SHALL be merged. A Requirement with neither linked managed children nor named quick pull requests SHALL be refused with the next action. Named quick pull requests MAY accompany managed children for a Requirement delivered partly by quick work.

#### Scenario: Requirement delivered only by quick PRs

- **GIVEN** a Requirement with an empty children block delivered by merged quick PRs
- **WHEN** `requirement_retrospective.py checkpoint --quick-pr owner/repo#N ...` runs
- **THEN** the receipt is recorded with the quick PRs and `check` reports it ready

#### Scenario: No children and no quick PRs

- **WHEN** the checkpoint runs for a Requirement with an empty children block and no `--quick-pr`
- **THEN** it is refused naming `--quick-pr`

#### Scenario: Named PR is not merged

- **WHEN** a named quick PR is not merged
- **THEN** the checkpoint stops naming that PR and records nothing
