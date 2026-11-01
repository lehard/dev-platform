## ADDED Requirements

### Requirement: A coordinator environment failure is visible on the candidate

When integration stops on a coordinator environment failure and the merge with main has no real conflict, the queue SHALL post a note naming the head and the failure, change no state, post no block and spend no attempt; the run still fails. Status SHALL show the note as the reason until a later record supersedes it. A real conflict SHALL go to integration-repair-pending, spending an attempt, naming the conflict and the environment failure.

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
