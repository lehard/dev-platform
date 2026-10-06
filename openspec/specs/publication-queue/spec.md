# publication-queue Specification

## Purpose
Coordinate final publication of independent Dev Platform changes through one durable order while retaining protected GitHub integration.

## Requirements

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

- **WHEN** task-owned content changes, or a merge conflict prevents exact preparation
- **THEN** the coordinator does not merge under old evidence
- **AND** the candidate has an explained block or an integration-repair job and a supported recovery action.

#### Scenario: Required check fails or main moves during final check

- **WHEN** the required check fails, or main advances before the guarded merge
- **THEN** the coordinator does not claim Done
- **AND** it either performs a bounded fresh-base retry or integration repair, or reports the exact blocker.

### Requirement: Queue recovers to an unambiguous outcome

The queue SHALL survive loss of an agent or coordinator process. A later coordinator invocation SHALL derive its next action from current GitHub PR, comment, label, head and check state. It SHALL report merged, waiting, needs-fix, or blocked with a reason and safe continuation; remote merge SHALL still require existing local terminal reconciliation.

#### Scenario: Runner exits after branch update

- **WHEN** a later run sees the coordinator-updated PR head and pending checks
- **THEN** it resumes that candidate without a new PR or branch rewrite.

#### Scenario: Remote merge completes before agent resumes

- **WHEN** GitHub reports the exact task PR merged
- **THEN** queue status reports the remote result
- **AND** normal finish performs remaining local and managed-task reconciliation before full Done.

### Requirement: Queue coordinator runs trusted code with a least-privilege token

The publication queue workflow SHALL execute only code from the protected default branch for every trigger, including the `publication:queued` label event, and SHALL NOT check out or execute pull-request-controlled content while holding the Dev Platform GitHub App token. The App token SHALL be scoped to the current repository and to only the permissions the coordinator uses (contents write and pull requests write). Protected publication, required checks, the expected-head merge guard and the absence of bypass or force semantics SHALL be unchanged.

#### Scenario: Pull request is labeled for the queue

- **WHEN** a pull request receives the `publication:queued` label
- **THEN** the coordinator runs the workflow and worker from the default branch
- **AND** no pull-request-controlled file is executed with the App token

#### Scenario: Token is created for the coordinator

- **WHEN** the workflow creates the GitHub App token
- **THEN** the token is limited to the current repository and to contents write and pull requests write
- **AND** no workflows, administration or other permission is requested

### Requirement: Coordinator tracks durable candidate lifecycle states

The publication coordinator SHALL derive each candidate's state (review-pending, reviewing, repair-pending, repairing, finalize-pending, ready, integrating, integration-repair-pending, merged, blocked-retryable, blocked-escalation) from GitHub PR head, checks, labels and immutable versioned marker comments, without a second journal or state store. Existing v1 queue markers SHALL remain readable.

#### Scenario: Coordinator restarts mid-review
- **GIVEN** a candidate marked reviewing for its exact head
- **WHEN** a new coordinator run starts
- **THEN** it derives the same state and next action from GitHub

#### Scenario: Head changes
- **WHEN** the PR head differs from the head in the latest marker
- **THEN** the candidate is not treated as having passed gates bound to the old head

### Requirement: Every transition publishes a structured handoff record

Each coordinator transition SHALL publish a record naming the candidate head, task-content identity, satisfied gates with the identity they verified, the failing gate and its evidence, items not re-verified, attempt counters and the next job, so a later executor can continue without reconstructing history.

#### Scenario: Repair follows a review failure
- **WHEN** a review finding moves the candidate to repair-pending
- **THEN** the record names the finding, the reviewed identity and the checks already satisfied

### Requirement: Candidate and Requirement status is read-only and actionable

A read-only status SHALL show for a candidate and for a Requirement the current state, active job or claim, attempts, red gate, evidence bindings and the next automatic or human action, from any execution location.

#### Scenario: Operator checks a Requirement
- **WHEN** status is requested for a Requirement
- **THEN** it lists each candidate's state and next action without mutating anything

### Requirement: Archive-derived spec conflicts are re-derived deterministically

When preparing a candidate on current main, conflicts confined to archive-derived current-spec paths SHALL be resolved by re-applying the candidate's archived delta specs on the actual base. A failed re-application SHALL become integration repair. A successful re-application SHALL be bookkeeping only: it SHALL NOT replace required checks on the actual candidate and SHALL NOT mask a semantic or contract conflict.

#### Scenario: Two candidates extend one capability
- **GIVEN** candidate A merged a change to a capability spec
- **WHEN** candidate B, archived earlier against older main, is prepared
- **THEN** B's deltas are re-applied on the new spec and checks run on the result

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
