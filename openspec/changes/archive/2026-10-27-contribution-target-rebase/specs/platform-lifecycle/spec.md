## ADDED Requirements

### Requirement: A contribution re-bases its integration job onto a moved requirement branch head

When a reviewed contribution's integration job was offered for a requirement integration branch head that has since moved, the coordinator worker SHALL NOT silently discard it. If the moved head still contains the contribution's recorded base, the worker SHALL re-offer the same integration job for the same contribution head and identity, bound to the moved head, without merging onto a head the job was not bound to. If the moved head no longer contains the base, the worker SHALL fail the job naming the lost base. A worker that lost its claim SHALL publish nothing.

#### Scenario: Another contribution integrated first

- **GIVEN** a contribution's integration job is bound to requirement branch head A
- **AND** the branch fast-forwarded to head B that contains the contribution base
- **WHEN** the worker runs the job
- **THEN** it publishes the same integration job bound to B and reports the target as moved
- **AND** it does not merge the contribution in that run

#### Scenario: Branch moves during the run

- **WHEN** the requirement branch moves after the worker checked it and before the protected merge
- **THEN** the worker re-offers the job bound to the newly observed head under the same base condition

#### Scenario: Base no longer contained

- **WHEN** the moved head does not contain the contribution base
- **THEN** the job fails naming the base and the moved head, and no job is re-offered
