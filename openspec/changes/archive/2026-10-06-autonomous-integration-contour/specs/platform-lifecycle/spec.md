## ADDED Requirements

### Requirement: Post-handoff lifecycle obligations are coordinator jobs

After developer handoff, friction capture for review, repair, integration, fallback and retry events, the task and Requirement retrospectives, terminal reconciliation of Issue/Project/Requirement state and safe local worktree cleanup SHALL be performed by coordinator-published jobs. Events SHALL be attributed to the candidate task and its parent Requirement, and a Requirement retrospective SHALL accept events attributed to its linked children. No manual completion pass SHALL be required on the happy path.

#### Scenario: Child event in parent retrospective
- **GIVEN** a friction event recorded for a linked child task
- **WHEN** the Requirement retrospective checkpoint links it
- **THEN** it is accepted without re-recording the event

#### Scenario: Merge completes
- **WHEN** GitHub reports the candidate merged
- **THEN** terminal reconciliation and cleanup run as jobs without the developer session

#### Scenario: Retrospective cannot be completed truthfully
- **WHEN** friction attribution is ambiguous or an evidence source is unreadable
- **THEN** the retrospective job reports it and records no clean result

#### Scenario: Obligation job is interrupted or fails
- **WHEN** a post-merge job stops or reports a failed or blocked result
- **THEN** the same obligation is offered again within a bounded number of attempts and completed obligations are never repeated

#### Scenario: Local cleanup is unsafe
- **WHEN** the task worktree is dirty, active, outside the managed directory or holds commits absent from the merged PR
- **THEN** cleanup refuses, reports why, and changes nothing
