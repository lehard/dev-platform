# publication-queue Specification

## Purpose

Coordinate final publication of independent Dev Platform changes through one durable order while retaining protected GitHub integration.

## ADDED Requirements

### Requirement: Ready candidates have durable ordered admission

The central source lifecycle SHALL admit an exact, locally verified and archived task PR to a GitHub-backed FIFO queue. Admission SHALL be idempotent for the same PR and validated head, record an observable ordering key, and expose the candidate's position, current owner/phase and waiting reason after agent restart. Implementation worktrees SHALL remain independent.

#### Scenario: Two independent agents finish together

- **GIVEN** two distinct verified task PRs are admitted concurrently
- **WHEN** either agent or a later session observes status
- **THEN** both have a stable visible queue order
- **AND** at most one candidate has active final integration ownership.

#### Scenario: Admission is retried after lost output

- **WHEN** the same exact PR/head is admitted again
- **THEN** the existing queue entry is reused
- **AND** no duplicate PR, ordering slot or merge is created.

### Requirement: Coordinator verifies the actual current-base candidate

One repository-owned coordinator SHALL process the next eligible PR after the prior merge, prepare its exact head on current main without rewriting task-owned content, require protected GitHub checks on that actual candidate, and request merge with an expected-head guard. An ordinary unrelated preceding queue merge SHALL NOT require each waiting task agent to manually reconcile and repeat a full local validation pass. Required CI and branch protection SHALL NOT be bypassed.

#### Scenario: Earlier queued PR advances main

- **GIVEN** candidate B waits behind candidate A and their task paths do not overlap
- **WHEN** A merges
- **THEN** B is prepared and checked on the new main by the coordinator
- **AND** B merges only after its actual updated head satisfies required checks.

#### Scenario: Main or candidate changes materially

- **WHEN** task-owned content changes, relevant main paths overlap, or a merge conflict prevents exact preparation
- **THEN** the coordinator does not merge under old evidence
- **AND** the candidate has an explained block and supported agent recovery action.

#### Scenario: Required check fails or main moves during final check

- **WHEN** the required check fails, or main advances before the guarded merge
- **THEN** the coordinator does not claim Done
- **AND** it either performs a bounded fresh-base retry or reports the exact blocker.

### Requirement: Queue recovers to an unambiguous outcome

The queue SHALL survive loss of an agent or coordinator process. A later coordinator invocation SHALL derive its next action from current GitHub PR, comment, label, head and check state. It SHALL report merged, waiting, needs-fix, or blocked with a reason and safe continuation; remote merge SHALL still require existing local terminal reconciliation.

#### Scenario: Runner exits after branch update

- **WHEN** a later run sees the coordinator-updated PR head and pending checks
- **THEN** it resumes that candidate without a new PR or branch rewrite.

#### Scenario: Remote merge completes before agent resumes

- **WHEN** GitHub reports the exact task PR merged
- **THEN** queue status reports the remote result
- **AND** normal finish performs remaining local and managed-task reconciliation before full Done.
