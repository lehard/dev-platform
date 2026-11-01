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

One repository-owned coordinator SHALL process the next eligible PR after the prior merge, prepare its exact head on current main without rewriting task-owned content, require protected GitHub checks on that actual candidate, and request merge with an expected-head guard.

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

#### Scenario: Two reviewed candidates and main moves before the second finalizes

- **GIVEN** two independent candidates A and B have both passed independent review
- **WHEN** A merges and advances `main` before B is finalized
- **THEN** B is finalized without merging `main` and without developer action
- **AND** the coordinator merges current `main` into B, runs required CI on the merged head and merges B

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

The publication queue workflow SHALL execute only code from the protected default branch for every trigger, including the `publication:queued` label event, and SHALL NOT check out or execute pull-request-controlled content while holding the Dev Platform GitHub App token.

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

The coordinator SHALL integrate ready candidates one at a time against current main using a clean deterministic merge and required checks on the actual candidate. Path overlap alone SHALL NOT block.

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

The coordinator SHALL provide a supported operator command that re-offers an open candidate's review or repair job on an explicit ordered list of supported providers.

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

The coordinator SHALL provide a supported operator command that resumes a blocked-retryable review or repair candidate (typically one whose automatic retries are exhausted), and a blocked-escalation candidate whose escalation is an operational repair outcome (worker failure, harness rejection or no change), after a human decision.

#### Scenario: Repair worker failed
- **GIVEN** a candidate escalated after a failed repair writer
- **WHEN** the operator resumes it with a reason
- **THEN** it returns to repair-pending on the same round with its findings

#### Scenario: Exhausted rounds
- **WHEN** the operator resumes a candidate escalated for exhausted repair rounds
- **THEN** the command refuses and names pushing a fix, recording a disposition or closing the PR

### Requirement: Coordinator configuration preflight

The publication coordinator SHALL validate its required configuration through one repository-owned preflight entrypoint before it observes any candidate.

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

Meaningful lifecycle and friction events recorded by the coordinator SHALL be persisted as a trusted, versioned evidence comment on the candidate pull request through the existing authenticated lifecycle comment channel, before the transition that produced them is published.

#### Scenario: Ephemeral runner ends

- **WHEN** a coordinator run on an ephemeral runner records friction for a candidate and the runner is discarded
- **THEN** a trusted evidence record bound to the Requirement's work identity, head, stage and worker remains on the pull request
- **AND** the Requirement retrospective lists it for that Requirement

#### Scenario: Retried transition

- **WHEN** an interrupted or scheduled run repeats the same transition for the same head and attempts
- **THEN** no second evidence record is posted

#### Scenario: Forged or malformed record

- **WHEN** an evidence comment is authored by an untrusted account
- **THEN** it is ignored
- **WHEN** a trusted evidence record is malformed or contradicts its pull request or head
- **THEN** reading it raises a named error and is not skipped

#### Scenario: Persistence fails

- **WHEN** the evidence comment cannot be posted or the Requirement work identity cannot be derived from a managed branch
- **THEN** the handoff record for the transition is not published
- **AND** the worker exits non-zero stating the persistence failure

### Requirement: Handoff records the originating task route

The developer handoff that admits a candidate SHALL record the originating task's executor route (provider, profile and change) in the authenticated handoff record, resolved from the task's durable routing evidence in the developer checkout.

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

### Requirement: Complete validated lifecycle comment history

The platform SHALL read the complete ordered PR comment history needed for lifecycle marker replay, including histories exceeding one GitHub API page. It SHALL validate the complete observation before returning comments to lifecycle consumers. A transport error or malformed page, comment record or ordering SHALL fail explicitly with an error naming comment-history acquisition and SHALL NOT yield a truncated or filtered history.

#### Scenario: History spans multiple pages

- **WHEN** a PR has 101 or more comments and a lifecycle marker occurs after the first 100 comments
- **THEN** the history reader returns every comment in API order and the marker is available to the existing authenticated replay rules

#### Scenario: History ends at an exact page boundary

- **WHEN** the complete history contains exactly 100 or 200 comments
- **THEN** the reader returns the complete history without treating a full page as an error

#### Scenario: Empty history

- **WHEN** GitHub returns a valid empty comment page
- **THEN** the reader returns an empty history

#### Scenario: Missing response is not an empty history

- **WHEN** the response body is empty or contains no pages
- **THEN** the operation fails explicitly instead of returning an empty history

#### Scenario: Later page is unavailable

- **WHEN** pagination fails after an earlier page was received
- **THEN** the operation fails with an error naming comment-history acquisition and no earlier-page prefix is consumed

#### Scenario: Malformed observation

- **WHEN** the response contains invalid JSON, a non-array page, a non-object comment record, a record without an integer id, or ids that are not strictly increasing in API order
- **THEN** the operation fails explicitly without dropping records or returning a partial history

### Requirement: Exact-head required-check observation

The platform SHALL derive the required-check state of a pull request from valid structured GitHub check output.

#### Scenario: Successful check snapshot

- **WHEN** gh returns a valid JSON list whose required checks all passed on the expected head
- **THEN** the observation is passed

#### Scenario: Pending check snapshot

- **WHEN** gh returns a valid JSON list containing an in-progress required check on the expected head
- **THEN** the observation is pending and the coordinator waits without blocking the candidate

#### Scenario: Failed check snapshot

- **WHEN** gh returns a valid JSON list containing a failed required check on the expected head
- **THEN** the observation is failed and the candidate enters the bounded repair path instead of a terminal block

#### Scenario: Contribution uses the main branch's required checks

- **WHEN** a contribution pull request targets an unprotected `requirement/BR-<n>` integration branch and main requires the `validate` check
- **THEN** the observation is derived from the contribution's `validate` check, a missing `validate` row is pending as `EXPECTED`, and the contribution can record a passed required-checks gate once `validate` succeeds

#### Scenario: Contribution preserves required App binding

- **WHEN** main requires a check from a specific App and a contribution has a successful check of the same name from another App
- **THEN** that success does not satisfy the requirement; the required App's missing run remains pending, and only its exact-head run determines the bound check state

#### Scenario: Base branch requires no checks

- **WHEN** gh reports no required checks for a main-targeted pull request and the base branch protection requires no status checks
- **THEN** the observation is not-registered with a detail naming the base branch, decided from branch protection rather than CLI text

#### Scenario: Unusable observation

