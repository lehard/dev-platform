## ADDED Requirements

### Requirement: Friction after the Requirement retrospective refreshes it

When terminal reconciliation finds the Requirement retrospective stale only because of unlinked friction signals recorded later, it SHALL record a blocked result keyed by those events. The queue SHALL then offer retrospective and terminal jobs bound to that key, with their own attempts, up to a fixed bound. Past the bound the obligation SHALL stay blocked and reported.

#### Scenario: Post-merge fix records friction
- **GIVEN** a completed retrospective and a later friction event of the Requirement
- **WHEN** the terminal job runs
- **THEN** it blocks naming the event, a keyed retrospective job is offered, and after it the terminal job closes the Requirement with no hand-run checkpoint

#### Scenario: Newer friction appears during the refresh
- **WHEN** another event is recorded after the keyed retrospective
- **THEN** the terminal job blocks with a new key and one more refresh is offered

#### Scenario: A result under an earlier key arrives
- **WHEN** a result of an earlier key or attempt arrives
- **THEN** it does not satisfy the current obligation

#### Scenario: Refresh bound is reached
- **WHEN** the refresh bound is spent
- **THEN** no job is offered and the candidate reports the blocked retrospective with its reason and next action

#### Scenario: Terminal is blocked for another reason
- **WHEN** the terminal job blocks for a reason other than later friction
- **THEN** no refresh is offered and the existing attempt budget applies
