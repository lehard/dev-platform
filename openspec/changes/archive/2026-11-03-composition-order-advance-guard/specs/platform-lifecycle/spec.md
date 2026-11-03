## ADDED Requirements

### Requirement: Requirement advance refuses a queue-owned composition

While the publication queue owns a Requirement composition, Requirement advance SHALL fail explicitly, naming the queue state, and SHALL run no checks or publication steps.

#### Scenario: Advance on a queued composition

- **WHEN** advance runs for a Requirement whose composition is in the queue
- **THEN** it fails naming the queue state and starts no checks
