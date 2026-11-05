## ADDED Requirements

### Requirement: Contribution evidence binds to one proven reviewed base

Review, task-content identity, selected checks and finalization of a contribution SHALL use one contribution base. Evidence from an earlier base SHALL be reused only when task content is proven equivalent across the move or the move is a proven target-only merge; otherwise a fresh review runs or the candidate blocks naming the base. Composition SHALL verify the recorded base, identity, head and integrated head of each child.

#### Scenario: Main-only movement is not attributed to the child
- **GIVEN** a requirement branch that absorbed main and a contribution reconciled onto it
- **WHEN** the contribution is reviewed and finalized
- **THEN** main's changes are absent from its task content and no finding is attributed to them

#### Scenario: Composition after a base move
- **WHEN** composition verifies a child whose base moved during delivery
- **THEN** it recomputes the identity from the recorded base and exact head and passes

#### Scenario: Identity differs
- **WHEN** the recomputed identity differs from the record
- **THEN** composition refuses naming the child
