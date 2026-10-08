## MODIFIED Requirements

### Requirement: Review and repair run as candidate jobs

Independent Review for a coordinator-managed candidate SHALL run as a job on the exact PR head with the existing fresh-context, read-only and two-perspective guarantees. A fixable finding SHALL produce a bounded repair job executed without the original developer; changed task content SHALL make review stale. A proposal to reject a material finding, or exhausted repair rounds, SHALL move the candidate to blocked-escalation.

Jobs SHALL retain the originating task's resolved reviewer provider or explicitly configured ordered providers across repair and retry until an operator re-offers the job on other supported providers. Workers SHALL NOT substitute their local route. An unavailable provider runtime (login, usage limit or failure to start) during review or repair SHALL leave the candidate blocked-retryable with a named provider-unavailable cause and SHALL NOT escalate it or spend a repair round. Unavailable review or repair SHALL retry the same round at most three consecutive attempts, then remain blocked-retryable with unavailable evidence and no automatic job until an operator resumes it. A repair writer that fails while its runtime is usable SHALL still be an operational escalation. Publication SHALL leave review-owned and repair-owned retry states untouched. Workers SHALL confirm unexpired ownership of the exact job and originating head immediately before push and candidate advancement; lost ownership SHALL abandon without further side effects. Repair SHALL reject lifecycle evidence paths at any depth, including evidence directories. A trusted repair completion published before interrupted advancement SHALL recover on the next run without rerunning the writer.

#### Scenario: Finding is repaired
- **GIVEN** review reports a fixable material finding
- **WHEN** the repair job changes task content
- **THEN** review runs again for the new identity

#### Scenario: Rejection proposed
- **WHEN** a worker proposes rejecting a material finding
- **THEN** the candidate waits for a human decision

#### Scenario: Provider limit during repair
- **GIVEN** a repair writer exits non-zero and the provider runtime then fails its readiness probe
- **WHEN** the worker records the outcome
- **THEN** the candidate is blocked-retryable with a provider-unavailable cause naming the limitation
- **AND** the repair round count is unchanged and the same round is offered again

#### Scenario: Repair fails with a usable runtime
- **GIVEN** a repair writer exits non-zero and the provider runtime passes its readiness probe
- **WHEN** the worker records the outcome
- **THEN** the candidate is blocked-escalation

#### Scenario: Provider unavailable repeatedly
- **WHEN** the same round is unavailable three consecutive attempts
- **THEN** the candidate remains blocked-retryable with unavailable evidence and no automatic job

#### Scenario: Unavailable runtime during review
- **WHEN** a review finds its provider runtime unavailable
- **THEN** the candidate is blocked-retryable and its record names the provider-unavailable cause and limitation
