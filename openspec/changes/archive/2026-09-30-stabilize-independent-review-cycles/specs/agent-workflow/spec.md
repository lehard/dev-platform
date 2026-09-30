## ADDED Requirements

### Requirement: An own stale ready receipt is superseded on proven head advancement

When Requirement execution records a ready-for-integration receipt for a child and a different receipt already exists at that location, the platform SHALL replace it only when the existing receipt is valid, carries the identical Requirement, child Issue, change and source branch, and its recorded head is a strict ancestor of the new head in the child's repository. Any other existing receipt SHALL continue to block with an actionable diagnostic. A supersession SHALL be reported in the execution result.

#### Scenario: A failed attempt left the lifecycle's own receipt for an older head
- **GIVEN** a valid ready receipt for the same Requirement, child, change and branch records an ancestor of the current child head
- **WHEN** the supervisor advances again
- **THEN** the receipt is replaced by the receipt for the current head without manual cleanup
- **AND** the result reports the superseded head

#### Scenario: The existing receipt is foreign or ambiguous
- **GIVEN** an existing receipt with a different identity, an unreadable or invalid payload, a head that is not a strict ancestor of the new head, or the same head with different content
- **WHEN** the supervisor writes the ready receipt
- **THEN** the write is refused and the lifecycle stays blocked
