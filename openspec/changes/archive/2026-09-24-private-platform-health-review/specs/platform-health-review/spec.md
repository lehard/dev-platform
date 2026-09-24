# platform-health-review Specification Delta

## MODIFIED Requirements

### Requirement: Process and Architecture Health Review run together on one combined trigger

Dev Platform SHALL run the combined scheduled and manually dispatched Platform Health Review in the private caller repository. The review SHALL read only the bounded public platform and private Backlog evidence needed by its existing process and architecture lenses. The public `lehard/dev-platform` repository SHALL NOT run a complete combined review that reads private Backlog data. The combined review remains advisory and does not create managed work or mutate source evidence.

#### Scenario: Scheduled combined run

- **WHEN** the private combined review is triggered on its schedule
- **THEN** its jobs, logs, artifacts, and full report remain in the private caller repository
- **AND** no private task information is emitted to a public `dev-platform` output surface

#### Scenario: Manually dispatched combined run

- **WHEN** a human manually triggers the combined review in the private caller repository
- **THEN** both reviews run in that private repository and remain advisory

#### Scenario: One review fails independently

- **WHEN** one review job fails or is unavailable
- **THEN** the other review still runs and its findings remain available for the private combined report

#### Scenario: Central pilot precedes downstream rollout

- **WHEN** the private combined trigger is validated for the Dev Platform pilot
- **THEN** managed consumer repositories do not receive it without separate approval

### Requirement: Platform Health Review publishes one combined durable report

Each run SHALL publish exactly one dated, combined, human-readable Issue in the private caller repository, replacing the prior same-prefix report. The report SHALL record the reviewed platform `main` SHA, review time, previous boundary, and whether private evidence was available. The public repository SHALL NOT publish a second full report or store private task information.

#### Scenario: Combined run produces one report

- **GIVEN** private evidence and both review jobs are available
- **WHEN** the private run completes
- **THEN** one complete combined report appears only as a private Backlog Issue

#### Scenario: Repeat run replaces the prior report

- **GIVEN** a prior same-prefix combined report exists in the private Backlog
- **WHEN** a new review run completes
- **THEN** the new private report replaces the prior report without accumulating duplicates

#### Scenario: Missing private access

- **GIVEN** GitHub App credentials, installation scope, or private Issues read access is absent
- **WHEN** the run executes
- **THEN** the private report explicitly says `degraded` and names the unavailable evidence category without exposing secrets
- **AND** it does not claim a complete audit or send private content to the public repository

#### Scenario: One review's section is unavailable

- **WHEN** one bounded review job fails
- **THEN** the private combined report marks that section unavailable and does not claim complete status

## ADDED Requirements

### Requirement: Private Backlog access uses a minimally scoped GitHub App token

The private workflow SHALL mint a short-lived GitHub App installation token for only the repositories and read permissions needed to inspect its bounded evidence. Report writing SHALL use a separate private-repository-scoped credential. Long-lived PATs and public-run access to private task data SHALL NOT be required.

#### Scenario: Token scope

- **WHEN** the private run prepares review credentials
- **THEN** its App read token is restricted to `dev-platform` and the private caller repository and only required read permissions
- **AND** report publishing is restricted to the private caller repository

#### Scenario: Credentials unavailable

- **WHEN** required App credentials are not configured
- **THEN** the run takes the explicit degraded path without running an agent against incomplete Backlog evidence
