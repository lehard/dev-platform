## ADDED Requirements

### Requirement: Transient queue failures are retried within a bound

The queue worker SHALL retry a transient failure of its candidate observation (`GET` of the candidate pull request) within a bounded backoff, logging each failed attempt with the PR, attempt number and error. Inside the queue's candidate observation only, HTTP 422 "too many files changed" SHALL count as transient. When the bound is spent the observation SHALL fail naming the PR, the attempts and the last error, and a run in which no candidate could be evaluated SHALL exit non-zero. A non-transient observation failure SHALL NOT be retried. A transient failure while integrating a candidate SHALL leave it `waiting` and SHALL record a consecutive-failure counter for its exact head in the candidate record; when the counter reaches the limit the candidate SHALL be blocked with a reason naming the head, the count and the error. A later evaluation of the same head without a transient failure SHALL reset the counter, and a new head SHALL start with no count.

#### Scenario: Transient observation then success
- **WHEN** reading an admitted PR fails with HTTP 422 "too many files changed" and a later attempt of the same read succeeds within the bound
- **THEN** the candidate is evaluated in the same run
- **AND** each failed attempt is logged

#### Scenario: Persistent observation failure
- **WHEN** every attempt of the bounded observation fails transiently
- **THEN** the run reports the PR as not observable naming the attempts and error
- **AND** a run where no candidate was observable exits non-zero

#### Scenario: Non-transient observation failure
- **WHEN** the observation fails with a non-transient error
- **THEN** it is not retried and is reported naming the PR

#### Scenario: Repeated transient integration failure
- **GIVEN** an admitted candidate whose integration fails transiently on head H
- **WHEN** this happens in consecutive runs
- **THEN** each run leaves it `waiting` with the counter for H visible in its record
- **AND** the run that reaches the limit blocks it with a reason naming H, the count and the error

#### Scenario: Counter reset
- **WHEN** a later run evaluates the same head without a transient failure, or the candidate moves to a new head
- **THEN** the next transient failure counts from one
