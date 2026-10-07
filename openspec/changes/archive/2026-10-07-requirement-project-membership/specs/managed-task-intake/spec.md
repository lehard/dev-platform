## ADDED Requirements

### Requirement: Requirement fixation confirms Project membership

Business Requirement fixation SHALL be reported successful only after the configured Development Backlog Project (`project_owner/project_number`) holds exactly one item for the Requirement Issue, confirmed by read-back, with an initialized Status. GitHub built-in auto-add MAY supply the item, but its absence SHALL be repaired by an idempotent add through the existing Project authorization and SHALL NOT be assumed. `project:*` labels SHALL NOT be treated as proof of membership. An unset Status SHALL be initialized to `Backlog`; an existing Status SHALL NOT be overwritten. More than one item, an unavailable Project, or a failed read-back SHALL fail explicitly naming the Requirement.

#### Scenario: Auto-add did not run

- **WHEN** a Requirement Issue is created and the Project holds no item for it
- **THEN** the platform adds the Issue to the configured Project, sets Status `Backlog` and reads back exactly one item before reporting success

#### Scenario: Item already present

- **WHEN** the Project already holds exactly one item for the Issue
- **THEN** no item is added and an existing Status is preserved
- **AND** repeating reconciliation is a no-op

#### Scenario: Project unavailable after Issue creation

- **WHEN** the Issue was created but the Project cannot be read or written
- **THEN** fixation fails closed naming the durable Issue and the reconciliation command
- **AND** a rerun with the same title and body continues that Issue instead of creating another

### Requirement: Connected fixation is complete only on confirmed membership

The connected-GitHub adapter SHALL report a Requirement as fixed only when Project membership is confirmed. When it cannot confirm membership it SHALL report the Issue as durable but fixation unconfirmed, SHALL NOT create another Issue, and SHALL leave completion to the operator-side `requirement_intake.py reconcile-board`, never to the user.

#### Scenario: Connector cannot write the user-owned Project

- **WHEN** a connected adapter creates the Issue and membership is unconfirmed
- **THEN** the outcome is unconfirmed rather than fixed
- **AND** operator reconciliation adds the item idempotently and confirms it
