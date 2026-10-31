## MODIFIED Requirements

### Requirement: Publication recovery reconciles authoritative observed state

For `harness_mode=platform` and `publish_mode=pr`, the platform SHALL derive publication status from current local Git and GitHub state on every supported finish/status invocation. Observation SHALL include the task branch and exact local head SHA, configured base branch, remote branch presence, an exact matching PR when one exists, required-check state, remote merge/auto-merge state, and whether local post-merge reconciliation remains.

#### Scenario: Caller restarts after PR creation

- **GIVEN** the validated task head still equals commit A
- **AND** GitHub has one open PR for that branch/base whose `headRefOid` is A
- **WHEN** normal task finish runs again
- **THEN** it reuses that exact PR
- **AND** it does not create a second PR or require prior phase history

#### Scenario: Task head changed after earlier publication work

- **GIVEN** an earlier PR observation referred to commit A
- **WHEN** the local task branch now resolves to commit B
- **THEN** commit A does not authorize publication of B
- **AND** the new head must pass normal local validation before any merge request for B

#### Scenario: GitHub state is temporarily unavailable

- **WHEN** authoritative PR/check/merge state cannot be read
- **THEN** publication fails closed without mutating local main
- **AND** a later invocation can re-observe and continue from current Git/GitHub state

### Requirement: Native GitHub merge orchestration is armed before long local waiting when supported

For `pr_merge_mode=auto`, after an exact-head PR is created or reused, the platform SHALL prefer to ask GitHub to persist the protected merge intent before entering a long foreground wait, using native auto-merge or merge-queue behavior when repository capability/policy supports it.

#### Scenario: Native auto-merge accepts the exact task head

- **GIVEN** the repository supports native auto-merge
- **AND** the task PR head is validated commit A
- **WHEN** the platform arms automatic merge for that PR before required checks are complete
- **THEN** GitHub retains the merge request while checks continue
- **AND** caller termination does not cancel that accepted remote merge request
- **AND** GitHub merges only if the PR head still matches A and protection requirements are satisfied

#### Scenario: Repository requires a merge queue

- **GIVEN** repository policy requires merge-queue integration
- **WHEN** the platform requests supported automatic integration for exact head A
- **THEN** it uses GitHub's queue-aware merge behavior without administrative bypass
- **AND** the queued/auto state remains observable after the local caller exits

#### Scenario: Native auto-merge is unavailable

- **GIVEN** the repository does not support or has not enabled native auto-merge for this PR
- **WHEN** the platform cannot persist remote merge intent before checks complete
- **THEN** it retains the existing bounded foreground check/merge fallback
- **AND** reports that remote durability is degraded rather than fabricating a local durable executor
- **AND** the exact branch/PR remains resumable by a later finish invocation

#### Scenario: PR head changes before merge request

- **GIVEN** validation covered commit A
- **WHEN** GitHub reports a different PR head before a merge/auto-merge request is accepted
- **THEN** the exact-head guard rejects the request
- **AND** the changed head is not merged under validation for A

### Requirement: Existing exact-head PRs resume before first-publication stale-base rejection

For an exact-head PR admitted to the source repository's publication queue, ordinary main advancement by a preceding queued change SHALL be handled by the queue coordinator rather than requiring the waiting agent to reconcile and revalidate solely for that advancement. A PR outside that queue retains explicit reconciliation behavior.

#### Scenario: Base advances while exact PR is waiting

- **GIVEN** an open exact-head task PR exists outside the central publication queue
- **AND** the base branch advances after the PR was created
- **WHEN** finish is invoked again
- **THEN** it stops before expensive validation and points to the supported reconcile operation
- **AND** reconciliation preserves the same PR branch without force-push or rebase
- **AND** validation must rerun for the resulting descendant head before publication resumes

#### Scenario: New stale branch has never been published

- **GIVEN** no exact-head PR exists for local task commit A
- **AND** A does not satisfy the platform's first-publication fresh-base prerequisite
- **WHEN** finish attempts first publication
- **THEN** publication remains blocked until the branch is explicitly reconciled and revalidated

#### Scenario: Queued PR waits while main advances

- **GIVEN** an exact-head task PR is admitted to the publication queue
- **AND** another nonoverlapping queued PR merges first
- **WHEN** waiting task finish/status runs
- **THEN** it observes the durable queue state without starting expensive validation or demanding agent-side reconcile merely for that base advancement
- **AND** the coordinator proves and checks the updated candidate before its protected merge.

#### Scenario: Queued candidate changes outside coordinator control

