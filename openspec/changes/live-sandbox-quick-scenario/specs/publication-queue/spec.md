## ADDED Requirements

### Requirement: The live sandbox queue reads checks and logs of its private repository

The live sandbox snapshot SHALL grant the coordinator token of each queue workflow it installs Checks read and Actions read in addition to contents and pull requests write, because check data and job logs of a private repository are not readable without them. The grant is applied to the sandbox snapshot only; the platform's own queue workflows and their token scope are unchanged, and no other permission is added.

#### Scenario: Sandbox snapshot

- **GIVEN** a snapshot composed for the private live sandbox repository
- **WHEN** its queue workflows are installed
- **THEN** each App token step also requests Checks read and Actions read

#### Scenario: Platform repository

- **GIVEN** the queue on the public platform repository
- **WHEN** its coordinator token is minted
- **THEN** it holds contents write and pull requests write only