- **WHEN** gh exits with an unexpected status, its output is not valid JSON, or the PR head differs from the expected head before or after the checks are read
- **THEN** the observation is unusable with a cause of transport, malformed or head-mismatch and cannot authorize publication

#### Scenario: Transport or head fault does not terminally block

- **WHEN** the coordinator receives an unusable observation caused by transport failure or head mismatch while integrating a candidate
- **THEN** it reports a non-terminal waiting result naming the cause and does not mark the candidate blocked

#### Scenario: Required checks not yet reported on a fresh head

- **WHEN** gh reports no required checks for a main-targeted pull request whose base protection requires `validate`, because GitHub has not yet attached any check to the head the coordinator just produced
- **THEN** the observation is pending with an `EXPECTED` `validate` row and a detail naming it, and the coordinator keeps waiting instead of blocking the candidate
- **AND** the candidate integrates once `validate` passes on that head

#### Scenario: Required checks never reported within the bound

- **WHEN** the coordinator's integration check wait expires while every required check of the head is still `EXPECTED`
- **THEN** the candidate is blocked with a reason naming the unreported checks and the bound
- **AND** it is never integrated without passed required checks

### Requirement: Trust configuration fails closed

The platform SHALL read every configured coordinator trust source under its explicit configuration contract and SHALL raise an error naming the source when a configured source is unreadable or invalid. It SHALL NOT silently narrow the trusted set. Only the documented absence of an optional source (unset environment variable, no project config, disabled operator config, no publication table or key) SHALL be treated as no contribution from that source.

#### Scenario: Invalid trust source

- **WHEN** the platform config cannot be parsed, an enabled operator config is missing or invalid, the publication table is not a table, or the configured coordinator App is not a string
- **THEN** the operation fails explicitly naming the source and no trusted set is derived

#### Scenario: Absent optional source

- **WHEN** the operator config is disabled or no publication table is configured
- **THEN** the remaining valid sources define the trusted set without error

#### Scenario: Consumers do not continue with narrowed trust

- **WHEN** a lifecycle consumer (admission or a lifecycle worker) needs the trusted set and a configured source is invalid
- **THEN** the consumer stops with the named error instead of continuing

### Requirement: Managed admission requires exact task-content provenance

The platform SHALL require valid exact task-content provenance, bound to the admitted head, before admitting a managed candidate, and SHALL fail explicitly when that provenance is missing, unreadable, invalid or cannot be bound to the admitted head. A failure to obtain managed provenance SHALL NOT produce a quick-task branch/head identity. Only a candidate that the validated lifecycle identifies as a genuine quick task without a managed package SHALL receive the quick-task identity.

#### Scenario: Managed proof unavailable

- **WHEN** a managed candidate's task state is unreadable, its checkout is not at the admitted head, or its task-content proof is missing or has no digest
- **THEN** admission fails with an error naming the missing provenance and writes no admission record or branch/head identity

#### Scenario: Managed package missing

- **WHEN** managed state names a change with no active or archived package
- **THEN** admission fails before writing any admission record or mutating labels, even if a digest can be computed

#### Scenario: Valid managed proof

- **WHEN** the managed task state and exact task-content proof are valid at the admitted head
- **THEN** admission binds the task-content digest and only the archived-verification evidence that is readable and successful

#### Scenario: Malformed archived verification evidence

- **WHEN** the archived automated-checks evidence of a managed task is unreadable or malformed
- **THEN** admission fails explicitly instead of continuing without the gate

#### Scenario: Genuine quick task

- **WHEN** the candidate has no managed task state and its head touches no OpenSpec change
- **THEN** the existing quick-task exact-head identity applies without disguising a managed proof failure

### Requirement: Local coordinator run is observe-only

Only the CI `publication-queue` workflow, acting as the coordinator GitHub App, SHALL integrate or merge candidates into `main`.

#### Scenario: Local run does not integrate

- **WHEN** an operator runs `publication_queue.py worker --mode local`
- **THEN** it exits non-zero naming the CI coordinator and the `status` and `preflight --mode local` commands
- **AND** no pull request, comment, label or branch is read, written or merged

#### Scenario: Local diagnostics without App token

- **GIVEN** a local `gh` login without any App token
- **WHEN** an operator runs `status` or `preflight --mode local`
- **THEN** both commands complete
- **AND** the local preflight does not probe or require repository push permission

### Requirement: Coordinator merge is a REST merge with an expected-head guard

The coordinator SHALL request the protected merge of a candidate through the GitHub REST merge endpoint with the squash method and the expected head commit, so that GitHub itself evaluates branch rules, ruleset bypass for the coordinator App and required checks. It SHALL NOT use a client that refuses on its own reading of the merge state, SHALL NOT request an administrator override or auto-merge, and SHALL report a refused merge as a waiting outcome with a bounded reason and no merge.

#### Scenario: Ruleset-protected main with App bypass

- **GIVEN** a green candidate whose base ref is restricted by a ruleset that the coordinator App may bypass for pull requests
- **WHEN** the coordinator requests the merge
- **THEN** it calls the REST merge endpoint with `merge_method=squash` and `sha` equal to the expected head
- **AND** a successful response leads to the merged transition after the merged fact is read back

#### Scenario: Merge refused

- **WHEN** the REST merge endpoint refuses (head changed, rule or required check)
- **THEN** the candidate stays waiting with the bounded refusal reason
- **AND** no administrator override, auto-merge or alternate merge call is attempted

### Requirement: Declared generated files are regenerated on integration

When preparing a candidate on current main, the coordinator SHALL treat files that its default branch declares generated in the committed check configuration as derived.

#### Scenario: Candidate conflicts with main only in the generated manifest
- **GIVEN** a ready candidate and a main that both changed neighbouring entries of the declared platform manifest
- **WHEN** the coordinator prepares the candidate
- **THEN** it pushes a coordinator merge with a regenerated manifest and records the update
- **AND** required checks run on that head, and after merge `generate_platform_manifest.py --check` passes on main

#### Scenario: Requirement composition conflicts with main only in the generated manifest
- **GIVEN** a ready Requirement composition candidate with archived children whose merge with main conflicts only in the declared platform manifest
- **WHEN** the coordinator runs the queue and the required checks pass on the coordinator merge
- **THEN** it pushes a fast-forward coordinator merge with a regenerated manifest, keeps the composition task-content identity, and merges the candidate in the same run
- **AND** it publishes no integration-repair or integration-merge job and no operator merge is needed

