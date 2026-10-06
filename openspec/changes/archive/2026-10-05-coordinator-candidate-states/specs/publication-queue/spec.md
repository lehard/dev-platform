## ADDED Requirements

### Requirement: Coordinator tracks durable candidate lifecycle states

The publication coordinator SHALL derive each candidate's state (review-pending, reviewing, repair-pending, repairing, finalize-pending, ready, integrating, integration-repair-pending, merged, blocked-retryable, blocked-escalation) from GitHub PR head, checks, labels and immutable versioned marker comments, without a second journal or state store. Existing v1 queue markers SHALL remain readable.

#### Scenario: Coordinator restarts mid-review
- **GIVEN** a candidate marked reviewing for its exact head
- **WHEN** a new coordinator run starts
- **THEN** it derives the same state and next action from GitHub

#### Scenario: Head changes
- **WHEN** the PR head differs from the head in the latest marker
- **THEN** the candidate is not treated as having passed gates bound to the old head

### Requirement: Every transition publishes a structured handoff record

Each coordinator transition SHALL publish a record naming the candidate head, task-content identity, satisfied gates with the identity they verified, the failing gate and its evidence, items not re-verified, attempt counters and the next job, so a later executor can continue without reconstructing history.

#### Scenario: Repair follows a review failure
- **WHEN** a review finding moves the candidate to repair-pending
- **THEN** the record names the finding, the reviewed identity and the checks already satisfied

### Requirement: Candidate and Requirement status is read-only and actionable

A read-only status SHALL show for a candidate and for a Requirement the current state, active job or claim, attempts, red gate, evidence bindings and the next automatic or human action, from any execution location.

#### Scenario: Operator checks a Requirement
- **WHEN** status is requested for a Requirement
- **THEN** it lists each candidate's state and next action without mutating anything
