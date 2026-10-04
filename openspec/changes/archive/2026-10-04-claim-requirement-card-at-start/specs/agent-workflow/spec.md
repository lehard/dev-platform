# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Started Requirement is claimed on its card before preparation continues

When Requirement execution starts, the primary Requirement Project card SHALL be projected to its existing nonterminal status as soon as pre-authoring state is durably initialised, and again at the entry of every resume, before duplicate checks, evidence gathering or child materialisation. The claim follows Requirement validation and the check that durable pre-authoring state exists, so an invalid or unsupported Requirement is not claimed, and it SHALL NOT rewrite a terminal `Done` card. The platform SHALL NOT add a new status for this interval, and no error after the durable start SHALL write or leave a free-looking `Ready` projection by its own action.

#### Scenario: Card is claimed before slow preparation

- **GIVEN** a Requirement card shows `Ready`
- **WHEN** `requirement_intake.py start` initialises its pre-authoring state
- **THEN** the card shows `In progress` before any later pre-authoring or GitHub-dependent step runs
- **AND** a second agent reading the card during the first agent's preparation sees it as occupied

#### Scenario: Restart continues instead of creating parallel ownership

- **GIVEN** a Requirement has durable pre-authoring state
- **WHEN** `start` or `execute_requirement.py advance` is run again
- **THEN** the existing work is continued and the card reconciliation is idempotent
- **AND** a card still showing `Ready` is repaired to `In progress` at entry

#### Scenario: Failure after durable start does not free the card

- **GIVEN** the Requirement has started and its state is durable
- **WHEN** the card reconciliation or a later step fails
- **THEN** the failure is reported, the state is retained and a rerun converges
- **AND** the platform does not write `Ready`
