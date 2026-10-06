## MODIFIED Requirements

### Requirement: Coordinator verifies the actual current-base candidate

One repository-owned coordinator SHALL process the next eligible PR after the prior merge, prepare its exact head on current main without rewriting task-owned content, require protected GitHub checks on that actual candidate, and request merge with an expected-head guard. An ordinary unrelated preceding queue merge SHALL NOT require each waiting task agent to manually reconcile and repeat a full local validation pass. Required CI and branch protection SHALL NOT be bypassed.

#### Scenario: Earlier queued PR advances main

- **GIVEN** candidate B waits behind candidate A and their task paths do not overlap
- **WHEN** A merges
- **THEN** B is prepared and checked on the new main by the coordinator
- **AND** B merges only after its actual updated head satisfies required checks.

#### Scenario: Main or candidate changes materially

- **WHEN** task-owned content changes, or a merge conflict prevents exact preparation
- **THEN** the coordinator does not merge under old evidence
- **AND** the candidate has an explained block or an integration-repair job and a supported recovery action.

#### Scenario: Required check fails or main moves during final check

- **WHEN** the required check fails, or main advances before the guarded merge
- **THEN** the coordinator does not claim Done
- **AND** it either performs a bounded fresh-base retry or integration repair, or reports the exact blocker.

## ADDED Requirements

### Requirement: Integration repairs real conflicts within a bound

The coordinator SHALL integrate ready candidates one at a time against current main using a clean deterministic merge and required checks on the actual candidate. Path overlap alone SHALL NOT block. A real merge conflict or failing integration check SHALL create an integration-repair job; if repair changes task-content identity, prior review, finalization and archive evidence become stale and the candidate returns through review and finalization; otherwise existing evidence is reused. After a bounded number of attempts the candidate SHALL become blocked.

#### Scenario: Overlapping but clean candidate
- **WHEN** main changed paths the candidate also changed and the merge is clean
- **THEN** the candidate proceeds to checks on the merged head

#### Scenario: Conflict changes task content
- **WHEN** integration repair resolves a conflict by changing task content
- **THEN** the candidate is reviewed and finalized again before merge

### Requirement: A blocked candidate does not stop the queue

A candidate in a blocked state SHALL NOT prevent later independent ready candidates from integrating.

#### Scenario: Head candidate blocked
- **WHEN** the first ready candidate becomes blocked
- **THEN** the coordinator integrates the next ready candidate

#### Scenario: Repair bound is spent
- **GIVEN** a candidate whose integration-repair attempts reached the bound
- **WHEN** integration fails again
- **THEN** the candidate becomes blocked, leaves the queue, and later candidates still integrate

#### Scenario: Repair is interrupted
- **WHEN** an integration-repair job pushed its validated result but stopped before recording it
- **THEN** a later run derives the outcome from the validated-push receipt and records it exactly once
