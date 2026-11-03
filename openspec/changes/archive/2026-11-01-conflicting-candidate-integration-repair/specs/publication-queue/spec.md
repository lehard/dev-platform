## ADDED Requirements

### Requirement: A coordinator environment failure is visible on the candidate

When integration stops on a coordinator environment failure and merge-tree reports no conflict, the queue SHALL post a note naming the head and the failure, change no state, post no block, spend no attempt; the run still fails. Any merge-tree conflict, including one only in declared generated or derived files, SHALL go to integration-repair-pending, spending an attempt, naming the conflict and the environment failure.

#### Scenario: Derived merge without OpenSpec CLI

- **GIVEN** a blocked-retryable candidate waiting for exact-head required checks
- **WHEN** its derived merge stops because the coordinator lacks the OpenSpec CLI
- **THEN** its state and attempts are unchanged and its reason names the environment failure on that head

#### Scenario: Real conflict of a waiting candidate

- **WHEN** a waiting candidate without a red gate conflicts with main outside generated files
- **THEN** it moves to integration-repair-pending and the integration-repair attempt is counted

#### Scenario: Derived merge unavailable with a real conflict

- **GIVEN** a waiting candidate whose merge with main conflicts outside generated files
- **WHEN** its derived merge stops because the coordinator lacks the OpenSpec CLI
- **THEN** it moves to integration-repair-pending, the attempt is counted, and the reason names the conflict and the environment failure

#### Scenario: Generated-only conflict with derived merge unavailable

- **GIVEN** a waiting candidate whose merge with main conflicts only in a declared generated file
- **WHEN** the coordinator cannot run the derived merge
- **THEN** it moves to integration-repair-pending, the attempt is counted, and the integration repair regenerates the declared generated files
