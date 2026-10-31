## ADDED Requirements

### Requirement: A coordinator environment failure is visible on the candidate

When integration of a candidate stops on a coordinator environment failure, the queue SHALL post a note naming the exact head and the failure, and SHALL NOT change its state, post a block or spend an attempt; the run still fails with environment-error. Lifecycle status SHALL show that note as the reason until a later record for the head supersedes it. The same failure on the same head SHALL NOT be posted again.

#### Scenario: Derived merge without OpenSpec CLI

- **GIVEN** a blocked-retryable candidate waiting for exact-head required checks
- **WHEN** its derived merge stops because the coordinator lacks the OpenSpec CLI
- **THEN** its state and attempts are unchanged and its reason names the environment failure on that head

#### Scenario: Real conflict of a waiting candidate

- **WHEN** a waiting candidate without a red gate conflicts with main outside generated files
- **THEN** it moves to integration-repair-pending and the integration-repair attempt is counted