- **WHEN** the queued PR head changes from the admitted or proven coordinator-produced head
- **THEN** old queue admission does not authorize publication
- **AND** fresh local validation and a new exact-head admission are required.

### Requirement: Publication status is read-only and actionable

The platform SHALL provide a supported read-only task publication status operation. Status SHALL not push branches, create/close PRs, arm merges, update boards, remove worktrees, or mutate local main.

#### Scenario: Base advances before another validation run

- **GIVEN** an active task branch no longer contains the latest authoritative main
- **WHEN** read-only status runs
- **THEN** it reports reconciliation required and the supported command
- **AND** it does not update the local `origin/main` ref

#### Scenario: Caller loses output after remote merge was armed

- **GIVEN** GitHub accepted automatic integration for the exact task PR
- **WHEN** a later read-only status runs
- **THEN** it reports the current PR/check/merge state from GitHub
- **AND** it does not depend on the prior process having written a phase journal

#### Scenario: PR merged but local checkout was not reconciled

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration/board/worktree reconciliation has not completed
- **WHEN** status runs
- **THEN** it reports remote delivery as complete and local reconciliation as pending
- **AND** normal finish can perform only the remaining safe local reconciliation

### Requirement: Exact-head publication identity remains unambiguous across reused branch names

For `harness_mode=platform` and `publish_mode=pr`, branch name SHALL be only a discovery hint. The publication lifecycle SHALL identify the current publication object by repository, configured base branch, head branch, and exact expected head SHA. Discovery SHALL remain correct when historical pull requests reuse the same head branch name.

#### Scenario: Historical merged PR and current exact PR share a branch name

- **GIVEN** an older PR for branch `X` is `MERGED` at head A
- **AND** branch `X` is later reused at head B
- **AND** GitHub has an exact PR for B targeting the configured base branch
- **WHEN** publication state for B is discovered
- **THEN** the lifecycle selects the PR whose `headRefOid` is B
- **AND** the historical PR at A cannot authorize checks, merge recovery, cleanup, or terminal status for B

#### Scenario: Historical merged PR exists but the current head has no PR yet

- **GIVEN** an older PR for branch `X` is `MERGED` at head A
- **AND** the current validated branch head is B
- **AND** no exact PR for B exists
- **WHEN** publication of B starts
- **THEN** the historical PR at A is treated only as historical state
- **AND** the lifecycle creates or discovers an exact PR for B or fails closed
- **AND** it does not delete the remote branch, reconcile local main, finish board/worktree state, or report terminal success for B

#### Scenario: Merge command succeeds but exact merge proof is not available

- **GIVEN** the lifecycle requested merge for stable PR P at expected head B
- **WHEN** the merge command exits zero
- **BUT** GitHub does not confirm both `state == MERGED` and `headRefOid == B` for P
- **THEN** cleanup and terminal reconciliation remain blocked and resumable

#### Scenario: Merge command exits non-zero after possible server-side success

- **GIVEN** the lifecycle requested merge for stable PR P at expected head B
- **WHEN** the merge command exits non-zero
- **THEN** recovery may continue only if GitHub confirms both `state == MERGED` and `headRefOid == B` for P
- **AND** a merged PR for another head cannot be used as recovery evidence

#### Scenario: Exact PR head changes after validation

- **GIVEN** stable PR P was selected for expected head B
- **WHEN** GitHub reports a different `headRefOid` before terminal merge confirmation
- **THEN** the lifecycle fails closed
- **AND** the changed head requires normal revalidation before publication can continue

#### Scenario: Restart observes the exact head already merged

- **GIVEN** stable PR P for expected head B was already merged
- **WHEN** publication recovery runs again
- **THEN** the lifecycle may resume from that exact merged evidence
- **AND** performs only the remaining safe reconciliation/cleanup idempotently

## ADDED Requirements

### Requirement: A matching publication PR is identified by exact head identity

For `harness_mode=platform` and `publish_mode=pr`, a matching PR SHALL be identified by repository/base branch plus task head branch and exact `headRefOid`; title/body text or a remembered PR number alone SHALL NOT authorize publication.

#### Scenario: Remembered PR number does not match the exact head

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **AND** a remembered PR number or matching title/body text exists but the PR's `headRefOid` differs from the task head
- **WHEN** publication observes PR state
- **THEN** that PR is not treated as the matching PR
- **AND** it does not authorize publication

### Requirement: Machine-local cached state is not the authoritative publication cursor

For `harness_mode=platform` and `publish_mode=pr`, machine-local cached state MAY assist diagnostics later but SHALL NOT be required as the authoritative publication cursor.

