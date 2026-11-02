## ADDED Requirements

### Requirement: An assembled Requirement branch has a standard repair entry

A repository command SHALL request repair of an assembled Requirement composition as a queue repair job. The writer SHALL NOT edit child receipts; generated files SHALL be regenerated; every child receipt SHALL be validated byte-for-byte before the repaired head is pushed. Manual commits to the Requirement branch SHALL NOT be the repair path.

#### Scenario: Composition needs a fix
- **WHEN** the coordinator requests repair of a composition with a reason
- **THEN** a repair job edits the branch, regenerates generated files and validates child receipts before pushing

#### Scenario: A child receipt would change
- **WHEN** the repaired head changes a child verification receipt or automated-check evidence
- **THEN** the job fails naming the child and the receipt, and nothing is pushed
