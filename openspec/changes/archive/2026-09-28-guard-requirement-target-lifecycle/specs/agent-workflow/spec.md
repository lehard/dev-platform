## ADDED Requirements

### Requirement: Business Requirement targets have a supported managed lifecycle

A Business Requirement SHALL enter normal intake or execution only when its target repository can demonstrate the managed OpenSpec child, verification, protected publication and terminal reconciliation path required by that Requirement. Local support requires the target's managed capabilities and required lifecycle entrypoints, in addition to valid Backlog routing and protected publication configuration. Backlog routing labels or operator parameters alone SHALL NOT prove lifecycle support. The check SHALL use target-owned evidence and SHALL fail before creating a new Requirement or beginning execution of an existing one when support is absent or unreadable. A rejection SHALL identify the missing evidence and an available supported route without silently retargeting or manually closing the Requirement.

#### Scenario: Unsupported operator repository has routing but no managed lifecycle

- **GIVEN** a target repository can supply a Backlog repository, project label and priority
- **AND** it lacks the managed child and publication lifecycle required for Requirement execution
- **WHEN** a local or connected actor attempts Requirement fixation or execution
- **THEN** the operation stops before normal Requirement progress
- **AND** explains the missing lifecycle support and a supported target checkout or workflow route

#### Scenario: Managed target proceeds

- **GIVEN** a target checkout proves its configured managed OpenSpec and publication lifecycle
- **WHEN** a Requirement is fixed or started for that target
- **THEN** normal Requirement routing and execution remain available

#### Scenario: Explicit operator-managed downstream opt-in proceeds

- **GIVEN** an operator-managed downstream target has explicit integration evidence and the required managed entrypoints
- **AND** its Backlog routing parameters derive from its target checkout configuration
- **WHEN** local or connected Requirement intake checks that target
- **THEN** the target is supported without requiring a committed machine-local operator configuration

### Requirement: Requirement terminal state requires target delivery proof

Requirement terminal reconciliation SHALL require a supported target lifecycle and the existing exact linked-child, archived verification and merged delivery evidence. A manually closed Issue, Project Done field, or empty child set SHALL NOT substitute for that proof.

#### Scenario: Target lacks a terminal path

- **GIVEN** a Requirement Issue appears complete or its work was delivered outside managed execution
- **WHEN** terminal reconciliation cannot prove the target's supported managed lifecycle and exact delivered children
- **THEN** it refuses parent Done and Issue closure
- **AND** reports the missing terminal proof