#### Scenario: Machine-local cache is absent

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **AND** no machine-local cached publication state exists
- **WHEN** a supported finish/status invocation runs
- **THEN** publication status is still derived from current local Git and GitHub state

### Requirement: Merge requests are guarded by the exact validated PR head

Every ordinary merge, auto-merge, or queue-enrollment request SHALL be guarded by the exact validated PR head SHA using `--match-head-commit` or equivalent expected-head semantics.

#### Scenario: Platform requests a merge

- **WHEN** the platform sends an ordinary merge, auto-merge, or queue-enrollment request
- **THEN** the request is guarded by the exact validated PR head SHA using `--match-head-commit` or equivalent expected-head semantics

### Requirement: Accepted remote merge orchestration survives caller output loss

Acceptance of remote merge orchestration SHALL survive loss of the caller output stream.

#### Scenario: Caller output stream is lost after acceptance

- **GIVEN** GitHub has accepted remote merge orchestration
- **WHEN** the caller output stream is lost
- **THEN** the accepted remote merge orchestration remains in effect

### Requirement: Finish distinguishes current task branches from stale ones before validation

A supported finish invocation SHALL distinguish a current task branch from one that is behind or diverged from freshly observed authoritative main before starting expensive validation. A first publication still obeys the platform's fresh-base safety preconditions.

#### Scenario: Task branch is behind authoritative main

- **GIVEN** a task branch is behind freshly observed authoritative main
- **WHEN** a supported finish invocation runs
- **THEN** it identifies the branch as behind before starting expensive validation

### Requirement: Changed content or unproven queue state fails closed to explicit recovery

Changed task content, overlapping relevant base changes, unknown queue identity or a failed coordinator check SHALL fail closed to explicit recovery.

#### Scenario: Queue identity is unknown

- **WHEN** the queue identity of a waiting exact-head PR is unknown
- **THEN** publication fails closed to explicit recovery

#### Scenario: Coordinator check fails

- **WHEN** a coordinator check fails
- **THEN** publication fails closed to explicit recovery

### Requirement: Publication status distinguishes publication states

Task publication status SHALL report concise sanitized facts sufficient to distinguish at least: not published, PR open/checks pending, remote merge armed/queued, blocked/failed required checks, remotely merged but local reconciliation pending, and complete.

#### Scenario: Required checks failed on the open PR

- **GIVEN** a task PR is open and a required check has failed
- **WHEN** task publication status is read
- **THEN** it reports concise sanitized facts that identify blocked/failed required checks rather than another state

### Requirement: Publication status exposes head, PR and merge capability

Task publication status SHALL include the exact task SHA and PR URL/number when available and SHALL expose whether native remote auto-merge capability is available or the task is using foreground fallback.

#### Scenario: Task uses foreground fallback

- **GIVEN** a task PR exists and native remote auto-merge capability is unavailable
- **WHEN** task publication status is read
- **THEN** it includes the exact task SHA and the PR URL/number
- **AND** it exposes that the task is using foreground fallback

### Requirement: Publication status exposes task freshness against authoritative main

Task publication status SHALL also expose task-vs-authoritative-main freshness and the explicit reconciliation command when the task is behind or diverged, without updating local remote-tracking refs.

#### Scenario: Task has diverged from authoritative main

- **GIVEN** the task has diverged from authoritative main
- **WHEN** task publication status is read
- **THEN** it exposes task-vs-authoritative-main freshness and the explicit reconciliation command
- **AND** it does not update local remote-tracking refs

### Requirement: Selected exact PR operations use a stable PR identity and the expected head

For `harness_mode=platform` and `publish_mode=pr`, once an exact pull request is selected or created, required-check reads, merge requests, merge-state reads, recovery, and terminal reconciliation SHALL use a stable PR number or URL together with the same expected head SHA that identified the current publication object.

#### Scenario: Lifecycle reads checks for a selected exact PR

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **AND** an exact pull request has been selected
- **WHEN** the lifecycle reads required checks, requests a merge or reads merge state
- **THEN** it uses the stable PR number or URL together with the same expected head SHA

### Requirement: Branch-name lookups and exit codes do not authorize cleanup or success

For `harness_mode=platform` and `publish_mode=pr`, a branch-name-only lookup, command exit code, or stale merged PR SHALL NOT authorize destructive cleanup or terminal success.

#### Scenario: Stale merged PR shares the head branch name

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **AND** a stale merged PR is found by a branch-name-only lookup
- **WHEN** the lifecycle decides on cleanup or terminal success
- **THEN** that lookup does not authorize destructive cleanup or terminal success
