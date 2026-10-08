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

### Requirement: Operators re-offer review and repair jobs on another provider

The coordinator SHALL provide a supported operator command that re-offers an open candidate's review or repair job on an explicit ordered list of supported providers. It SHALL append one head-bound record that preserves task identity, gates, findings and every attempt counter, offers the job as a distinct re-offer of the same attempt, and records the previous and new providers, the reason and the time. It SHALL spend no retry or repair round and SHALL NOT require closing the PR or a new developer handoff. It SHALL refuse a candidate whose job holds an unexpired claim, a state that is not an unfinished review or repair, a merged or closed PR, and an unsupported or duplicated provider. Switching an unfinished pending job to the providers it already names SHALL change nothing. Later retries, repair and review jobs of the candidate SHALL follow the new providers.

#### Scenario: Switch an open candidate
- **GIVEN** a review-pending candidate whose job names codex and has no live claim
- **WHEN** the operator switches it to claude with a reason
- **THEN** the candidate remains review-pending with its gates and attempts unchanged
- **AND** its job names claude and records codex as the previous provider and the reason
- **AND** the former job is no longer the candidate's job

#### Scenario: Switch under a live claim
- **WHEN** the operator switches a candidate whose job has an unexpired claim
- **THEN** the command refuses naming the claim and nothing is published

#### Scenario: Repair keeps its findings
- **WHEN** a repair-pending candidate is switched
- **THEN** the repair job still receives the candidate's findings

### Requirement: Operational escalation has a supported exit

The coordinator SHALL provide a supported operator command that resumes a blocked-retryable review or repair candidate (typically one whose automatic retries are exhausted), and a blocked-escalation candidate whose escalation is an operational repair outcome (worker failure, harness rejection or no change), after a human decision. The command SHALL require a reason, SHALL accept a provider list, SHALL restore the findings-bearing red gate from the failed review or required-checks gate, and SHALL re-offer the same round without spending budget. It SHALL refuse finding-level escalation (proposed rejection, exhausted rounds, rejected review), malformed records and closed PRs with a message naming the human actions available. A candidate escalated before its providers were recorded SHALL require an explicit provider.

#### Scenario: Repair worker failed
- **GIVEN** a candidate escalated after a failed repair writer
- **WHEN** the operator resumes it with a reason
- **THEN** it returns to repair-pending on the same round with its findings

#### Scenario: Exhausted rounds
- **WHEN** the operator resumes a candidate escalated for exhausted repair rounds
- **THEN** the command refuses and names pushing a fix, recording a disposition or closing the PR

### Requirement: Coordinator configuration preflight

The publication coordinator SHALL validate its required configuration through one repository-owned preflight entrypoint before it observes any candidate. The preflight SHALL be run in an explicit mode (CI or local) and phase (inputs, runtime or all), SHALL prove the coordinator App identity, trust configuration, token scope, write permission and runtime inputs, and SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input. Its output SHALL NOT contain credential values, and a missing or invalid required input SHALL NOT be replaced by a default or alternate strategy. The `publication-queue` workflow SHALL run the inputs phase before minting the App token without passing secret values to the preflight, and the runtime phase before candidate work; the worker command SHALL run the full preflight itself.

#### Scenario: Valid configuration

- **WHEN** every required App, trust, permission and runtime input is proven
- **THEN** the preflight exits zero and the worker proceeds to observe candidates

#### Scenario: Missing input stops before candidate work

- **WHEN** a required variable or secret presence flag, run identifier, tool or App slug is missing
- **THEN** the preflight exits non-zero naming that input
- **AND** no pull request, comment or label is read or written

#### Scenario: Contradictory App identity

- **WHEN** the App slug exported by the workflow differs from the configured `[publication] coordinator_app`, or the trust configuration cannot be read as valid
- **THEN** startup fails naming the contradiction or the unreadable source
- **AND** no trusted set is silently narrowed or widened

#### Scenario: Insufficient token or permission

- **WHEN** the token is not an installation token for the current repository or the coordinator App lacks write permission
- **THEN** the preflight fails naming the check category

#### Scenario: Secret-safe diagnostics

- **WHEN** any preflight check fails
- **THEN** stdout, stderr and the JSON result identify only input names and fixed categories
- **AND** no token, private key or API response body appears

### Requirement: Coordinator friction evidence is durable on the candidate pull request

Meaningful lifecycle and friction events recorded by the coordinator SHALL be persisted as a trusted, versioned evidence comment on the candidate pull request through the existing authenticated lifecycle comment channel, before the transition that produced them is published. Each record SHALL bind the Requirement (or prove none), pull request number, exact head, lifecycle stage and the worker run identity, SHALL be idempotent per dedupe key, and SHALL be authenticated by the same trust rules as other lifecycle markers. A persistence failure SHALL fail the transition and the run visibly; the coordinator SHALL NOT proceed with machine-local-only evidence.

#### Scenario: Ephemeral runner ends

- **WHEN** a coordinator run on an ephemeral runner records friction for a candidate and the runner is discarded
- **THEN** a trusted evidence record bound to the Requirement, head, stage and worker remains on the pull request

#### Scenario: Retried transition

- **WHEN** an interrupted or scheduled run repeats the same transition for the same head and attempts
- **THEN** no second evidence record is posted

#### Scenario: Forged or malformed record

- **WHEN** an evidence comment is authored by an untrusted account
- **THEN** it is ignored
- **WHEN** a trusted evidence record is malformed or contradicts its pull request or head
- **THEN** reading it raises a named error and is not skipped

#### Scenario: Persistence fails

- **WHEN** the evidence comment cannot be posted or the Requirement lineage cannot be resolved
- **THEN** the handoff record for the transition is not published
- **AND** the worker exits non-zero stating the persistence failure

### Requirement: Handoff records the originating task route

The developer handoff that admits a candidate SHALL record the originating task's executor route (provider, profile and change) in the authenticated handoff record, resolved from the task's durable routing evidence in the developer checkout. Later lifecycle jobs for the candidate SHALL take their provider from that record rather than from the coordinator checkout, and a missing, unreadable, mismatched or unsupported route SHALL fail explicitly instead of publishing a job for a default or unresolved provider.

#### Scenario: Coordinator publishes repair from another checkout

- **WHEN** a required-check or integration failure makes the coordinator publish a repair job from a checkout whose own task route differs
- **THEN** the job names the provider recorded on the candidate's handoff

#### Scenario: Route cannot be resolved at handoff

- **WHEN** the developer checkout has no valid routing evidence for the task's change
- **THEN** admission fails with an error naming the change and writes no admission comment

#### Scenario: Candidate has no recorded route

- **WHEN** a repair or integration-repair job is to be published for a candidate whose record carries no route, or whose recorded change differs from its task identity
- **THEN** publication fails explicitly asking for a new developer handoff and no job is published

#### Scenario: Route is stable across head changes

- **WHEN** the candidate head advances within the same task
- **THEN** the recorded route is inherited by the new exact-head record
