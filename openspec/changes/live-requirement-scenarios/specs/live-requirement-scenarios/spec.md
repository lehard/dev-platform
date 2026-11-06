## ADDED Requirements

### Requirement: Requirement path scenarios run on real GitHub

The scenarios SHALL include a Requirement with two children through composition to MERGED, a contribution conflict after a sibling merge, main movement with `absorb-main`, and post-merge with late friction to terminal. Requirement Issues and Project items SHALL live in the sandbox binding and SHALL NOT reach the production Backlog.

#### Scenario: Two children compose

- **WHEN** the scenario drives two linked children and their composition
- **THEN** the composition is MERGED, post-merge jobs reach terminal and the sandbox Requirement is closed

#### Scenario: Sibling merge conflicts a contribution

- **GIVEN** a sibling merge conflicts the second contribution
- **WHEN** the scenario follows the path the queue offers
- **THEN** the contribution is repaired and merged with no step outside documented entrypoints

#### Scenario: Main moves under a requirement branch

- **GIVEN** main moved and the requirement branch is not queue-owned
- **WHEN** `absorb-main` runs
- **THEN** the requirement branch contains main without history rewrite

#### Scenario: Friction arrives after merge

- **GIVEN** an unlinked friction event recorded after the composition merged
- **WHEN** terminal reconciliation runs
- **THEN** it blocks and re-offers retrospective and terminal
- **AND** the Requirement reaches terminal after they complete

### Requirement: Live coverage is listed

Documentation SHALL map every live-unverified item from recent delivery reports to a scenario or a stated reason. Sandbox composition finalize SHALL invoke real `npx` through its archive rehearsal.

#### Scenario: Item cannot be covered

- **GIVEN** an item applies only to a path the scenarios exclude
- **WHEN** the coverage list is read
- **THEN** the item is listed with that reason
