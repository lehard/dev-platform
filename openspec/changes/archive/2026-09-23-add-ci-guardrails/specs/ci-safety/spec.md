## ADDED Requirements

### Requirement: Platform workflows bound token rights and job duration

Central and Copier-generated platform-owned GitHub Actions workflows SHALL explicitly declare the minimum GITHUB_TOKEN permissions needed by each applicable workflow or job and SHALL give potentially long-running jobs reasonable timeout limits below the platform maximum.

#### Scenario: Read-only validation runs

- **WHEN** a platform validation job runs
- **THEN** its GITHUB_TOKEN cannot write repository contents or issues
- **AND** the job has an explicit timeout

#### Scenario: Publication or rollout runs

- **WHEN** a publication or rollout job requires a write operation
- **THEN** only its required token scopes are granted while other jobs retain narrower scopes
- **AND** each long-running job has an explicit timeout

#### Scenario: Managed project receives a platform update

- **WHEN** a generated platform workflow is rendered or updated through Copier
- **THEN** its validation job uses read-only repository token rights and has a bounded timeout
- **AND** a generated label-provisioning job retains only the issue-write scope it requires and has a bounded timeout