#### Scenario: Conflict in an ordinary file
- **GIVEN** a ready candidate whose merge with main conflicts in a file that is neither generated nor archive-derived
- **WHEN** the coordinator prepares the candidate
- **THEN** it offers integration repair as before and pushes nothing

#### Scenario: Regeneration fails
- **GIVEN** a candidate whose only conflict is in a declared generated file
- **WHEN** the declared regeneration command fails on the merged tree and succeeds on a pristine checkout of main
- **THEN** the coordinator offers integration repair naming the failure and pushes nothing

#### Scenario: Regeneration environment is missing
- **GIVEN** a candidate whose only conflict is in a declared generated file
- **WHEN** the declared regeneration command fails on a pristine checkout of main as well, for example because a dependency is not installed on the runner
- **THEN** the coordinator records nothing on the candidate and publishes no integration-repair job
- **AND** it still evaluates the other candidates and the run fails naming the command and the failure

### Requirement: A writer-needing repair is escalated to the operator

A candidate that enters `repair-pending` or `integration-repair-pending` needs a writer, and no writer SHALL be launched automatically for it.

#### Scenario: Integration repair is offered
- **WHEN** a real conflict makes the coordinator offer an integration-repair job for PR #N
- **THEN** PR #N gets one "Repair needed" attention comment with the conflict, the head and the `work-next --kinds integration-repair` command

#### Scenario: Review findings need repair
- **WHEN** independent review moves PR #N to `repair-pending`
- **THEN** PR #N gets one "Repair needed" attention comment naming the `repair` command

#### Scenario: Same round observed again
- **WHEN** the coordinator observes the same repair round again
- **THEN** no second attention comment is posted unless the first one is missing

#### Scenario: Integration merge needs no repair comment
- **WHEN** the coordinator offers an `integration-merge` job for PR #N
- **THEN** no "Repair needed" attention comment is posted for that round

### Requirement: A clean merge after a failed derived merge is integrated without a writer

When integration of a candidate fails on the `integration` gate and a trial merge of the candidate head with current main has no conflict, the coordinator SHALL offer an `integration-merge` job instead of an integration-repair job.

#### Scenario: Derived merge failed but the plain merge is clean
- **GIVEN** a candidate whose derived merge failed for a candidate reason and whose trial merge with main has no conflict
- **WHEN** the coordinator handles the integration failure
- **THEN** it records `integration-repair-pending` marked merge-only and publishes an `integration-merge` job without providers

#### Scenario: Integration merge succeeds
- **WHEN** a worker runs the claimed `integration-merge` job and the merge is clean
- **THEN** the harness pushes the merge of main without any writer and the candidate advances as after an integration repair

#### Scenario: Integration merge meets a conflict
- **WHEN** the merge of main conflicts at execution time
- **THEN** the job fails naming the conflicting paths and starts no writer
- **AND** the next attempt is an integration-repair job, or the candidate is blocked when the bound is spent

#### Scenario: Real conflict keeps integration repair
- **WHEN** the trial merge of the candidate with main conflicts in an ordinary file
- **THEN** the coordinator offers an integration-repair job as before

### Requirement: A developer fix re-admits a candidate waiting for integration repair

The coordinator SHALL accept a fresh developer handoff for a candidate whose latest record is `integration-repair-pending` when the record is bound to the proven integrated head, the handoff names the same task, the offered integration-repair job holds no live claim, and the new head descends from the proven head.

#### Scenario: Developer fix of a red integrated check is re-admitted
- **GIVEN** a candidate in `integration-repair-pending` after a required check failed on its integrated head, with no live claim on its integration-repair job
- **WHEN** the developer hands off a fix commit on top of the integrated head
- **THEN** the handoff is admitted for review and the integration-repair job is no longer offered

#### Scenario: Claimed integration repair refuses the developer fix
- **GIVEN** a candidate in `integration-repair-pending` whose integration-repair job is claimed by a live writer
- **WHEN** the developer hands off a fix
- **THEN** the handoff is refused naming the claim

#### Scenario: Unrelated head refuses the developer fix
- **GIVEN** a candidate in `integration-repair-pending`
- **WHEN** the developer hands off a head that does not descend from the integrated head
- **THEN** the handoff is refused naming the missing ancestry

### Requirement: An integration-repair writer receives the failed check's evidence

When integration repair is needed because a required check failed on the integrated candidate, the red gate SHALL record the identity of each failed required check, including its name and log link.

#### Scenario: Writer brief carries the failed log
- **GIVEN** an integration-repair job for a failed required check whose log is readable
- **WHEN** the operator runs the job
- **THEN** the writer brief names the failed check and includes the excerpt of its failed log

#### Scenario: Brief without evidence is refused
- **GIVEN** an integration-repair job for a failed required check whose red gate has no failed-check identity
- **WHEN** the operator runs the job
- **THEN** no writer starts and the run fails naming the missing evidence

### Requirement: Operator re-offers an exhausted post-merge obligation

The coordinator SHALL provide `publication_queue.py reoffer-post-merge --pr N --expected-head H --reason TEXT [--via LABEL]`.

#### Scenario: Exhausted cleanup re-offered
- **GIVEN** a merged PR whose cleanup obligation exhausted its attempts
- **WHEN** the operator runs `reoffer-post-merge` with the merged head and a reason
- **THEN** one record is appended with the incremented sequence, actor and reason
- **AND** the cleanup obligation is offered again with a fresh attempt budget

#### Scenario: Refusals before any write
- **WHEN** the PR is open, the expected head differs, nothing is exhausted, or a live claim holds the obligation
- **THEN** the command exits non-zero naming the cause and writes nothing

### Requirement: Transient queue failures are retried within a bound

The queue worker SHALL retry a transient failure of its candidate observation (`GET` of the candidate pull request) within a bounded backoff, logging each failed attempt with the PR, attempt number and error.

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

### Requirement: A developer re-handoff supersedes an unclaimed finalize-pending candidate

The coordinator SHALL accept a fresh developer handoff for a candidate whose latest record is `finalize-pending` when the record is bound to the proven head, the handoff names the same task, the offered finalize job holds no live claim, and the new head descends from the proven head.

#### Scenario: Reconciled finalize-pending candidate is re-admitted
- **GIVEN** a candidate in `finalize-pending` at its proven head whose finalize job holds no live claim
- **WHEN** the developer hands off a head that merged the moved main on top of the proven head
- **THEN** the handoff supersedes the finalize-pending admission and the candidate re-enters review

