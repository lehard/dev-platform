## ADDED Requirements

### Requirement: The queue carries composition gates over a proven main-only update

When the queue refreshes a composition onto main, it SHALL carry review, finalization and full checks only with the existing main-only proof and trusted passed-gate evidence. Proven updates SHALL NOT rerun full checks, but SHALL wait for required CI on the exact new head before ready or admission. Failed proof SHALL prohibit reuse and preserve the existing repair/review rules.

#### Scenario: Clean update of a composition

- **WHEN** the queue cleanly refreshes a finalized composition and the main-only proof holds
- **THEN** no full-check rerun is started
- **AND** the candidate waits for required CI on its new head before ready or admission

#### Scenario: Conflict and runtime policy is preserved

- **WHEN** composition refresh encounters an environment failure or a merge-tree conflict
- **THEN** the accepted environment-failure and real-conflict transitions and attempt accounting remain in force
