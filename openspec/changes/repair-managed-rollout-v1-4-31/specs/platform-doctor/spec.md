## ADDED Requirements

### Requirement: Shared-workspace permission policy is environment-aware

Platform doctor SHALL enforce and, where supported, repair the shared-workspace group-write/setgid contract on a collaborative local workspace. It SHALL recognize a GitHub-hosted Actions runner as an environment where that local topology is unavailable and SHALL not fail a downstream PR solely for absent local group/setgid state there.

#### Scenario: Local shared workspace has incorrect permissions

- **GIVEN** platform doctor runs in a supported shared local workspace
- **WHEN** required collaborative permissions are missing
- **THEN** doctor reports the permission problem according to the existing strict policy
- **AND** supported repair behavior remains available

#### Scenario: GitHub-hosted runner lacks local collaboration topology

- **GIVEN** platform doctor runs on a GitHub-hosted Actions runner
- **AND** the runner does not expose the expected shared local group/setgid topology
- **WHEN** doctor audits shared-workspace permissions
- **THEN** it records an advisory environment diagnostic
- **AND** it does not fail the PR solely for that unavailable local topology