#### Scenario: Live finalize claim refuses the re-handoff
- **GIVEN** a candidate in `finalize-pending` whose finalize job is claimed by a live worker
- **WHEN** the developer hands off a descendant head
- **THEN** the handoff is refused naming the claim

#### Scenario: Rewritten head refuses the re-handoff
- **GIVEN** a candidate in `finalize-pending`
- **WHEN** the developer hands off a head that does not descend from the proven head
- **THEN** the handoff is refused naming the missing ancestry

### Requirement: Waiting task agents do not reconcile after an unrelated queue merge

An ordinary unrelated preceding queue merge SHALL NOT require each waiting task agent to manually reconcile and repeat a full local validation pass.

#### Scenario: An unrelated queue merge precedes a waiting candidate

- **GIVEN** a task agent's candidate waits in the queue
- **WHEN** an ordinary unrelated preceding queue merge lands
- **THEN** the task agent is not required to manually reconcile or repeat a full local validation pass

### Requirement: Queue integration bypasses no required CI or branch protection

Required CI and branch protection SHALL NOT be bypassed.

#### Scenario: The coordinator merges a candidate

- **WHEN** the coordinator merges a candidate
- **THEN** required CI and branch protection are not bypassed

### Requirement: Base actualization belongs to the coordinator's integration contour

Base actualization SHALL belong to the coordinator's integration contour alone, after finalization: the coordinator SHALL merge a clean result with current main automatically, SHALL run required CI on the actual merged head, and SHALL offer integration repair on a real conflict or a failing required check.

#### Scenario: A finalized candidate merges cleanly with current main

- **GIVEN** a finalized candidate
- **WHEN** it merges cleanly with current main
- **THEN** the coordinator merges it automatically and runs required CI on the actual merged head

#### Scenario: A finalized candidate conflicts with current main

- **GIVEN** a finalized candidate
- **WHEN** merging current main has a real conflict or a required check fails
- **THEN** the coordinator offers integration repair

### Requirement: A reviewed unchanged candidate needs no developer for finalization or base advance

Neither candidate finalization nor an advance of `main` by other PRs between review and finalization SHALL require developer involvement for a reviewed candidate whose task content is unchanged.

#### Scenario: Main advances between review and finalization

- **GIVEN** a reviewed candidate whose task content is unchanged
- **WHEN** other PRs advance `main` between review and finalization, and the candidate is finalized
- **THEN** no developer involvement is required

### Requirement: The queue App token is scoped to the coordinator's permissions

The Dev Platform GitHub App token SHALL be scoped to the current repository and to only the permissions the coordinator uses (contents write and pull requests write).

#### Scenario: The publication queue workflow mints the App token

- **WHEN** the publication queue workflow mints the Dev Platform GitHub App token
- **THEN** the token is scoped to the current repository
- **AND** it carries only contents write and pull requests write

### Requirement: Queue publication protections stay unchanged

Protected publication, required checks, the expected-head merge guard and the absence of bypass or force semantics SHALL be unchanged.

#### Scenario: The publication queue workflow publishes a candidate

- **WHEN** the publication queue workflow publishes a candidate
- **THEN** protected publication, required checks and the expected-head merge guard apply unchanged
- **AND** no bypass or force semantics are used

### Requirement: A real integration conflict creates an integration-repair job

A real merge conflict or failing integration check SHALL create an integration-repair job; if repair changes task-content identity, prior review, finalization and archive evidence become stale and the candidate returns through review and finalization; otherwise existing evidence is reused.

#### Scenario: Integration repair changes task content

- **GIVEN** a real merge conflict created an integration-repair job
- **WHEN** the repair changes task-content identity
- **THEN** prior review, finalization and archive evidence become stale
- **AND** the candidate returns through review and finalization

#### Scenario: Integration repair keeps task content

- **GIVEN** a failing integration check created an integration-repair job
- **WHEN** the repair keeps task-content identity
- **THEN** existing evidence is reused

### Requirement: Integration repair is bounded

After a bounded number of integration-repair attempts the candidate SHALL become blocked.

#### Scenario: Integration-repair attempts are exhausted

- **WHEN** a candidate spends the bounded number of integration-repair attempts
- **THEN** the candidate becomes blocked

### Requirement: A provider re-offer appends one head-bound record

The provider re-offer operator command SHALL append one head-bound record that preserves task identity, gates, findings and every attempt counter, offers the job as a distinct re-offer of the same attempt, and records the previous and new providers, the reason and the time.

#### Scenario: An operator re-offers a review job on another provider

- **WHEN** the provider re-offer operator command runs for an eligible review job
- **THEN** one head-bound record is appended preserving task identity, gates, findings and every attempt counter
- **AND** the job is offered as a distinct re-offer of the same attempt
- **AND** the record names the previous and new providers, the reason and the time

### Requirement: A provider re-offer spends no round

The provider re-offer operator command SHALL spend no retry or repair round and SHALL NOT require closing the PR or a new developer handoff.

#### Scenario: A repair job is re-offered on another provider

- **WHEN** the provider re-offer operator command re-offers a repair job
- **THEN** no retry or repair round is spent
- **AND** the PR is not closed and no new developer handoff is required

### Requirement: A provider re-offer refuses ineligible candidates

The provider re-offer operator command SHALL refuse a candidate whose job holds an unexpired claim, a state that is not an unfinished review or repair, a merged or closed PR, and an unsupported or duplicated provider.

#### Scenario: The job to re-offer holds an unexpired claim

- **WHEN** the provider re-offer operator command targets a candidate whose job holds an unexpired claim
- **THEN** the command refuses

#### Scenario: The provider list is unsupported or duplicated

- **WHEN** the provider re-offer operator command is given an unsupported or duplicated provider
- **THEN** the command refuses

### Requirement: Switching a pending job to its current providers changes nothing

Switching an unfinished pending job to the providers it already names SHALL change nothing.

#### Scenario: A pending job is switched to the same providers

- **GIVEN** an unfinished pending job naming providers A and B
- **WHEN** it is switched to providers A and B
- **THEN** nothing changes

### Requirement: Later jobs of a re-offered candidate follow the new providers

Later retries, repair and review jobs of the re-offered candidate SHALL follow the new providers.

#### Scenario: A re-offered candidate needs a later job

