# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Sequential Requirement children can share one integration delivery

Dev Platform SHALL support verified nonterminal child handoff and SHALL combine sequential isolated child results into one requirement-level candidate by default when the children are parts of one delivery outcome.

#### Scenario: Two children share one publication

- **GIVEN** two linked children have exact verified ready-for-integration receipts
- **WHEN** their parent Requirement is integrated
- **THEN** the candidate combines the exact child results in an isolated worktree and verifies interactions
- **AND** one protected PR and mandatory full CI own final delivery
- **AND** each child remains traceable to its own package, commit and verification receipt

#### Scenario: A child is not terminal at handoff

- **WHEN** a child becomes ready for shared integration
- **THEN** its Issue and Project status remain nonterminal until the exact shared candidate is merged and reconciled

#### Scenario: Handoff has exact child provenance

- **WHEN** a child is handed off for shared integration
- **THEN** a content-bound receipt identifies its parent Requirement, child Issue, OpenSpec change, exact commit, archived contract and successful verification receipt
- **AND** a changed or ambiguous receipt is rejected before candidate assembly

#### Scenario: Separate publication requires a boundary

- **WHEN** independent delivery or rollout risk requires a child to publish separately
- **THEN** the exception is recorded with its reason and uses the existing protected lifecycle
