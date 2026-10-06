## ADDED Requirements

### Requirement: Materialized Requirement execution does not depend on pre-authoring freshness

Once every handoff of a Requirement has a linked materialized child, Requirement advance and terminal reconciliation SHALL use the linked children and their OpenSpec as canonical and SHALL NOT require fresh pre-authoring. A material contract conflict SHALL still stop explicitly.

#### Scenario: Delivery changes bound sources
- **GIVEN** a Requirement whose children are materialized and delivered
- **AND** the delivery changed sources bound by its pre-authoring snapshot
- **WHEN** advance runs terminal reconciliation
- **THEN** it completes without requiring pre-authoring refresh

#### Scenario: A child is not yet materialized
- **WHEN** a handoff has no linked child
- **THEN** advance requires fresh pre-authoring before materializing it

### Requirement: Lifecycle GitHub calls retry classified transient failures

Requirement advance, terminal reconciliation and the publication queue SHALL retry GitHub/network failures classified as transient within a bounded number of attempts with backoff, and SHALL fail closed immediately on non-transient failures. Only read calls SHALL be retried automatically; mutating calls SHALL run once.

#### Scenario: Connection reset during advance
- **WHEN** a GitHub call fails with a connection reset and then succeeds
- **THEN** advance continues without operator action

#### Scenario: Persistent or non-transient failure
- **WHEN** the failure is non-transient or persists past the bound
- **THEN** the command reports a retryable or failed state with the bounded error