- **GIVEN** a candidate whose job was re-offered on new providers
- **WHEN** a later retry, repair or review job is offered for it
- **THEN** that job follows the new providers

### Requirement: The operator resume command restores the red gate and re-offers the same round

The operator resume command SHALL require a reason, SHALL accept a provider list, SHALL restore the findings-bearing red gate from the failed review or required-checks gate, and SHALL re-offer the same round without spending budget.

#### Scenario: An operator resumes a blocked-retryable candidate

- **WHEN** the operator resume command runs with a reason and a provider list
- **THEN** the findings-bearing red gate is restored from the failed review or required-checks gate
- **AND** the same round is re-offered without spending budget

#### Scenario: The operator resume command has no reason

- **WHEN** the operator resume command runs without a reason
- **THEN** the command refuses

### Requirement: The operator resume command refuses finding-level escalation

The operator resume command SHALL refuse finding-level escalation (proposed rejection, exhausted rounds, rejected review), malformed records and closed PRs with a message naming the human actions available.

#### Scenario: An operator resumes a finding-level escalation

- **GIVEN** a candidate escalated for exhausted rounds
- **WHEN** the operator resume command runs for it
- **THEN** the command refuses with a message naming the human actions available

### Requirement: Resuming a candidate escalated without recorded providers needs an explicit provider

A candidate escalated before its providers were recorded SHALL require an explicit provider when resumed.

#### Scenario: A candidate without recorded providers is resumed

- **GIVEN** a candidate escalated before its providers were recorded
- **WHEN** the operator resume command runs for it without a provider
- **THEN** the command refuses and requires an explicit provider

### Requirement: The coordinator preflight proves identity, trust, scope, permission and inputs

The coordinator preflight SHALL be run in an explicit mode (CI or local) and phase (inputs, runtime or all), and SHALL prove the coordinator App identity, trust configuration, token scope, write permission and runtime inputs.

#### Scenario: The coordinator preflight runs

- **WHEN** the coordinator preflight runs in an explicit mode and phase
- **THEN** it proves the coordinator App identity, trust configuration, token scope, write permission and runtime inputs

### Requirement: The coordinator preflight stops at the first failed check

The coordinator preflight SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input.

#### Scenario: A coordinator preflight check fails

- **WHEN** a coordinator preflight check fails
- **THEN** the preflight stops with a non-zero exit
- **AND** the diagnostic names the missing or contradictory input

### Requirement: The coordinator preflight output contains no credential values

The coordinator preflight output SHALL NOT contain credential values.

#### Scenario: The coordinator preflight reports its result

- **WHEN** the coordinator preflight prints its output
- **THEN** the output contains no credential values

### Requirement: A missing coordinator input is not replaced by a default

A missing or invalid required coordinator input SHALL NOT be replaced by a default or alternate strategy.

#### Scenario: A required coordinator input is missing

- **WHEN** a required coordinator input is missing or invalid
- **THEN** no default or alternate strategy replaces it

### Requirement: The publication-queue workflow runs the preflight phases before token and candidate work

The `publication-queue` workflow SHALL run the inputs phase of the coordinator preflight before minting the App token without passing secret values to the preflight, and the runtime phase before candidate work.

#### Scenario: The publication-queue workflow starts

- **WHEN** the `publication-queue` workflow starts
- **THEN** it runs the inputs phase before minting the App token without passing secret values to the preflight
- **AND** it runs the runtime phase before candidate work

### Requirement: The coordinator worker command runs the full preflight

The worker command SHALL run the full coordinator preflight itself.

#### Scenario: The coordinator worker command starts

- **WHEN** the worker command starts
- **THEN** it runs the full coordinator preflight itself

### Requirement: A coordinator evidence record binds the Requirement by public work identity

Each coordinator evidence record SHALL bind the Requirement through its public work identity derived from the managed candidate branch (or prove none for an unmanaged branch), and SHALL NOT contain a private Development Backlog reference.

#### Scenario: Evidence is recorded for a managed candidate branch

- **WHEN** the coordinator records evidence for a managed candidate branch
- **THEN** the record binds the Requirement through its public work identity derived from the branch
- **AND** it contains no private Development Backlog reference

#### Scenario: Evidence is recorded for an unmanaged branch

- **WHEN** the coordinator records evidence for an unmanaged branch
- **THEN** the record proves that no Requirement is bound

### Requirement: A coordinator evidence record binds the pull request, head, stage and run

Each coordinator evidence record SHALL bind the pull request number, exact head, lifecycle stage and the worker run identity.

#### Scenario: A coordinator evidence record is written

- **WHEN** a coordinator evidence record is written
- **THEN** it binds the pull request number, exact head, lifecycle stage and the worker run identity

### Requirement: A coordinator evidence record is idempotent and authenticated

Each coordinator evidence record SHALL be idempotent per dedupe key, and SHALL be authenticated by the same trust rules as other lifecycle markers.

#### Scenario: The same coordinator evidence is recorded twice

- **WHEN** a coordinator evidence record with an existing dedupe key is recorded again
- **THEN** no second record is created
- **AND** records are authenticated by the same trust rules as other lifecycle markers

### Requirement: A coordinator evidence persistence failure fails the transition

A persistence failure of coordinator evidence SHALL fail the transition and the run visibly; the coordinator SHALL NOT proceed with machine-local-only evidence.

#### Scenario: Coordinator evidence cannot be persisted

- **WHEN** persisting coordinator evidence on the pull request fails
- **THEN** the transition and the run fail visibly
- **AND** the coordinator does not proceed with machine-local-only evidence

### Requirement: Later lifecycle jobs take their provider from the handoff route

Later lifecycle jobs for the candidate SHALL take their provider from the authenticated handoff record rather than from the coordinator checkout, and a missing, unreadable, mismatched or unsupported route SHALL fail explicitly instead of publishing a job for a default or unresolved provider.

#### Scenario: A later lifecycle job is published

- **GIVEN** an admitted candidate whose authenticated handoff record names a route
- **WHEN** a later lifecycle job is published for it
- **THEN** its provider comes from the handoff record, not from the coordinator checkout

#### Scenario: The handoff route is unsupported

- **WHEN** the recorded route is missing, unreadable, mismatched or unsupported
- **THEN** publishing the job fails explicitly
- **AND** no job is published for a default or unresolved provider

### Requirement: The required-check set comes from the final protected target

