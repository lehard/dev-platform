# publication-recovery Specification

## Purpose
Platform-owned automatic PR publication is restartable from authoritative Git and GitHub state, so interrupted agent sessions converge on one exact task delivery without a second publication database.
## Requirements
### Requirement: Publication recovery reconciles authoritative observed state

For `harness_mode=platform` and `publish_mode=pr`, the platform SHALL derive publication status from current local Git and GitHub state on every supported finish/status invocation. Observation SHALL include the task branch and exact local head SHA, configured base branch, remote branch presence, an exact matching PR when one exists, required-check state, remote merge/auto-merge state, and whether local post-merge reconciliation remains.

A matching PR SHALL be identified by repository/base branch plus task head branch and exact `headRefOid`; title/body text or a remembered PR number alone SHALL NOT authorize publication. Machine-local cached state MAY assist diagnostics later but SHALL NOT be required as the authoritative publication cursor.

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

Every ordinary merge, auto-merge, or queue-enrollment request SHALL be guarded by the exact validated PR head SHA using `--match-head-commit` or equivalent expected-head semantics. Acceptance of remote merge orchestration SHALL survive loss of the caller output stream.

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

A supported finish invocation SHALL distinguish first publication of a stale local branch from recovery of an already-existing exact-head PR. A first publication still obeys the platform's fresh-base safety preconditions. An existing exact-head PR MAY continue through GitHub required checks, branch protection, auto-merge, or merge queue even when the base branch advanced after that PR was opened.

The platform SHALL NOT silently rewrite/rebase/update the task branch merely to make recovery succeed. If repository policy requires the PR branch to be updated and no supported queue/automatic integration can satisfy that policy, the lifecycle SHALL report that concrete blocker.

#### Scenario: Base advances while exact PR is waiting

- **GIVEN** an open exact-head task PR already exists for commit A
- **AND** the base branch advances after the PR was created
- **WHEN** finish is invoked again
- **THEN** the platform revalidates current local safety and re-observes GitHub
- **AND** it does not reject the existing PR solely because A no longer contains the newest base tip
- **AND** GitHub protection/queue remains authoritative for whether A can integrate

#### Scenario: New stale branch has never been published

- **GIVEN** no exact-head PR exists for local task commit A
- **AND** A does not satisfy the platform's first-publication fresh-base prerequisite
- **WHEN** finish attempts first publication
- **THEN** publication remains blocked until the branch is explicitly reconciled and revalidated

### Requirement: Publication status is read-only and actionable

The platform SHALL provide a supported read-only task publication status operation. Status SHALL not push branches, create/close PRs, arm merges, update boards, remove worktrees, or mutate local main.

Status SHALL report concise sanitized facts sufficient to distinguish at least: not published, PR open/checks pending, remote merge armed/queued, blocked/failed required checks, remotely merged but local reconciliation pending, and complete. It SHALL include the exact task SHA and PR URL/number when available and SHALL expose whether native remote auto-merge capability is available or the task is using foreground fallback.

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

### Requirement: Concurrent publication attempts converge without a long-lived publisher lease

Automatic publication operations SHALL be idempotent under repeated or concurrent finish attempts for the same exact task head. The platform SHALL prefer exact-head observation, create-race re-query, GitHub uniqueness and expected-head merge guards over a long-lived lease that spans remote waits.

#### Scenario: Two publishers race to create the same task PR

- **GIVEN** two finish processes target the same branch/base/head SHA
- **WHEN** both observe no PR before one process creates it
- **THEN** at most one exact task PR becomes the publication target
- **AND** the losing process re-observes and reuses that PR rather than treating the create race as a reason to create competing delivery work

#### Scenario: Two publishers request automatic merge

- **GIVEN** both processes refer to the same exact task PR head A
- **WHEN** both attempt a supported merge/auto-merge transition
- **THEN** repeated requests remain convergent or one process observes the state established by the other
- **AND** no request is allowed to merge a head other than A

#### Scenario: Remote merge completes before local reconciliation races

- **WHEN** GitHub has merged the exact task PR
- **THEN** the already-existing integration lock continues to serialize local main/board/worktree mutation
- **AND** remote waiting never holds that integration lock

### Requirement: Repository merge capability is observable but not silently mutated

For a platform-owned automatic PR, doctor/status SHOULD detect whether native GitHub auto-merge or queue behavior can persist the remote waiting step. The platform SHALL NOT silently enable repository auto-merge from the task publication path.

#### Scenario: Native repository auto-merge is disabled

- **WHEN** `pr_merge_mode=auto` is configured but repository auto-merge/queue capability is unavailable
- **THEN** doctor/status reports safe foreground fallback / degraded remote durability
- **AND** provides an explicit administrative remediation when the current operator can enable the capability
- **AND** ordinary publication safety remains unchanged

#### Scenario: Native repository auto-merge is enabled explicitly

- **WHEN** an administrator enables native auto-merge for the repository
- **THEN** that repository setting alone does not merge any PR
- **AND** only a specific exact-head PR explicitly armed by the publication lifecycle becomes eligible for GitHub automatic merge after protections pass

