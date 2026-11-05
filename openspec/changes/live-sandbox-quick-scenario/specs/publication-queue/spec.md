## ADDED Requirements

### Requirement: A queue on a private repository reads checks and logs

A publication queue running on a private repository SHALL hold Checks read and Actions read in addition to its contents and pull requests write, because check data and job logs of a private repository are not readable without them. The token scope of a queue on a public repository is unchanged, and no other permission is added.

#### Scenario: Private repository

- **GIVEN** a queue on a private repository
- **WHEN** its coordinator token is minted
- **THEN** it also holds Checks read and Actions read
- **AND** a missing grant fails the queue run instead of being treated as absent checks

#### Scenario: Public repository

- **GIVEN** the queue on the public platform repository
- **WHEN** its coordinator token is minted
- **THEN** it holds contents write and pull requests write only