The platform SHALL resolve the required-check set of a pull request from the pull request's final protected target (the main branch for main-targeted pull requests and for Requirement contribution pull requests targeting a `requirement/BR-<n>` integration branch).

#### Scenario: A Requirement contribution pull request is observed

- **GIVEN** a Requirement contribution pull request targeting a `requirement/BR-<n>` integration branch
- **WHEN** its required checks are resolved
- **THEN** the required set comes from the main branch

### Requirement: A required-check snapshot is bound to the expected head

The platform SHALL bind the required-check snapshot to the expected PR head both before and after reading the checks.

#### Scenario: Required checks are read for an expected head

- **WHEN** the platform reads the required checks of a pull request
- **THEN** it binds the snapshot to the expected PR head both before and after reading the checks

### Requirement: Unusable required-check observations carry a cause

Passed, pending, failed and not-registered observations SHALL remain distinct from unusable observations, which SHALL carry an explicit cause (transport failure, malformed output, head mismatch or unsupported state) and SHALL NOT authorize publication.

#### Scenario: Check output is malformed

- **WHEN** the check output is malformed
- **THEN** the observation is unusable with cause malformed output, distinct from passed, pending, failed and not-registered
- **AND** it does not authorize publication

### Requirement: The no-required-checks condition comes from base branch protection

The no-required-checks condition SHALL be resolved from the base branch's protection, not from CLI wording.

#### Scenario: A pull request may have no required checks

- **WHEN** the platform decides whether a pull request has no required checks
- **THEN** it resolves this from the base branch's protection, not from CLI wording

### Requirement: An unreported required context is pending

A required context that the protected target requires but that is not yet reported on the observed head SHALL be pending (`EXPECTED`), not unusable.

#### Scenario: A required context is not yet reported

- **GIVEN** a context the protected target requires
- **WHEN** it is not yet reported on the observed head
- **THEN** it is pending (`EXPECTED`), not unusable

### Requirement: The integration wait for unreported required checks is bounded

The coordinator's integration wait for required checks not yet reported on the observed head SHALL be bounded and SHALL end in an explicit block naming the unreported checks.

#### Scenario: Required checks stay unreported during integration

- **WHEN** required checks stay unreported on the observed head beyond the coordinator's bounded integration wait
- **THEN** the wait ends in an explicit block naming the unreported checks

### Requirement: Pending or repairable failed checks do not terminally block

A pending check or a repairable failed check SHALL NOT terminally block a candidate.

#### Scenario: A candidate has a pending check

- **WHEN** a candidate has a pending check or a repairable failed check
- **THEN** the candidate is not terminally blocked

### Requirement: An unusable check observation is reported with its cause

An unusable check observation SHALL be reported with its cause and SHALL NOT be substituted by an assumed state.

#### Scenario: A check observation is unusable

- **WHEN** a check observation is unusable
- **THEN** it is reported with its cause
- **AND** no assumed state replaces it

### Requirement: A local coordinator worker exits before any GitHub read

`publication_queue.py worker --mode local` SHALL NOT observe, prepare, integrate or merge any candidate: it SHALL exit non-zero before any GitHub read with a diagnostic that names the CI coordinator as the only integrator and points to `publication_queue.py status` and `publication_queue.py preflight --mode local`.

#### Scenario: An operator runs the worker locally

- **WHEN** `publication_queue.py worker --mode local` runs
- **THEN** it exits non-zero before any GitHub read
- **AND** the diagnostic names the CI coordinator as the only integrator and points to `publication_queue.py status` and `publication_queue.py preflight --mode local`

### Requirement: Queue status and local preflight need no App token

`status` and `preflight --mode local` of `publication_queue.py` SHALL work without an App token.

#### Scenario: Status runs without an App token

- **GIVEN** no App token is available
- **WHEN** `publication_queue.py status` or `publication_queue.py preflight --mode local` runs
- **THEN** it works

### Requirement: The local coordinator preflight needs no push permission

The local coordinator preflight SHALL NOT require repository push permission.

#### Scenario: The local preflight runs without push permission

- **GIVEN** the operator has no repository push permission
- **WHEN** `publication_queue.py preflight --mode local` runs
- **THEN** it does not fail for missing push permission

### Requirement: The coordinator regenerates conflicting declared generated files

When a merge of current main conflicts only in declared generated files and archive-derived current-spec paths, or a declared generated file changed both in main since the admission base and in the candidate, the coordinator SHALL merge in a disposable checkout, re-derive archive-derived specs as before, and regenerate each such file by running its declared command from the default-branch code over the merged tree.

#### Scenario: A merge conflicts only in a declared generated file

- **GIVEN** a merge of current main conflicts only in declared generated files and archive-derived current-spec paths
- **WHEN** the coordinator prepares the candidate
- **THEN** it merges in a disposable checkout, re-derives archive-derived specs and regenerates each such file with its declared command from the default-branch code over the merged tree

### Requirement: The coordinator pushes regenerated declared files as a recorded update

When a merge of current main conflicts only in declared generated files and archive-derived current-spec paths, or a declared generated file changed both in main since the admission base and in the candidate, the coordinator SHALL push the result of the regeneration as a recorded coordinator update whose parents are the claimed head and main.

#### Scenario: Declared generated files were regenerated on integration

- **GIVEN** a declared generated file changed both in main since the admission base and in the candidate
- **WHEN** the coordinator has regenerated it over the merged tree
- **THEN** it pushes the result as a recorded coordinator update whose parents are the claimed head and main

### Requirement: Required checks gate a regenerated coordinator update

Required checks SHALL run on the recorded coordinator update head and gate the merge unchanged.

#### Scenario: The coordinator pushed a regenerated update

- **WHEN** the coordinator pushes a recorded coordinator update
- **THEN** required checks run on that head and gate the merge unchanged

### Requirement: Unresolved generated-file integration becomes integration repair

A remaining conflict, a conflict in any file other than declared generated files and archive-derived current-spec paths, or a regeneration that fails on the merged tree while the same command succeeds on a pristine checkout of main SHALL become integration repair.

#### Scenario: Regeneration fails only on the merged tree

- **WHEN** a declared regeneration command fails on the merged tree but succeeds on a pristine checkout of main
- **THEN** the candidate becomes integration repair

#### Scenario: A merge conflicts in an ordinary file

- **WHEN** a merge of current main conflicts in a file that is neither declared generated nor an archive-derived current-spec path
- **THEN** the candidate becomes integration repair

### Requirement: A coordinator environment failure is not integration repair

A failure of the coordinator's own environment — the OpenSpec CLI is unavailable, a declared regeneration command cannot start, or the command fails on the pristine checkout of main as well — SHALL NOT become integration repair: the coordinator SHALL leave the candidate's state unchanged, publish no job, still evaluate the other candidates, and end the run as a failure naming each cause.

#### Scenario: The OpenSpec CLI is unavailable during regeneration

- **WHEN** the OpenSpec CLI is unavailable while preparing a candidate
- **THEN** the candidate's state is unchanged and no job is published
- **AND** the other candidates are still evaluated
- **AND** the run ends as a failure naming the cause

### Requirement: Regeneration runs no pull-request-controlled code under the App token

The coordinator SHALL NOT execute pull-request-controlled code while holding the App token.

#### Scenario: The coordinator regenerates a declared file

- **WHEN** the coordinator regenerates a declared generated file while holding the App token
- **THEN** it executes no pull-request-controlled code

### Requirement: Recovery accepts an unrecorded regenerated update

Recovery of an unrecorded coordinator update SHALL accept a merge that differs from both parents only in archive-derived specs and declared generated files.

#### Scenario: A coordinator update was pushed but not recorded

- **GIVEN** an unrecorded coordinator update that differs from both parents only in archive-derived specs and declared generated files
- **WHEN** the coordinator recovers it
- **THEN** the merge is accepted

### Requirement: A writer-needing repair round posts one attention comment

For a candidate in `repair-pending` or `integration-repair-pending`, the coordinator SHALL post one human-readable attention comment per exact repair round on the pull request, titled as a needed repair of that pull request, naming the reason, the head, the attempts and the worker command an operator runs to execute the published job. The published job SHALL stay claimable.

#### Scenario: A candidate enters repair-pending

- **WHEN** a candidate enters `repair-pending`
- **THEN** one human-readable attention comment titled as a needed repair of the pull request is posted for that round
- **AND** it names the reason, the head, the attempts and the worker command an operator runs
- **AND** the published job stays claimable

### Requirement: An integration-merge round posts no repair attention comment

An `integration-merge` round needs no writer and SHALL NOT post the repair attention comment.

#### Scenario: An integration-merge round is published

- **WHEN** an `integration-merge` round is published
- **THEN** no repair attention comment is posted

### Requirement: A lost repair attention comment is posted once on the next observation

A lost repair attention comment SHALL be posted on the next observation of the same round; an unchanged round SHALL NOT post another repair attention comment.

#### Scenario: The repair attention comment was lost

- **GIVEN** a repair round whose attention comment was lost
- **WHEN** the coordinator next observes the same round
- **THEN** the attention comment is posted

#### Scenario: The repair round is unchanged

- **GIVEN** a repair round whose attention comment exists
- **WHEN** the coordinator observes the unchanged round again
- **THEN** no other attention comment is posted

### Requirement: An integration-merge job names no provider and keeps its kind

The `integration-merge` job SHALL name no provider and no route, SHALL count against the same bounded integration-repair attempts, and SHALL record on the candidate that the round is merge-only so a re-published job and a recovered push keep the kind.

#### Scenario: An integration-merge job is re-published

- **GIVEN** an `integration-merge` job that names no provider and no route and counts against the integration-repair attempts
- **WHEN** the job is re-published or its push is recovered
- **THEN** it keeps the merge-only kind recorded on the candidate

### Requirement: The integration-merge executor merges main without a writer

The executor of an `integration-merge` job SHALL merge current main in a disposable harness checkout without starting any writer, validate the result like an integration repair, push it under the claim and advance the candidate like an integration repair.

#### Scenario: An integration-merge job is executed

- **WHEN** an `integration-merge` job is executed
- **THEN** current main is merged in a disposable harness checkout without starting any writer
- **AND** the result is validated, pushed under the claim and the candidate advanced like an integration repair

### Requirement: A failing integration-merge job leads to integration repair

When the merge conflicts or a required check is red at execution time of an `integration-merge` job, the `integration-merge` job SHALL fail naming the conflicts and the coordinator SHALL offer an integration-repair job in the next attempt, never a writer inside the integration-merge job.

#### Scenario: An integration-merge job meets a conflict

- **WHEN** an `integration-merge` job's merge conflicts at execution time
- **THEN** the job fails naming the conflicts
- **AND** the coordinator offers an integration-repair job in the next attempt, never a writer inside the integration-merge job

### Requirement: Conflicts and red checks keep offering integration repair

A conflict, a red required check or a failed GitHub branch update SHALL keep offering integration repair as before.

#### Scenario: A failed GitHub branch update blocks integration

- **WHEN** integration meets a conflict, a red required check or a failed GitHub branch update
- **THEN** the coordinator offers integration repair as before

### Requirement: An accepted developer fix supersedes the integration-repair job

A fresh developer handoff accepted for a candidate whose latest record is `integration-repair-pending` SHALL supersede the published integration-repair job.

#### Scenario: A developer fix is accepted during integration repair

- **WHEN** a fresh developer handoff is accepted for a candidate in `integration-repair-pending`
- **THEN** the published integration-repair job is superseded

### Requirement: An archived task is re-opened for a developer fix during integration repair

An archived managed task whose admitted PR waits in `integration-repair-pending` SHALL be re-opened for a fresh developer handoff when the local head strictly descends from the proven head.

#### Scenario: The task of a waiting PR is already archived

- **GIVEN** an archived managed task whose admitted PR waits in `integration-repair-pending`
- **WHEN** the local head strictly descends from the proven head
- **THEN** the task is re-opened for a fresh developer handoff

### Requirement: An ineligible developer fix during integration repair is refused

For a fresh developer handoff of a candidate whose latest record is `integration-repair-pending`, a live claim, a different task or a head that does not descend from the proven head SHALL be refused with a message naming the reason.

#### Scenario: The integration-repair job holds a live claim

- **GIVEN** a candidate in `integration-repair-pending` whose integration-repair job holds a live claim
- **WHEN** a fresh developer handoff arrives
- **THEN** it is refused with a message naming the live claim

### Requirement: The integration-repair writer brief carries failed check logs

The integration-repair writer brief SHALL carry, for each failed check, its identity and a bounded excerpt of its failed log.

#### Scenario: An integration-repair writer is briefed

- **GIVEN** integration repair is needed because required checks failed
- **WHEN** the integration-repair writer brief is built
- **THEN** it carries each failed check's identity and a bounded excerpt of its failed log

### Requirement: An integration-repair brief without failed check evidence is refused

An integration-repair writer brief for a failed required check without that check's identity or with an unreadable log SHALL be refused before any writer starts, naming the cause, and SHALL NOT spend an integration-repair attempt.

#### Scenario: The failed check's log is unreadable

- **WHEN** the integration-repair writer brief is built for a failed required check whose log is unreadable
- **THEN** the brief is refused before any writer starts, naming the cause
- **AND** no integration-repair attempt is spent

### Requirement: reoffer-post-merge refuses an ineligible obligation before any write

`publication_queue.py reoffer-post-merge` SHALL refuse before any write when the reason or the acting authenticated GitHub identity is missing, the PR is not merged, `H` differs from the merged head, there is no coordinator record at the merged head, no post-merge obligation of the PR is exhausted, or an unexpired claim holds a job of the exhausted obligation.

#### Scenario: The expected head differs from the merged head

- **WHEN** `publication_queue.py reoffer-post-merge` runs with `H` different from the merged head
- **THEN** it refuses before any write

#### Scenario: An unexpired claim holds the exhausted obligation's job

- **WHEN** an unexpired claim holds a job of the exhausted obligation
- **THEN** `publication_queue.py reoffer-post-merge` refuses before any write

### Requirement: reoffer-post-merge appends one record at the merged head

When `publication_queue.py reoffer-post-merge` does not refuse, the command SHALL append one coordinator record at the merged head that keeps state `merged`, task identity and attempt counters, increments `post-merge-reoffers`, and carries a re-offer event naming the obligation kind, reason, actor, `via` label when given, head and time.

#### Scenario: An exhausted post-merge obligation is re-offered

- **WHEN** `publication_queue.py reoffer-post-merge` accepts an exhausted post-merge obligation
- **THEN** one coordinator record is appended at the merged head keeping state `merged`, task identity and attempt counters
- **AND** `post-merge-reoffers` is incremented
- **AND** the re-offer event names the obligation kind, reason, actor, `via` label when given, head and time

### Requirement: Post-merge re-offer eligibility is one shared function

Post-merge re-offer eligibility SHALL be one function shared with the lifecycle overview and the attention comment.

#### Scenario: The overview and the attention comment show post-merge re-offer

- **WHEN** the lifecycle overview or the attention comment decides whether `reoffer-post-merge` is permitted
- **THEN** it uses the same eligibility function as `publication_queue.py reoffer-post-merge`

### Requirement: HTTP 422 too many files changed is transient in candidate observation

Inside the queue's candidate observation only, HTTP 422 "too many files changed" SHALL count as transient.

#### Scenario: Candidate observation returns too many files changed

- **WHEN** the queue's candidate observation receives HTTP 422 "too many files changed"
- **THEN** the failure counts as transient and is retried

#### Scenario: Another queue step returns too many files changed

- **WHEN** a request outside the queue's candidate observation receives HTTP 422 "too many files changed"
- **THEN** the failure does not count as transient

### Requirement: Exhausted candidate observation retries fail visibly

When the candidate observation retry bound is spent the observation SHALL fail naming the PR, the attempts and the last error, and a run in which no candidate could be evaluated SHALL exit non-zero.

#### Scenario: Candidate observation retries are exhausted

- **WHEN** the candidate observation retry bound is spent
- **THEN** the observation fails naming the PR, the attempts and the last error

#### Scenario: No candidate could be evaluated

- **WHEN** no candidate could be evaluated in a queue worker run
- **THEN** the run exits non-zero

### Requirement: A non-transient candidate observation failure is not retried

A non-transient candidate observation failure SHALL NOT be retried.

#### Scenario: Candidate observation fails non-transiently

- **WHEN** the candidate observation fails with a non-transient error
- **THEN** it is not retried

### Requirement: A transient integration failure is counted per head

A transient failure while integrating a candidate SHALL leave the candidate `waiting` and SHALL record a consecutive-failure counter for its exact head in the candidate record; when the counter reaches the limit the candidate SHALL be blocked with a reason naming the head, the count and the error.

#### Scenario: Integration fails transiently

- **WHEN** integrating a candidate fails transiently
- **THEN** the candidate stays `waiting`
- **AND** the candidate record holds a consecutive-failure counter for its exact head

#### Scenario: The consecutive-failure counter reaches the limit

- **WHEN** the consecutive-failure counter for the candidate's head reaches the limit
- **THEN** the candidate is blocked with a reason naming the head, the count and the error

### Requirement: The transient integration failure counter resets

A later evaluation of the same head without a transient failure SHALL reset the consecutive-failure counter, and a new head SHALL start with no count.

#### Scenario: The same head is evaluated without a transient failure

- **GIVEN** a candidate head with a consecutive-failure counter
- **WHEN** a later evaluation of that head has no transient failure
- **THEN** the counter is reset

#### Scenario: The candidate gets a new head

- **WHEN** the candidate gets a new head
- **THEN** the new head starts with no count

### Requirement: An accepted re-handoff supersedes the finalize-pending admission

A fresh developer handoff accepted for a candidate whose latest record is `finalize-pending` SHALL supersede the finalize-pending admission.

#### Scenario: A re-handoff is accepted while finalize is pending

- **WHEN** a fresh developer handoff is accepted for a candidate in `finalize-pending`
- **THEN** the finalize-pending admission is superseded

### Requirement: An archived task is re-opened for a finalize-pending re-handoff

An archived managed task whose admitted PR waits in `finalize-pending` SHALL be re-opened for a fresh developer handoff when the local head strictly descends from the proven head.

#### Scenario: The task of a finalize-pending PR is already archived

- **GIVEN** an archived managed task whose admitted PR waits in `finalize-pending`
- **WHEN** the local head strictly descends from the proven head
- **THEN** the task is re-opened for a fresh developer handoff

### Requirement: An ineligible finalize-pending re-handoff is refused

For a fresh developer handoff of a candidate whose latest record is `finalize-pending`, a live finalize claim, a different task or a head that does not descend from the proven head SHALL be refused with a message naming the reason.

#### Scenario: The finalize job holds a live claim

- **GIVEN** a candidate in `finalize-pending` whose finalize job holds a live claim
- **WHEN** a fresh developer handoff arrives
- **THEN** it is refused with a message naming the live finalize claim

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
