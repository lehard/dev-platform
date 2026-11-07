# Platform Lifecycle Specification

## Purpose

The platform lifecycle SHALL define safe, agent-driven task execution from synchronization through publication while preserving OpenSpec contract coherence and avoiding routine human Git hand-offs.

## Requirements

### Requirement: GitHub-aware task lifecycle

The platform SHALL fetch and compare the configured remote integration branch before starting work and again immediately before publication. It SHALL abort rather than auto-resolve divergent histories and SHALL never force-push.

#### Scenario: Remote main advances before start

- **WHEN** local main is clean and behind origin/main
- **THEN** the platform fast-forwards local main before creating task work

#### Scenario: Remote main diverges before publication

- **WHEN** local and remote integration history are not in a safe ancestor relationship
- **THEN** publication aborts and requires explicit reconciliation

### Requirement: Configurable publication modes

The platform SHALL support `pr` and `direct` publication modes. PR mode SHALL publish a feature branch and create or reuse a GitHub PR; its completion behavior SHALL be controlled by `pr_merge_mode=auto|manual`. Direct mode SHALL publish only a safe fast-forward of an integration branch that is explicitly not protected.

#### Scenario: Project uses PR publication

- **WHEN** `publish_mode=pr` and validated feature work is completed
- **THEN** the platform pushes the feature branch and creates or reuses a PR
- **AND** follows the configured PR merge policy

#### Scenario: Project uses direct publication

- **GIVEN** `protected_main=false`
- **WHEN** `publish_mode=direct` and the integration branch safely descends from current origin/main
- **THEN** the platform may push the fast-forward update and SHALL abort on divergence

### Requirement: Composable workflow profiles

The platform SHALL provide `light`, `standard`, and `multi-agent` profiles from one template. Worktrees and the agent board SHALL only be mandatory for `multi-agent`.

#### Scenario: Single-agent project uses light profile

- **WHEN** a project selects `light`
- **THEN** it can use OpenSpec, checks and GitHub lifecycle without mandatory worktrees or agent-board coordination

#### Scenario: Concurrent agents use multi-agent profile

- **WHEN** a project selects `multi-agent`
- **THEN** isolated worktrees and machine-local scope coordination are part of the workflow

### Requirement: OpenSpec contract coherence

For non-trivial OpenSpec work, agents SHALL update planning artifacts before knowingly implementing changed intent, observable behavior, technical design, or execution order. Semantic OpenSpec verification and project-specific checks SHALL be completed before archive.

#### Scenario: Implementation discovers a different solution is required

- **WHEN** the intended behavior or implementation direction changes during an active OpenSpec change
- **THEN** the corresponding proposal, delta spec, design or tasks artifact is updated before implementation knowingly diverges

#### Scenario: Non-trivial OpenSpec change is completed

- **WHEN** implementation tasks are finished
- **THEN** project checks and semantic OpenSpec verification occur before the change is archived

### Requirement: Deliberate learning promotion

Platform friction SHALL keep raw evidence machine-local by default, while high-signal sanitized friction candidates SHALL be routed automatically to the appropriate GitHub process-issue backlog during supported lifecycle processing instead of depending on remembered routine manual promotion.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem through a high-signal supported friction event
- **THEN** only sanitized structured evidence is sent to the central platform inbox through the routing contract
- **AND** raw evidence remains machine-local by default

#### Scenario: Platform-level friction is captured

- **WHEN** an agent or supported deterministic lifecycle hook records a high-signal event with `scope=platform`
- **THEN** the platform stores the raw structured event locally
- **AND** automatically attempts to create or update a sanitized fingerprinted issue in the configured platform repository
- **AND** does not require the human operator to remember a separate `promote` command

#### Scenario: Project-level friction is captured

- **WHEN** a high-signal event has `scope=project`
- **THEN** the platform automatically attempts to create or update the sanitized fingerprinted issue in the normalized current project repository
- **AND** does not route that project-specific issue to the central platform inbox solely because the platform provides the tooling

#### Scenario: Similar friction repeats

- **GIVEN** an open process issue already contains the stable sanitized fingerprint for the event class
- **WHEN** the same friction class recurs
- **THEN** routing updates that issue with a bounded sanitized occurrence rather than creating a duplicate issue
- **AND** execution model/runtime MAY be recorded as occurrence provenance without splitting the same process problem into model-specific duplicate issues

#### Scenario: Raw evidence contains sensitive context

- **WHEN** a recorded friction event contains arbitrary raw evidence, credential-like text or machine-local details
- **THEN** those raw fields remain machine-local by default
- **AND** the GitHub representation contains only bounded sanitized structured fields allowed by the routing contract

#### Scenario: GitHub routing is unavailable

- **WHEN** authentication, network or GitHub API availability prevents issue routing
- **THEN** the local event remains pending for a later supported lifecycle retry
- **AND** no raw credential-bearing evidence is printed or uploaded
- **AND** an otherwise safe task is not reclassified as failed solely because process telemetry could not be routed

#### Scenario: Process evidence looks ready for remediation

- **WHEN** a process issue or cloud review recommends a reusable fix
- **THEN** the recommendation remains advisory process evidence
- **AND** no Business Requirement is created until explicit human fixation, and no technical OpenSpec change is created until execution or explicit direct technical intent

### Requirement: Workflow profile and harness ownership are composable

The platform SHALL treat workflow profile and lifecycle implementation ownership as independent configuration dimensions. `multi-agent` SHALL describe required capabilities, while `harness_mode=project` SHALL allow a downstream repository to satisfy those capabilities through its own reviewed implementation.

#### Scenario: Mature project provides its own multi-agent lifecycle

- **GIVEN** `workflow_profile=multi-agent` and `harness_mode=project`
- **WHEN** an agent starts or finishes work
- **THEN** platform-owned start/finish wrappers SHALL direct the agent to the repository-owned lifecycle described by project rules instead of requiring platform worktree/board implementations
- **AND** platform doctor SHALL validate only the project-required lifecycle files declared by the reviewed project contract plus common platform files

#### Scenario: Platform provides multi-agent lifecycle

- **GIVEN** `workflow_profile=multi-agent` and `harness_mode=platform`
- **WHEN** platform doctor validates the repository
- **THEN** the platform-managed worktree, board and Git-hook files remain mandatory

### Requirement: Protected integration branches use remote PR integration

A platform-owned lifecycle SHALL NOT publish directly to an integration branch declared as protected. Protected-main publication SHALL use a feature branch and GitHub pull request so required status checks remain authoritative.

#### Scenario: Protected main is configured with direct publication

- **GIVEN** `protected_main=true`
- **AND** `harness_mode=platform`
- **WHEN** doctor or finish preflight evaluates `publish_mode=direct`
- **THEN** the lifecycle fails before local integration or remote push
- **AND** it explains that protected main requires PR publication

#### Scenario: Protected task is ready to publish

- **GIVEN** `protected_main=true`, `publish_mode=pr`, and `pr_merge_mode=auto`
- **WHEN** validated feature work is finished
- **THEN** the platform pushes the feature branch, creates or reuses its PR, waits for required checks, merges through GitHub, and synchronizes local main afterward
- **AND** it never force-pushes or bypasses branch protection

### Requirement: Automatic task PR merge preserves zero-hand-off delivery

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy. The merge is one action: `gh pr merge --auto --squash --match-head-commit <head>`. Required-check state SHALL be determined from structured GitHub state for the current PR head, not from human-readable CLI message matching.

#### Scenario: No required check gates the merge

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** structured GitHub state shows no required check for the current PR head
- **THEN** the platform refuses the merge and names the missing required check
- **AND** the PR stays open and local main remains unchanged

#### Scenario: GitHub refuses auto-merge

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** GitHub rejects the merge request
- **THEN** publication stops with GitHub's reason
- **AND** no other merge form is tried and no local wait for checks starts

#### Scenario: Structured required check fails

- **GIVEN** required checks are registered for the current PR head
- **WHEN** structured GitHub state reports a required check in a failing terminal state
- **THEN** the platform does not merge the PR
- **AND** local main remains unchanged
- **AND** the failing required check is reported without relying on arbitrary log text

#### Scenario: Auto-merge remains pending past the bounded wait

- **GIVEN** GitHub accepted auto-merge
- **WHEN** the bounded merge confirmation wait expires before the exact task PR reaches `MERGED`
- **THEN** the platform does not begin local-main reconciliation
- **AND** leaves the PR available for GitHub to continue processing
- **AND** a later rerun checks whether the exact task head has since merged and resumes safely

#### Scenario: Automatic task PR succeeds

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** required PR checks succeed and GitHub completes the armed auto-merge
- **THEN** the platform confirms the PR is `MERGED`
- **AND** updates the local integration copy to the merged remote state
- **AND** completes normal board/worktree cleanup

#### Scenario: Automatic task PR check fails

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** a required PR check fails
- **THEN** the platform does not merge the PR
- **AND** local main remains unchanged
- **AND** the agent receives the failing-check result

#### Scenario: Manual task PR is requested

- **GIVEN** `pr_merge_mode=manual`
- **WHEN** the task is published
- **THEN** the platform creates or reuses the PR and stops without merging it

### Requirement: Remote merge precedes local integration for protected-main work

For PR publication, local integration branch mutation SHALL occur only after the remote PR has been successfully merged. A confirmed GitHub merge SHALL remain authoritative even if later local or remote-branch cleanup reports a non-zero convenience error. In platform-owned multi-agent PR mode, the shared integration checkout mutation phase SHALL be serialized through the configured integration lock.

#### Scenario: Two task PRs merge near the same time

- **GIVEN** two independent multi-agent task PRs have both been confirmed `MERGED` by GitHub
- **WHEN** both finish processes attempt local reconciliation against the same integration checkout
- **THEN** only one process mutates the integration checkout at a time
- **AND** each process re-fetches remote main after acquiring the integration lock
- **AND** both tasks may complete without Git/index lock races or manual synchronization solely because of concurrent reconciliation

#### Scenario: First reconciliation advances local main before second acquires the lock

- **GIVEN** task A reconciles and advances local main while task B waits for the integration lock
- **WHEN** task B acquires the lock
- **THEN** task B re-fetches and recomputes local-main versus remote-main state
- **AND** safely fast-forwards or accepts an already-equal state
- **AND** does not assume the pre-lock local-main observation is still current

#### Scenario: Remote wait is still in progress

- **WHEN** a task is waiting for required checks or auto-merge completion
- **THEN** it SHALL NOT hold the shared integration lock during that remote wait

#### Scenario: Remote PR merge is rejected

- **WHEN** GitHub rejects every supported non-bypass merge form because protection requirements are not satisfied
- **THEN** the feature branch and PR remain available
- **AND** local main remains at its pre-publication commit

#### Scenario: Merge is confirmed but cleanup fails

- **WHEN** GitHub reports the task PR as `MERGED`
- **AND** remote branch deletion or local worktree/branch cleanup fails
- **THEN** the lifecycle treats the task as remotely merged
- **AND** continues safe local-main reconciliation where possible
- **AND** reports cleanup as a warning rather than redefining the merge as failed

### Requirement: Publication prerequisites fail early

Platform-owned PR publication SHALL validate GitHub CLI/API availability before work reaches the remote merge stage, and credential resolution SHALL fall back from invalid process token variables to other validated persistent GitHub credentials without requiring routine re-login.

#### Scenario: Stale environment token shadows persistent credentials

- **GIVEN** `GH_TOKEN` or `GITHUB_TOKEN` is present but invalid
- **AND** a valid persistent `gh` login or reusable Git HTTPS credential exists
- **WHEN** platform PR publication resolves GitHub API authentication
- **THEN** it ignores the invalid token source after validation fails
- **AND** continues with the valid persistent credential
- **AND** does not require the user to run `gh auth login` again

#### Scenario: GitHub CLI is unavailable or unauthenticated

- **GIVEN** `harness_mode=platform` and `publish_mode=pr`
- **WHEN** all supported GitHub CLI/API credential sources fail validation
- **THEN** doctor/finish fails with an actionable authentication/setup message
- **AND** no local-main integration is attempted

### Requirement: Git branch publication is independent from PR API operations

The platform SHALL treat pushing a validated feature branch and performing GitHub PR API operations as separate publication steps.

#### Scenario: Direct invocation lacks PR API authentication

- **WHEN** a validated feature branch can be pushed using git credentials but GitHub PR API authentication is unavailable
- **THEN** the platform may leave the branch safely published
- **AND** it reports that PR creation/merge is incomplete
- **AND** it does not mutate local main

### Requirement: Protected-main publication is resumable after remote merge

The platform-owned finish lifecycle SHALL recognize a task PR that was already merged by GitHub and SHALL resume only the remaining local reconciliation steps instead of requiring the feature branch to be republished or rebased. The resumed local reconciliation SHALL use the same integration serialization as a first-pass successful PR finish.

#### Scenario: Already-merged retry races another task reconciliation

- **GIVEN** a task PR is already merged for the exact local task head
- **AND** another task is currently reconciling the shared integration checkout
- **WHEN** the first task is retried
- **THEN** it waits for the integration lock rather than mutating the checkout concurrently
- **AND** re-fetches remote main after acquiring the lock
- **AND** completes idempotent local/board/worktree reconciliation without creating a second PR or requiring a rebase

#### Scenario: Process stops after GitHub merge before local synchronization

- **GIVEN** a task feature branch still exists locally
- **AND** its GitHub PR is already `MERGED`
- **AND** `origin/main` no longer has the feature branch as an ancestor because the PR was squash-merged
- **WHEN** the agent reruns `finish_task`
- **THEN** the platform recognizes the already-merged PR before applying stale-branch rejection
- **AND** synchronizes local main to the merged remote state
- **AND** reconciles board/worktree cleanup according to normal options
- **AND** returns success without creating a second PR or requesting a rebase

### Requirement: Task intake preserves managed and quick execution paths

The platform lifecycle SHALL distinguish planned managed work from small direct quick work before implementation begins. A Development Backlog issue explicitly supplied as the task source SHALL use managed-task intake and OpenSpec preflight. A small task directly requested by the user MAY enter the existing execution lifecycle without first creating a central backlog issue or ceremonial OpenSpec.

#### Scenario: User explicitly supplies a managed backlog task

- **WHEN** the user asks the agent to take a supported Development Backlog issue
- **THEN** the agent uses managed-task intake to discover and verify the referenced OpenSpec planning contract before implementation
- **AND** the platform materializes that contract only after the configured task branch or worktree is established
- **AND** does not ask the user to restate the already captured product decision

#### Scenario: User gives a small direct fix

- **WHEN** the requested work is a small scoped change that does not require a product/architecture contract
- **THEN** the agent may use the existing task start/check/finish workflow directly
- **AND** does not create a central Development Backlog issue solely to record short-lived work

#### Scenario: Quick task becomes non-trivial

- **WHEN** implementation reveals that a quick task requires a material behavior, architecture, compatibility, data-contract or scope change
- **THEN** the agent stops before knowingly broadening the contract
- **AND** proposes escalation to a managed task/OpenSpec instead of silently continuing as a quick fix

### Requirement: Repository OpenSpec becomes canonical after managed import

A Development Backlog package SHALL be treated as a planning handoff, not as a permanent parallel implementation plan. Once a managed package has been successfully materialized, repository-local OpenSpec SHALL be the canonical contract used by implementation, verification and archive lifecycle.

#### Scenario: Imported change is being implemented

- **GIVEN** a managed package has been materialized successfully
- **WHEN** implementation discovers that intent, observable behavior, technical design or execution dependencies must change
- **THEN** the repository-local OpenSpec artifacts are updated according to the existing no-silent-divergence rules
- **AND** implementation does not repeatedly overwrite them from the original backlog package

#### Scenario: Human views the backlog during implementation

- **WHEN** the managed task is in progress
- **THEN** the central issue remains the human workflow/provenance item
- **AND** it is not treated as a second task list competing with `openspec/changes/<change>/tasks.md`

### Requirement: Managed task start preserves integration-copy isolation

For a platform-owned feature-capable workflow, managed task start SHALL
perform package discovery and target validation without materializing files,
synchronize the integration branch, create the configured task branch or
worktree, and materialize the OpenSpec package only in that task checkout.
The integration copy SHALL remain clean after a successful managed task start.

#### Scenario: Multi-agent managed task starts successfully

- **GIVEN** a clean integration copy and a valid managed backlog package
- **WHEN** the platform starts the managed task
- **THEN** it creates and registers an isolated task worktree before materializing the OpenSpec package
- **AND** all imported OpenSpec artifacts exist in that task worktree
- **AND** the integration copy remains clean on its integration branch

#### Scenario: Standard managed task starts successfully

- **GIVEN** a clean integration copy and a valid managed backlog package
- **WHEN** the platform starts the managed task in the `standard` profile
- **THEN** it creates the task feature branch before materializing the OpenSpec package
- **AND** the imported artifacts belong to that feature branch rather than the integration branch

#### Scenario: Managed package is invalid before task creation

- **GIVEN** the supplied issue does not contain a valid package for the current repository
- **WHEN** managed task start performs read-only package discovery
- **THEN** it refuses before creating a branch, worktree, board entry or OpenSpec files

#### Scenario: Materialization fails after task creation

- **GIVEN** a task branch or worktree has been created for a valid managed package
- **WHEN** materialization or strict OpenSpec validation fails
- **THEN** the platform reports the failure without modifying the integration copy
- **AND** it reconciles the newly created local task state without deleting unrelated work

### Requirement: Direct managed import protects feature-capable integration branches

The standalone managed importer SHALL refuse to materialize a package from the
integration branch of a platform-owned `standard` or `multi-agent` workflow.
The error SHALL direct the caller to the managed task start entrypoint. Direct
materialization remains supported where the `light` profile intentionally
performs work on its integration branch.

#### Scenario: Importer is invoked from multi-agent integration main

- **GIVEN** a platform-owned `multi-agent` workflow is on its integration branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it fails before creating OpenSpec artifacts
- **AND** it explains how to start the managed task in an isolated worktree

#### Scenario: Importer is invoked from a standard task branch

- **GIVEN** a platform-owned `standard` workflow is on a task feature branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it may materialize the package in that feature branch

#### Scenario: Importer is invoked in the light profile

- **GIVEN** a platform-owned `light` workflow is on its integration branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it may materialize the package according to the light workflow

### Requirement: Automatic PR publication reconciles from exact observed state

Platform-owned automatic PR publication SHALL be restartable by re-observing the exact task branch/head and GitHub PR/check/merge state instead of depending on an uninterrupted foreground process or replaying prior phase events.

#### Scenario: Existing exact-head PR is resumed

- **GIVEN** `harness_mode=platform`, `publish_mode=pr`, and `pr_merge_mode=auto`
- **AND** an open PR already exists for the configured base and exact local task head SHA
- **WHEN** the agent runs normal finish again
- **THEN** the platform reuses and reconciles that PR
- **AND** does not create duplicate delivery work solely because the previous publisher stopped

#### Scenario: Existing PR head differs from validated local head

- **GIVEN** the local task head was validated as A
- **WHEN** the candidate GitHub PR resolves to head B
- **THEN** the platform refuses to treat that PR as publication of A
- **AND** it does not merge B under the validation decision for A

### Requirement: Automatic merge intent is exact-head guarded and durable when GitHub supports it

For an exact-head automatic task PR, the platform SHALL persist merge intent in native GitHub auto-merge state before any local wait. Every protected merge request SHALL include an exact expected task-head guard.

#### Scenario: Auto-merge is armed before required checks finish

- **GIVEN** native GitHub auto-merge is available
- **AND** required checks for exact head A are still pending
- **WHEN** the platform publishes the task PR
- **THEN** it requests auto-merge for A before waiting for all checks locally
- **AND** GitHub may complete the merge after the publisher process exits, provided protections pass and the head remains A

#### Scenario: Exact head changes before GitHub accepts merge

- **GIVEN** validation covered A
- **WHEN** a protected merge operation observes a different PR head
- **THEN** the merge request fails closed through expected-head semantics
- **AND** the changed head must be validated separately

### Requirement: Existing published PR recovery is distinct from first-publication freshness

The platform SHALL preserve the existing fresh-base prerequisite for first publication while allowing an already-existing exact-head task PR to continue through GitHub protection after the base advances. It SHALL NOT silently rewrite the candidate branch during recovery.

#### Scenario: Base advances after exact PR was opened

- **GIVEN** an exact-head task PR already exists
- **AND** the configured base advances before merge
- **WHEN** normal finish runs again
- **THEN** it re-observes the existing PR before applying first-publication stale-base rejection
- **AND** GitHub required checks and branch protection determine whether integration may proceed

#### Scenario: Repository requires candidate branch update

- **GIVEN** an existing exact-head PR cannot integrate because repository policy requires an updated branch
- **AND** no supported automatic integration path can satisfy that policy
- **WHEN** recovery runs
- **THEN** it reports the branch-update requirement as an actionable blocker
- **AND** it does not silently mutate/rebase the task head

### Requirement: Task publication status is read-only

Platform-owned publication SHALL expose a supported status operation derived from current Git/GitHub state. The status operation SHALL not perform publication or local integration mutations.

#### Scenario: Status observes an unfinished remote task

- **WHEN** an exact task PR is open, waiting, armed, queued, failed, or merged
- **THEN** status reports the exact task SHA, PR identity, current remote delivery state and safe next operation
- **AND** it does not push, create/merge PRs, update boards, clean worktrees, or change local main

#### Scenario: Remote merge is complete but local reconciliation is not

- **WHEN** GitHub reports the exact task PR as `MERGED` but the local integration copy has not yet been reconciled
- **THEN** status distinguishes `remote merged` from `local reconciliation pending`
- **AND** normal finish may complete only the already-supported serialized local reconciliation

### Requirement: Remote publication races converge idempotently

Repeated or concurrent platform-owned publication attempts for the same exact task head SHALL converge on the same remote PR and merge intent without requiring a lease that spans remote waits.

#### Scenario: Concurrent PR create race

- **GIVEN** two publishers target the same exact branch/base/head SHA
- **WHEN** one publisher creates the PR after both initially observed none
- **THEN** the other publisher re-queries and reuses that PR
- **AND** the create race does not produce competing task PRs

#### Scenario: Concurrent merge request race

- **GIVEN** two publishers target the same exact PR head A
- **WHEN** both request protected automatic integration
- **THEN** exact-head guards and current GitHub state make the operations convergent
- **AND** neither process may merge a different head

### Requirement: Native automatic-merge capability is visible and explicitly administered

For `harness_mode=platform` and `pr_merge_mode=auto`, platform diagnostics SHOULD report whether repository-native auto-merge is available; publication requires it. Task publication SHALL NOT silently enable or disable repository-level auto-merge settings.

#### Scenario: Repository auto-merge is disabled

- **WHEN** automatic task publication is configured but native auto-merge is unavailable
- **THEN** doctor/status reports that publication will be refused
- **AND** may provide the explicit administrative action required to enable native auto-merge
- **AND** no repository setting is changed implicitly

### Requirement: Validation feedback is observable and failure-diagnostic

The platform SHALL emit machine-readable duration and outcome evidence for each validation command. Successful routine output SHALL be concise, while a failed command SHALL preserve actionable diagnostics including the command identity, exit outcome, and bounded relevant output or a durable artifact reference.

#### Scenario: Successful local validation

- **WHEN** a local validation command succeeds
- **THEN** the lifecycle records its selected check identity, duration and successful outcome
- **AND** routine output remains concise enough for an agent to identify progress and elapsed time

#### Scenario: Validation command fails

- **WHEN** a validation command fails
- **THEN** the lifecycle reports the command identity and non-success outcome
- **AND** exposes a bounded useful diagnostic tail or artifact location without suppressing the failure

### Requirement: Local affected validation never replaces protected PR authority

The platform SHALL distinguish a conservative `local affected` feedback policy from a `protected full` merge-authority policy. A protected-main PR SHALL still require the complete authoritative platform validation set even when a local affected subset has succeeded.

#### Scenario: Proven local affected change

- **WHEN** every changed path is covered by maintained and tested mappings to bounded canonical test/check groups
- **THEN** local feedback executes those mapped groups without unrelated full-suite work
- **AND** a group selected by multiple changed paths is executed only once within the validation invocation
- **AND** the resulting success is not accepted as the protected PR required validation result

#### Scenario: Local path is unknown or high impact

- **WHEN** a changed path is unknown, ambiguously classified, or affects selector/check configuration, CI workflow, OpenSpec/lifecycle control-plane code or another explicitly high-impact surface
- **THEN** local affected validation selects the full authoritative set, without the commands the repository left to its required PR check
- **AND** reports that the fallback was safety-driven

#### Scenario: Protected-main PR is evaluated

- **WHEN** a protected-main PR contains any platform change
- **THEN** CI executes every mandatory validation group in the complete authoritative validation set for the current head
- **AND** merge authority does not depend on a prior local affected run

### Requirement: Validation selection fails closed

The validation selector SHALL choose the full authoritative set whenever a changed path is unknown, ambiguously classified, or affects selector/configuration, workflow, OpenSpec, lifecycle, or other explicitly high-impact control-plane code. Commands a repository left to its required PR check SHALL be dropped from that local selection.

#### Scenario: Changed path has no proven selector mapping

- **WHEN** local affected validation receives a path without an explicit safe mapping
- **THEN** it selects the full validation set
- **AND** reports that the fallback was safety-driven

#### Scenario: Control-plane path changes

- **WHEN** a change touches validation selection/configuration, CI workflow, OpenSpec, or lifecycle control-plane code
- **THEN** local affected validation selects the full validation set

### Requirement: A required PR check can own slow full-set commands

A repository MAY list entries of `full_commands` in `ci_only_commands`. A local selection SHALL then drop them, record them as left to required CI and run the affected tests of changed Python paths; protected-full mode SHALL keep every command. The selector SHALL refuse the setting unless a required PR check gates every merge, and SHALL refuse an entry that is not in `full_commands`.

#### Scenario: A script changes in a repository with the setting

- **GIVEN** `ci_only_commands` lists the full test suite
- **WHEN** a local run selects validation for a changed script
- **THEN** it runs the remaining full commands and the affected tests
- **AND** the evidence names the suite as left to required CI
- **AND** the required PR check still runs the suite on the exact head

#### Scenario: A merge has no required PR check

- **GIVEN** `ci_only_commands` is set
- **AND** the repository lacks any of `harness_mode=platform`, `scm_provider=github`, `protected_main=true`, `publish_mode=pr`, `pr_merge_mode=auto`
- **WHEN** a local run selects validation
- **THEN** the selector stops and names the settings that refuse it

#### Scenario: The setting is absent

- **WHEN** a repository does not set `ci_only_commands`
- **THEN** local selection keeps the full authoritative set

### Requirement: Parallel validation preserves resource isolation and aggregate authority

The platform SHALL run validation groups concurrently only when each group's mutable resources are isolated per run/worker or the group is explicitly serialized. Independent validation invocations in separate task worktrees SHALL NOT interfere through fixed temporary paths, shared artifacts, locks, ports, process-global state or other mutable test resources. When CI uses partitions, it SHALL publish a stable aggregate required result that fails if any mandatory partition fails.

#### Scenario: Two task worktrees validate concurrently

- **GIVEN** two independent task worktrees execute supported validation at the same time
- **WHEN** their isolation-safe groups use mutable test resources
- **THEN** those resources are namespaced or otherwise isolated per run/worker
- **AND** neither run corrupts, blocks or changes the outcome of the other because of shared fixture state

#### Scenario: Candidate partition shares mutable state

- **WHEN** the resource audit identifies a shared mutable database, artifact path, lock, port, external state, or process-global setting
- **THEN** the candidate is serialized or given proven per-worker isolation before concurrent execution is enabled

#### Scenario: Candidate group has a legitimate shared boundary

- **WHEN** the resource audit identifies mutable state that cannot safely be isolated in this change
- **THEN** that group is explicitly serialized or otherwise bounded
- **AND** unrelated isolation-safe groups are not forced into repository-wide serialization solely because of that boundary

#### Scenario: Partitioned required validation fails

- **WHEN** any mandatory validation partition fails
- **THEN** the stable aggregate required result reports failure
- **AND** protected-main merge remains blocked

### Requirement: Task start leaves a pending rollout PR untouched

Task start SHALL NOT merge, close, relabel or arm auto-merge on a Dev Platform rollout PR, and SHALL NOT synchronize local integration for one or stop because one is open. A rollout PR SHALL be merged only by an explicit rollout, never as a side effect of starting a task.

#### Scenario: A green rollout PR is open when a task starts

- **GIVEN** an authoritative rollout PR with satisfied required checks is open
- **WHEN** a quick or managed task starts
- **THEN** the rollout PR stays open and unchanged
- **AND** the task starts on the current platform state

#### Scenario: A rollout PR with failed or pending checks is open when a task starts

- **GIVEN** an open rollout PR whose required checks are failed, pending or ambiguous
- **WHEN** a quick or managed task starts
- **THEN** start completes without treating the rollout as a blocker

### Requirement: The doctor reports a pending rollout read-only

`agent_doctor.py` SHALL report an open authoritative rollout PR with its observed check state as a read-only warning for every harness mode, and SHALL state that only an explicit rollout merges it.

#### Scenario: Project owns task harness

- **GIVEN** a managed repository uses `harness_mode=project`
- **WHEN** the agent runs `agent_doctor.py` before starting new work
- **THEN** it reports the pending rollout read-only
- **AND** Dev Platform does not replace the project-owned task/worktree implementation

### Requirement: Managed Project status follows actual execution lifecycle

For a task with an unambiguous managed Development Backlog source, the
platform-owned lifecycle SHALL keep the configured GitHub Project `Status`
consistent with actual execution/delivery state. The Project field SHALL be a
human-facing projection of lifecycle evidence rather than an independent task
state machine.

#### Scenario: Managed task is successfully claimed

- **GIVEN** the source managed task is authorized as `Ready`
- **WHEN** the standard managed start path successfully validates the source and establishes its task workspace
- **THEN** the Project item is reconciled to `In progress` before implementation continues
- **AND** a Project mutation/configuration failure is surfaced rather than silently leaving active work in `Ready`

#### Scenario: Import is performed without task claim

- **WHEN** a supported managed OpenSpec package is only discovered/imported outside a successful managed execution claim
- **THEN** that package operation alone does not change Project workflow status

### Requirement: Managed delivery projects review and terminal states truthfully

The platform SHALL project reviewable delivery as `In review`, genuine external
stops as `Blocked`, and terminal reconciled completion as `Done`. Transient CI
waiting SHALL NOT be misclassified as a blocker.

#### Scenario: Exact task PR is published

- **GIVEN** a managed task is active
- **WHEN** its exact reviewable delivery PR is created or safely reused
- **THEN** the Project item is reconciled to `In review`
- **AND** it remains non-terminal while checks/review/merge are pending

#### Scenario: Lifecycle requires external action

- **WHEN** the managed lifecycle reaches a supported blocker that cannot continue without a human/external action or decision
- **THEN** the Project item is reconciled to `Blocked`
- **AND** the blocker is surfaced with actionable context

#### Scenario: Blocked task resumes

- **WHEN** the external blocker is resolved and lifecycle resumes
- **THEN** reconciliation restores `In progress` or `In review` according to the current execution/delivery evidence

#### Scenario: Required checks are merely pending

- **WHEN** an active managed PR is waiting for normal required checks or accepted automatic merge processing
- **THEN** its status remains `In review`
- **AND** the lifecycle does not use `Blocked` solely because remote processing is incomplete

#### Scenario: Managed delivery completes

- **GIVEN** GitHub confirms the exact managed delivery is merged
- **WHEN** required local/source-task reconciliation reaches terminal success
- **THEN** the configured Project item is reconciled to `Done`
- **AND** open/green-but-unmerged delivery cannot produce `Done`

### Requirement: Managed Project status reconciliation is idempotent and recoverable

Status synchronization SHALL be safe to retry and SHALL use unambiguous source
Issue/Project identity plus authoritative lifecycle evidence. It SHALL support
repairing stale status after interruption without creating duplicate Project
items or redefining Git/PR truth.

#### Scenario: Desired status is already current

- **WHEN** reconciliation observes that the Project item already has the desired lifecycle status
- **THEN** it performs no workflow-changing mutation
- **AND** returns success

#### Scenario: Remote merge succeeded but Project update failed

- **GIVEN** GitHub already confirms the exact task PR as merged
- **WHEN** Project mutation is unavailable or fails
- **THEN** the merge remains authoritative
- **AND** lifecycle reports Project reconciliation as pending/blocking full workflow completion
- **AND** a later retry can set the correct Project state without creating another delivery

#### Scenario: Historical item is stale

- **GIVEN** an existing managed item still shows `Ready` or another stale value
- **AND** its source and lifecycle/delivery evidence unambiguously imply another supported state
- **WHEN** explicit recovery reconciliation is run
- **THEN** the Project item is repaired to that supported state
- **AND** ambiguity causes no mutation and is reported for human resolution

### Requirement: Human readiness authorization remains human-owned

Automatic status synchronization SHALL NOT select work from the backlog or grant
execution authorization.

#### Scenario: Managed task is still in Backlog

- **WHEN** no human has moved/authorized the task as `Ready`
- **THEN** lifecycle status synchronization does not move it to `Ready` or start execution
- **AND** no dispatcher is implied by this capability

### Requirement: Lifecycle preflights shared workspace access before mutation

The platform lifecycle SHALL validate and, where authorized, idempotently repair
the group collaboration contract for the platform-owned paths needed by the
next operation. The check SHALL include the integration root, registered task
worktree administration, required Git common-directory metadata and
platform-owned machine-local state. An unrepairable permission blocker SHALL be
surfaced before the next remote mutation whenever authoritative remote state has
not already changed.

#### Scenario: Restrictive drift is safely repairable

- **GIVEN** a platform-owned shared file is missing group write or a shared
  directory is missing group write/setgid
- **AND** the current user is authorized to change that bounded path
- **WHEN** lifecycle preflight runs
- **THEN** it restores the reviewed shared-group contract idempotently
- **AND** proceeds without requiring an alternate Git object store

#### Scenario: Restrictive drift is owned by another user

- **GIVEN** a required path cannot be repaired by the current process
- **WHEN** a managed lifecycle operation reaches preflight
- **THEN** it stops before the next remote mutation
- **AND** reports the exact path and minimal owner action required
- **AND** it does not stash, reset, clean, sudo or widen access beyond the
  reviewed group

#### Scenario: Remote merge is already authoritative

- **GIVEN** the exact managed PR is already GitHub-confirmed merged
- **AND** local reconciliation is blocked by restrictive shared permissions
- **WHEN** finish is retried after the owner repairs those paths
- **THEN** it resumes local-main, source-state, board and cleanup reconciliation
  without republishing or changing the merged result

### Requirement: File-producing lifecycle operations preserve group access

Platform-owned entry points SHALL set a cooperative creation mask where POSIX
semantics apply and SHALL explicitly set the final shared mode for secure
temporary files before atomic publication. They SHALL validate the affected
shared paths after file-producing operations that may ignore the creation mask.

#### Scenario: Secure temporary API defaults to owner-only mode

- **WHEN** a platform writer creates an atomic temporary file with a secure
  owner-only default
- **THEN** it applies the reviewed group-readable/group-writable mode before
  replacing the shared destination
- **AND** the destination never regresses to owner-only mode

#### Scenario: Git recreates mutable metadata

- **WHEN** fetch, commit, worktree or reconciliation creates new Git metadata
- **THEN** shared-repository configuration and post-operation validation keep the
  required metadata writable by the reviewed group
- **AND** any remaining drift is reported with exact paths

### Requirement: Managed resume and publication require canonical OpenSpec provenance

For work originating from a Development Backlog managed Issue, platform-owned resume/finish SHALL verify the matching repository-local active or archived OpenSpec provenance before treating the task as a valid managed execution. Publication SHALL also require the existing task-completion, semantic-verification and archive evidence appropriate to the task's lifecycle stage.

#### Scenario: Managed implementation is still active

- **WHEN** a managed task resumes with a matching active canonical OpenSpec change
- **THEN** execution may continue using that change as the implementation contract
- **AND** normal no-silent-divergence rules continue to apply

#### Scenario: Managed PR has code but no matching canonical change

- **WHEN** an existing managed branch or PR has implementation changes but matching active/archived OpenSpec provenance cannot be resolved
- **THEN** the lifecycle blocks further managed publication
- **AND** reports the missing/mismatched source evidence instead of inferring completion from the code or PR alone

#### Scenario: Managed PR directly changes current specs without lifecycle evidence

- **WHEN** a managed delivery directly edits accepted `openspec/specs/*`
- **AND** there is no matching canonical change/archive evidence explaining those edits
- **THEN** publication fails closed as unexplained contract drift

#### Scenario: Matching change is archived and delivery remains

- **GIVEN** the managed change has matching provenance, completed tasks, semantic verification and archive evidence
- **WHEN** finish resumes after implementation completion
- **THEN** only remaining publication/reconciliation work proceeds
- **AND** no new OpenSpec materialization is required

### Requirement: Managed completeness uses existing OpenSpec evidence rather than fuzzy diff scoring

The platform SHALL use deterministic task checklist state, required semantic verification and archive/lifecycle evidence as the managed completion gate. It SHALL NOT use an LLM or fuzzy comparison between the original Issue body and code diff as the authoritative completeness boundary.

#### Scenario: Only part of the canonical task checklist is complete

- **WHEN** a managed task still has incomplete required OpenSpec tasks
- **THEN** terminal managed completion/publication SHALL NOT be reported solely because a PR exists or checks are green

### Requirement: Protected remote merge revalidates integration checkout safety at the last local mutation boundary

For platform-owned PR publication, immediately before the auto-merge request for the exact validated task head, the lifecycle SHALL re-observe the integration checkout under the appropriate integration serialization boundary. Divergent uncommitted integration state SHALL block remote merge intent before GitHub is mutated.

#### Scenario: Integration remains clean after PR checks

- **GIVEN** the exact task PR is ready for a supported protected merge
- **WHEN** the pre-merge integration observation finds no uncommitted state
- **THEN** the existing exact-head merge orchestration may proceed

#### Scenario: Integration becomes dirty while PR waits for checks

- **GIVEN** task start and initial publication preflight observed a clean integration checkout
- **AND** another local actor changes integration while the PR waits remotely
- **WHEN** required checks become ready and finish reaches the merge boundary
- **THEN** the lifecycle observes the new dirty state before the auto-merge request
- **AND** blocks remote merge intent when that state is divergent

#### Scenario: Divergent integration state is found before merge

- **WHEN** the pre-merge observation finds tracked or untracked local integration content that is not safely reconciled state
- **THEN** publication reports the concrete affected paths and stops before remote merge mutation
- **AND** SHALL NOT automatically stash, reset, clean, delete or overwrite that local state

#### Scenario: Dirty paths merely resemble task paths

- **WHEN** local dirty paths overlap the task diff by name but content equivalence has not been proven
- **THEN** the lifecycle SHALL NOT treat that overlap alone as safe
- **AND** remote merge remains blocked

### Requirement: Pre-merge safety check composes with integration serialization

The last-safe-point observation SHALL not hold the integration lock during long remote check waits, but SHALL acquire/reuse the appropriate serialization before the merge decision and re-observe state after acquiring it.

#### Scenario: Another reconciliation completes before merge decision

- **WHEN** the current task acquires the integration serialization after another task changed local main
- **THEN** it re-fetches/re-observes current local and remote state
- **AND** bases the merge decision on that current state rather than a pre-wait snapshot

### Requirement: Managed terminal side effects use exact task provenance

For a Development Backlog managed task, platform-owned terminal reconciliation SHALL perform Project-status and related managed side effects only for the source identity bound to the exact delivered task. Shared integration state SHALL NOT be the sole or higher-precedence source of managed task identity after execution has moved out of the task checkout.

#### Scenario: Exact task PR merges while integration state belongs to another task

- **GIVEN** GitHub confirms the exact-head PR for task A as `MERGED`
- **AND** integration-visible managed state identifies task B
- **WHEN** terminal reconciliation begins
- **THEN** the GitHub merge for task A remains authoritative
- **AND** the lifecycle does not update task B
- **AND** managed Project mutation is blocked until task A's identity can be safely reconciled

#### Scenario: Correct task identity reaches terminal completion

- **GIVEN** task A's exact managed identity is preserved through publication
- **WHEN** remote merge and local reconciliation complete
- **THEN** only source Issue A is reconciled to the appropriate terminal Project state
- **AND** repeating terminal reconciliation is idempotent

#### Scenario: Status reconciliation fails after confirmed merge

- **WHEN** the exact task PR is already `MERGED`
- **AND** managed Project reconciliation cannot safely complete
- **THEN** the task remains remotely merged
- **AND** the lifecycle records or reports a resumable pending-reconciliation state tied to that exact task
- **AND** a later retry continues without creating a second delivery path

### Requirement: Expensive validation requires a fresh task base

For platform-owned task execution, the lifecycle SHALL refresh its observation of the configured remote integration branch and verify that the current task head is based on the authoritative remote history before running expensive full/protected validation intended as delivery evidence.

#### Scenario: Task remains fresh before full validation

- **GIVEN** the current task head contains the freshly fetched `origin/<main>` in its ancestry
- **WHEN** full/protected validation is about to begin
- **THEN** the lifecycle continues with the existing selected validation commands
- **AND** no additional human action is required solely for freshness

#### Scenario: Remote main advances during task execution

- **GIVEN** the task began from an earlier integration state
- **AND** `origin/<main>` has advanced so the current task head no longer contains that authoritative history
- **WHEN** expensive full/protected validation is requested
- **THEN** the lifecycle stops before executing that expensive validation set
- **AND** reports a resumable rebase/reconciliation-first outcome with the observed relationship
- **AND** does not automatically reset, force-rebase, or force-push the task branch

#### Scenario: Freshness cannot be established

- **WHEN** the remote integration state required for authoritative freshness cannot be observed
- **THEN** the lifecycle does not claim the task is fresh for delivery-evidence validation
- **AND** returns an explicit safe blocker/retry outcome rather than silently proceeding

#### Scenario: Task is reconciled and retried

- **GIVEN** a stale task has been safely reconciled onto the current authoritative integration history
- **WHEN** the freshness check is repeated
- **THEN** it succeeds if ancestry is now valid
- **AND** the ordinary validation lifecycle resumes without a second special workflow

### Requirement: Task start establishes an explicit freshness observation

Platform-owned task start SHALL establish the authoritative remote integration observation used to create or resume task work, in addition to existing project synchronization.

#### Scenario: Task starts after normal synchronization

- **WHEN** the platform has completed its ordinary start sync/preflight
- **THEN** the task starts only from a deterministically observed current remote integration state
- **AND** later freshness checks can compare the task head against a newly refreshed observation without relying on a stale local remote-tracking ref

### Requirement: Platform Git failures expose actionable sanitized diagnostics

When a platform-owned Git command is configured to fail on non-zero exit, the lifecycle SHALL surface an actionable bounded error that includes the attempted Git operation, execution directory and exit status together with useful sanitized diagnostic output. It SHALL NOT rely on a raw Python `CalledProcessError` traceback as the primary operator-facing result.

#### Scenario: Git command fails with useful stderr

- **WHEN** a checked Git command exits non-zero and stderr explains a permission, merge, ref or repository blocker
- **THEN** the platform error identifies the command, cwd and exit code
- **AND** includes bounded sanitized stderr sufficient to diagnose the blocker
- **AND** does not require the operator to inspect a Python traceback to discover the captured Git message

#### Scenario: Diagnostic output contains credential-like material

- **WHEN** captured Git output contains credential-like or secret-bearing text
- **THEN** the platform applies existing secret-safety/redaction rules before presenting or persisting the diagnostic
- **AND** does not emit unbounded raw process output

#### Scenario: Caller intentionally uses non-raising Git execution

- **GIVEN** a lifecycle component invokes Git with non-raising semantics to classify return codes itself
- **WHEN** the Git command exits non-zero
- **THEN** the caller still receives the inspectable non-terminal command result
- **AND** the common diagnostic layer does not convert that expected observation into a fatal generic error

#### Scenario: Higher-level resumable state owns the failure

- **WHEN** a structured lifecycle component catches or classifies a Git failure into an existing resumable blocker state
- **THEN** the actionable Git detail may be attached to that state
- **AND** the common wrapper does not erase the higher-level recovery semantics

### Requirement: Platform-owned multi-agent execution passes admission before implementation

For `workflow_profile=multi-agent` with platform-owned lifecycle semantics, a task SHALL receive a successful coordination admission before its first implementation change. Task discovery, isolated worktree creation, managed OpenSpec materialization, and semantic preflight MAY occur before admission when needed to resolve exact scope, but `WAIT` SHALL prevent implementation changes.

#### Scenario: Managed task reaches hard overlap after materialization

- **GIVEN** a managed task has a valid package and an isolated task worktree with canonical OpenSpec materialized
- **AND** semantic scope resolution establishes a hard overlap with an active task
- **WHEN** admission runs before implementation
- **THEN** the result is `WAIT`
- **AND** no implementation change is performed
- **AND** the existing worktree and canonical OpenSpec are preserved for resume

#### Scenario: Multi-agent task has only soft overlap

- **WHEN** preflight finds only soft or potential overlap
- **THEN** the lifecycle surfaces the warning
- **AND** the task is not blocked solely by that warning

### Requirement: Managed overlap waiting projects truthful workflow state

When a managed task receives `WAIT` because of a hard active-scope conflict, the platform SHALL reconcile the configured GitHub Project status to `Blocked` and surface the conflicting task/scope as the blocker reason. A successful later admission SHALL restore the managed task to `In progress` before implementation continues.

#### Scenario: Hard overlap blocks a managed task

- **WHEN** managed task B receives `WAIT` because active task A owns a conflicting concrete path
- **THEN** task B's Project item is reconciled to `Blocked`
- **AND** the blocker context identifies task A and a bounded conflicting scope
- **AND** normal CI or remote processing is not reclassified as this kind of blocker

#### Scenario: Hard-overlap blocker clears

- **GIVEN** the conflicting task no longer owns the concrete path
- **WHEN** the blocked managed task is explicitly resumed and admission succeeds
- **THEN** its Project item is reconciled to `In progress`
- **AND** implementation may continue

### Requirement: Admission resume reuses canonical managed task state

A managed task that previously reached `WAIT` SHALL be resumed from its existing task worktree and canonical repository-local OpenSpec. The next explicit start/resume invocation SHALL re-check admission and SHALL NOT create a duplicate worktree or re-import the original transport package over the canonical change.

No background daemon or automatic autoresume is required.

#### Scenario: Waiting task is retried while conflict remains

- **GIVEN** a managed task is preserved in a task worktree after `WAIT`
- **WHEN** the operator explicitly retries start/resume before the hard conflict clears
- **THEN** the lifecycle reuses that worktree
- **AND** re-checks admission
- **AND** remains `Blocked` without duplicate materialization if the conflict still exists

#### Scenario: Waiting task resumes after conflict clears

- **GIVEN** a managed task is preserved in its existing worktree
- **AND** the conflicting active claim has been released or is no longer valid
- **WHEN** start/resume is invoked again
- **THEN** the lifecycle reuses the existing canonical OpenSpec and worktree
- **AND** admission is evaluated again
- **AND** a successful `RUN` allows normal implementation to continue

### Requirement: Validation optimization preserves mandatory coverage and proves performance improvement

When the platform changes test execution structure for performance, it SHALL retain comparable before/after evidence for the same mandatory protected coverage. The optimized full path SHALL demonstrate lower wall-clock execution in a repeatable comparable environment before the change is accepted; performance SHALL NOT be improved by silently omitting mandatory tests or replacing current-head validation with a cached/prior result.

#### Scenario: Faster full validation is proposed

- **WHEN** an optimized protected-full execution model is evaluated
- **THEN** before/after evidence identifies the same mandatory test/check coverage and comparable environment
- **AND** the optimized execution demonstrates lower wall-clock duration
- **AND** any remaining serial boundaries and contention effects are recorded

#### Scenario: Proposed speedup reduces coverage

- **WHEN** a proposed optimization obtains lower wall-clock time by omitting a mandatory test/check or by reusing validation from a different head
- **THEN** the optimization is rejected as satisfying neither protected-full authority nor this performance requirement

### Requirement: Validation depth is proportional to a declared risk class

The platform SHALL classify a changed path into one of a small canonical set of risk classes rather than selecting validation depth solely by file-type or directory glob. A documentation/instruction surface with no intended agent-behavior change SHALL receive bounded structure/link/anchor/render checks and SHALL NOT by itself trigger the full mandatory software suite.

#### Scenario: Semantic-preserving documentation or instruction change

- **WHEN** every changed path is a documentation/instruction surface (for example `AGENTS.md`, `docs/**`, OpenSpec prose, `template/AGENTS.md.jinja`) and none carries an instruction-behavior-change declaration
- **THEN** local and protected validation execute the bounded documentation/instruction check group instead of the full Python suite
- **AND** that check group still fails on a broken required anchor, a broken link/destination, or a template render defect

#### Scenario: Ambiguous or unrecognized instruction surface

- **WHEN** a changed instruction/documentation-adjacent path does not match a maintained documentation/instruction surface mapping
- **THEN** validation selects the full authoritative set for that path
- **AND** reports that the fallback was safety-driven

### Requirement: Intended agent-behavior change requires executed targeted evidence

A change to an instruction/prompt surface that is declared to intentionally change agent behavior SHALL require the configured targeted behavioral smoke command(s) for the affected runtime/provider to actually execute and succeed as part of that validation invocation. A model's own narrative report that the change is safe SHALL NOT be accepted as behavioral evidence.

#### Scenario: Declared behavior change with executed evidence

- **WHEN** an instruction/prompt surface change is declared as an intended agent-behavior change for a specific runtime/provider
- **AND** the configured targeted behavioral smoke command for that runtime/provider is executed as part of the same validation invocation
- **THEN** the recorded command outcome is required to be successful before the change is accepted as validated for that risk class

#### Scenario: Declared behavior change without executed evidence

- **WHEN** an instruction/prompt surface change is declared as an intended agent-behavior change
- **AND** no configured targeted behavioral command for the affected runtime/provider was executed, or the model's own summary is offered in place of an executed command outcome
- **THEN** the selection falls back to the full authoritative validation set
- **AND** reports that the fallback was evidence-driven

### Requirement: Meaningful friction capture is a completion invariant

For a non-trivial platform-owned task, terminal completion SHALL include a bounded post-task process retrospective so meaningful user corrections, repeated failures, safety near-misses, workarounds, false task premises, avoidable CI/lifecycle failures, excessive retries or other high-signal unresolved process problems cannot be omitted merely because the agent forgot to record them.

#### Scenario: Several unresolved semantic frictions occurred

- **WHEN** a non-trivial platform-owned task reaches completion with two or more distinct high-signal semantic conditions that remain unresolved and unrecorded
- **THEN** the retrospective records or links all corresponding new friction events before completion is reported
- **AND** the completion result is not forced to choose only one event

#### Scenario: No meaningful friction occurred

- **WHEN** the bounded retrospective completes with zero new meaningful unresolved/unrecorded findings
- **THEN** the current completion checkpoint may resolve to `friction: none`
- **AND** no friction issue is created merely for the clean result

#### Scenario: Retrospective is omitted

- **WHEN** a non-trivial platform-owned task reaches the completion boundary without a current retrospective result
- **THEN** the lifecycle refuses terminal completion with an actionable instruction to perform the bounded review
- **AND** it does not invent a friction event on the agent's behalf

#### Scenario: Evidence source is degraded

- **GIVEN** the friction log has unreadable or malformed content
- **WHEN** the agent records `none` without accepting the named gap
- **THEN** the checkpoint is refused and names the degraded source
- **AND** an explicit acceptance of that gap is stored in the receipt

#### Scenario: Stale retrospective is reused

- **GIVEN** a valid retrospective/checkpoint existed for an earlier task execution state
- **WHEN** relevant task state changes before terminal completion
- **THEN** the old result does not satisfy the completion invariant
- **AND** a current retrospective is required

#### Scenario: Deterministic lifecycle failure occurs

- **WHEN** a supported lifecycle component detects an allow-listed machine-classifiable process failure or safety near-miss
- **THEN** it records the structured local friction event directly with bounded available context
- **AND** does not depend on a later natural-language reminder to preserve the observation

#### Scenario: Routing fails after checkpoint resolution

- **WHEN** a valid positive friction checkpoint has recorded its local event but GitHub routing is temporarily unavailable
- **THEN** completion may continue if all deterministic delivery requirements are otherwise satisfied
- **AND** the event remains pending for later routing retry

#### Scenario: Successful override and known issue recur

- **GIVEN** an agent uses a non-default override to complete a task and the same process defect already has an open issue
- **WHEN** it performs the retrospective
- **THEN** it records the meaningful recurrence as a new occurrence through the existing friction router
- **AND** no user prompt is required to surface it.

### Requirement: Friction evidence carries truthful bounded execution provenance

For a non-trivial platform-owned task, the platform SHALL maintain bounded execution provenance sufficient to relate completion/friction evidence to the execution run and, when knowable, the relevant supervisor or delegated executor.

#### Scenario: Friction is observed during a delegated execution

- **GIVEN** a supervisor actually delegates work to a recorded child executor
- **AND** a meaningful friction finding is attributable to that child
- **WHEN** the finding is recorded
- **THEN** it references the current execution/run and the child participant using available truthful runtime/routing evidence
- **AND** the parent model is not presented as the sole executor of that finding

#### Scenario: Route was prepared but child did not run

- **GIVEN** a lower-cost route was selected or prepared
- **BUT** delegation did not actually execute and the parent/fallback performed the work
- **WHEN** completion provenance is recorded
- **THEN** no executed child participant is fabricated
- **AND** the actual fallback/parent route is represented truthfully

#### Scenario: Effective reasoning effort cannot be confirmed

- **GIVEN** the platform selected or configured a reasoning-effort value
- **BUT** the current runtime does not reliably expose the effective value applied to the actual execution
- **WHEN** provenance is persisted
- **THEN** the selected/configured effort MAY be retained with that source/status
- **AND** runtime-confirmed/effective effort remains unknown

#### Scenario: Participant attribution is ambiguous

- **WHEN** a meaningful friction finding cannot be reliably attributed to a specific supervisor or child participant
- **THEN** the finding remains attached to the task execution/run with participant attribution unknown
- **AND** the platform does not guess which model caused it

### Requirement: Stale managed tasks have a supported non-rewriting reconcile path

The platform SHALL provide an explicit managed-task reconciliation operation for a task branch that no longer contains current authoritative main. The operation SHALL reuse existing managed provenance, freshness and publication state, SHALL preserve protected-main and exact-head safeguards, and SHALL NOT require force-push or automatic history rewrite.

#### Scenario: Unpublished task falls behind main

- **GIVEN** a managed task branch has not yet been published
- **AND** authoritative `origin/main` has advanced
- **WHEN** the operator invokes the supported reconcile operation
- **THEN** the platform safely incorporates current main using a non-destructive history-preserving update
- **AND** the task can proceed through the normal freshness and validation gates

#### Scenario: Exact managed PR is already open

- **GIVEN** the task has an open exact managed PR
- **AND** target main advances after publication
- **WHEN** reconciliation is requested
- **THEN** the platform preserves task/PR ancestry so the updated task head can be fast-forward pushed to the same PR branch
- **AND** it does not rebase the published branch or require force-push

#### Scenario: Task worktree is dirty

- **WHEN** safe reconciliation would require automatically stashing, resetting or otherwise hiding dirty task work
- **THEN** the platform stops with an actionable blocker
- **AND** leaves the dirty work untouched

#### Scenario: Reconciliation conflicts

- **WHEN** current main cannot be incorporated without a merge conflict
- **THEN** the operation stops before publication
- **AND** reports the conflicting repository-relative paths
- **AND** does not guess a resolution

### Requirement: Freshness drift is visible before another expensive validation run

Supported task status/preflight SHALL expose when the current managed task head is behind authoritative main before the platform begins a new expensive authoritative validation cycle. A stale observation SHALL remain resumable rather than being reported as terminal task failure.

#### Scenario: Main advanced after prior task work

- **GIVEN** a managed task was previously valid
- **AND** authoritative main advances while the task remains active
- **WHEN** the operator asks for task status or begins the finish path
- **THEN** the platform reports that reconciliation is required before expensive validation
- **AND** points to the supported reconcile operation

### Requirement: Reconciliation preserves validation and publication authority

A successful reconcile SHALL create a new task head that must satisfy the current required validation and exact-head publication lifecycle. Reconciliation SHALL NOT reuse stale validation evidence as if it applied to the new head and SHALL NOT create a second publication path.

#### Scenario: Reconciled task resumes delivery

- **GIVEN** reconciliation completed successfully
- **WHEN** delivery resumes
- **THEN** current required checks run for the reconciled head
- **AND** publication continues through the existing exact-head PR/recovery mechanism
- **AND** a repeated reconcile on an already-current head is a no-op

### Requirement: Managed work carries explicit process-evidence linkage

When a human explicitly fixes accepted process evidence into a managed task, the platform SHALL support an explicit bounded list of source process issues and SHALL preserve that relation in a deterministic task representation readable by the managed lifecycle. Linked source issues SHALL remain evidence records, SHALL stay open while remediation is incomplete, and MAY receive the minimal `process:managed` lifecycle label and one bounded backlink.

#### Scenario: Several symptoms become one managed change

- **GIVEN** several open process issues have been judged symptoms of one root cause
- **WHEN** the human explicitly creates one managed task with those evidence references
- **THEN** the managed task stores each exact source issue reference in its canonical linkage
- **AND** each eligible open evidence issue remains open and is marked as managed without duplicate backlinks
- **AND** no additional managed task is created solely because there are several source issues

#### Scenario: Evidence reference is not eligible

- **WHEN** authoring receives an inaccessible, malformed or non-process issue as explicit evidence
- **THEN** linkage fails with an actionable diagnostic
- **AND** the platform does not silently treat that issue as valid process provenance

### Requirement: Terminal managed success resolves only its linked process evidence

After the existing managed lifecycle establishes terminal delivery success, the platform SHALL reconcile the task's explicit process evidence and close each linked still-open issue with a bounded resolution record. Non-terminal, failed, blocked or cancelled work SHALL NOT be represented as having resolved its evidence.

#### Scenario: Linked managed task completes

- **GIVEN** a managed task has explicit linked process evidence
- **AND** the exact task has reached terminal delivery success under the existing lifecycle
- **WHEN** completion reconciles process evidence
- **THEN** each linked still-open process issue is closed with reason `completed`
- **AND** a bounded resolution note identifies the Development Backlog task and implementation provenance
- **AND** repeating completion produces no duplicate resolution mutation

#### Scenario: Managed task is not terminally successful

- **WHEN** the managed task is blocked, failed, abandoned or otherwise not at terminal success
- **THEN** linked process evidence remains open
- **AND** it is not classified as resolved solely because managed work exists

#### Scenario: Same friction recurs after resolution

- **GIVEN** the prior fingerprinted process issue was closed after a successful fix
- **WHEN** the same friction class is observed again
- **THEN** the router creates a new open process issue under the existing open-issue dedupe rule
- **AND** the recurrence is visible as new regression evidence rather than rewriting the historical resolved record

### Requirement: Scope-claim reconciliation never takes over a sibling worktree

Using authoritative publication state to reconcile a stale scope claim SHALL mutate only bounded coordination metadata. It SHALL NOT clean, reset, switch, delete or otherwise take over the sibling task worktree.

#### Scenario: Stale merged claim is reconciled

- **GIVEN** a sibling managed task is proven terminally merged
- **WHEN** its stale coordination claim is reconciled
- **THEN** scope ownership metadata may be released
- **AND** the sibling worktree content is left untouched

#### Scenario: Sibling worktree is dirty

- **GIVEN** the exact sibling PR is merged but its local worktree still exists with local state
- **WHEN** claim reconciliation runs
- **THEN** the platform does not clean or delete that worktree as part of scope gating
- **AND** worktree cleanup remains governed by its separate lifecycle

### Requirement: Routine process review ownership is unambiguous during task preflight

Managed-task preflight SHALL NOT present the legacy local friction review surface as a routine action required from every current task agent when the configured routine review is performed by the periodic cloud workflow. Local review commands MAY remain available for recovery or diagnostics.

#### Scenario: Pending local friction exceeds the legacy threshold

- **GIVEN** routine periodic process review is configured
- **AND** several local friction events remain pending in the legacy local cursor
- **WHEN** `agent_doctor` runs for a managed task
- **THEN** it does not instruct the task agent to perform the routine local markdown review
- **AND** any message about the local surface is informational/recovery-oriented
- **AND** the weekly cloud review remains the documented routine cadence

### Requirement: Synthetic friction tests do not mutate live GitHub
Automated tests that intentionally generate synthetic friction or containment violations SHALL preserve fixture-local evidence while preventing live GitHub issue/comment mutations caused by host authentication.

#### Scenario: Authenticated host runs containment regression
- **GIVEN** a regression test intentionally creates a containment violation
- **AND** GitHub CLI is available and authenticated on the host
- **WHEN** the synthetic friction event is recorded
- **THEN** fixture-local friction evidence remains available for assertions
- **AND** no live GitHub process record is created or updated by that test

#### Scenario: Real runtime friction
- **GIVEN** a real runtime friction event outside the hermetic test fixture
- **WHEN** normal routing prerequisites are satisfied
- **THEN** existing production friction routing remains in effect

### Requirement: Project-owned managed harnesses reconcile exact terminal delivery

When a reviewed project-owned harness proves that its exact managed PR is
merged, the platform compatibility lifecycle SHALL reconcile only the source
Issue bound by that task's `source_issue + change` provenance to terminal
`Done` and close the Issue as completed. Publish command success alone SHALL
NOT authorize this transition.

#### Scenario: Exact managed PR completes through automatic merge

- **GIVEN** a recognized project harness has an exact managed PR for head A
- **WHEN** GitHub reports that same PR as `MERGED` with `headRefOid` A
- **THEN** only the provenance-bound source Issue is reconciled to `Done` and closed
- **AND** a different archived or integration task identity is not mutated

#### Scenario: Terminal mutation fails after confirmed merge

- **GIVEN** GitHub confirms the exact managed PR is merged
- **WHEN** Project or Issue terminal mutation fails
- **THEN** the lifecycle reports pending terminal reconciliation and does not claim completion
- **AND** a later finish retry performs only the remaining reconciliation after re-proving the exact merge

#### Scenario: Delayed required checks do not change recovery semantics

- **GIVEN** a recognized project harness has just published an exact PR
- **WHEN** required checks are not yet registered for its expected head
- **THEN** the lifecycle remains resumable and does not set `Done`
- **AND** after exact merge it uses the same terminal reconciliation path

### Requirement: Friction learning can represent project-context gaps without self-modifying context

Platform friction SHALL support a bounded `context-gap` classification for high-signal evidence that an agent lacked, misread, or repeatedly guessed stable project/domain context. Context-gap evidence SHALL reuse the existing sanitized friction/process-learning pipeline and SHALL NOT automatically rewrite canonical project context or create managed work.

#### Scenario: User correction reveals missing project context
- **WHEN** a user correction or substantive task failure shows that the agent lacked or misinterpreted stable project/domain context
- **THEN** the existing friction path can record the event as a `context-gap`
- **AND** the event identifies a bounded concern such as product, domain, architecture, anti-pattern, example, or other project-context destination
- **AND** stored/routed evidence remains sanitized and excludes raw sensitive transcripts.

#### Scenario: Same context gap recurs across executions
- **WHEN** materially equivalent context-gap evidence recurs, including across different model or provider identities
- **THEN** the existing deduplication/root-cause path strengthens or updates one bounded evidence identity instead of creating a second failure-log system
- **AND** model/provider identity is not part of the root-cause fingerprint merely because the executor changed.

#### Scenario: Repetition reaches an arbitrary count
- **WHEN** the same context gap has been observed three or more times
- **THEN** repetition is available as evidence strength
- **BUT** the platform does not automatically modify canonical context
- **AND** does not automatically create or start a managed task solely because that count was reached.

### Requirement: Process review distinguishes context improvements from process/tooling fixes

Process Health Review SHALL be able to distinguish context-gap evidence from ordinary tooling/process friction and surface a bounded proposed context destination/improvement when current evidence supports that classification. The review remains advisory and read-only until a human explicitly accepts work.

#### Scenario: Review finds a recurring context root cause
- **WHEN** a review clusters multiple context-gap observations around the same likely root cause
- **THEN** the report identifies the contributing evidence and the likely context concern/destination to improve
- **AND** keeps observation, evidence, hypothesis, and proposal distinct
- **AND** does not create a managed task or edit canonical context.

#### Scenario: Evidence is actually a tooling/process defect
- **WHEN** the observed failure is better explained by lifecycle, tooling, CI, worktree, authentication, or process behavior
- **THEN** the review keeps it in the ordinary process-friction path
- **AND** does not misclassify it as a project-context defect merely because an agent made an error.

### Requirement: Accepted context improvements use the ordinary managed lifecycle

A proposed context improvement SHALL become repository work only after explicit human acceptance and SHALL then use the ordinary managed-task/OpenSpec lifecycle appropriate to the target repository.

#### Scenario: Human accepts a context improvement candidate
- **WHEN** a human explicitly accepts a reviewed context-gap proposal as work
- **THEN** generic fixation creates or reuses a Business Requirement, and explicit execution or direct technical intent enters its corresponding managed path
- **AND** context evidence is linked as provenance where supported
- **AND** no parallel context-specific task state machine is introduced.

### Requirement: Shared integration publication preserves exact provenance and protected checks

A requirement-level integration candidate SHALL bind its main base and ordered exact child heads, fail closed on stale or ambiguous inputs, and use the existing protected full-check and PR authority for final publication.

#### Scenario: A child or base changes before publication

- **WHEN** a bound child head or the authoritative main base changes before final validation
- **THEN** integration stops or explicitly reconciles and revalidates the new candidate
- **AND** it never publishes an unvalidated head or silently rewrites another worktree

#### Scenario: Candidate child edits overlap

- **WHEN** two independently handed-off child heads claim the same changed path relative to the bound base
- **THEN** candidate assembly fails before creating a publication object
- **AND** the failure identifies the conflicting children and paths

#### Scenario: The combined candidate fails verification

- **WHEN** interaction or required full checks fail
- **THEN** no child or parent is projected as terminal

#### Scenario: An interrupted publication resumes

- **GIVEN** an exact integration PR or merge is already present
- **WHEN** the operation is retried
- **THEN** it reuses and reconciles that exact publication object without duplicate PRs or false child completion

### Requirement: Overlapping verified Requirement children use a protected merge candidate

When exact patch replay cannot combine a sequential verified child chain with newer main, the platform SHALL allow an isolated merge candidate whose two parents are exact current main and final verified child head. It SHALL preserve prior candidates and child heads, make conflict resolutions reviewable, run full validation and use protected PR publication before terminal reconciliation.

#### Scenario: Accepted spec changes overlap

- **GIVEN** current main and an archived child both extend the same accepted spec
- **WHEN** exact patch replay refuses the overlap
- **THEN** a separate candidate may merge the exact child chain and retain both accepted changes after reviewed resolution
- **AND** full checks and protected publication precede Done

#### Scenario: Merge provenance is not exact

- **GIVEN** a changed child branch, wrong merge parent, unexpected resolution path or unresolved conflict
- **WHEN** the candidate is prepared, finalized or published
- **THEN** it fails without taking over a prior candidate or changing terminal status

### Requirement: Shared Requirement PR publication does not claim one child

A protected publisher handling a candidate with multiple verified internal children SHALL use an exact committed Requirement manifest as its identity and SHALL NOT infer one child for its pre-merge Project update. Required PR checks and exact merged-PR terminal reconciliation remain mandatory.

#### Scenario: Valid combined candidate

- **GIVEN** a clean candidate with a committed manifest linking multiple children to one Requirement
- **WHEN** the shared publisher opens or resumes its exact-head PR
- **THEN** it does not assign the PR to one child Issue
- **AND** the parent remains nonterminal until protected merge is confirmed

#### Scenario: Shared identity is missing or ambiguous

- **GIVEN** an absent, uncommitted, malformed or unlinked shared manifest
- **WHEN** the shared publication mode is requested
- **THEN** publication stops before push or PR mutation

### Requirement: Corrected shared merge candidates preserve immutable generations

When a verified Requirement child chain changes after an earlier shared merge candidate fails required checks, the merge recovery lifecycle SHALL assign a distinct candidate generation using both the authoritative base and exact final child head. It SHALL preserve prior branches, worktrees and PR evidence, and SHALL still reject an occupied identical generation.

#### Scenario: New verified child at the same main base

- **GIVEN** a failed shared candidate at a main base and a corrected final child head
- **WHEN** the corrected chain is assembled
- **THEN** it receives a different branch, worktree and committed manifest identity
- **AND** the earlier generation remains untouched

#### Scenario: Identical chain is retried

- **GIVEN** a candidate already exists for the same exact base and final child head
- **WHEN** another preparation is attempted
- **THEN** the occupied-generation guard blocks duplication rather than overwriting it

### Requirement: Friction events carry resolvable task attribution

New friction events SHALL record an explicit task when given, otherwise the current task branch.

#### Scenario: Event lost its task but kept branch and source issue

- **GIVEN** a recorded event has an empty task and a branch equal to the task under review
- **WHEN** the retrospective selects mandatory signals
- **THEN** the event is included as an inferred-attribution signal and must be explained
- **AND** the stored event is not modified

#### Scenario: Event recorded outside a task does not block another candidate

- **GIVEN** an event is recorded from the integration checkout while candidate A is in progress
- **WHEN** the automated retrospective of candidate B runs
- **THEN** the event is classified `no-task`, is not a signal of B and does not block it

#### Scenario: Operator classifies an event as not related to any task

- **WHEN** the operator runs the explicit no-task attribution with a reason
- **THEN** the classification is appended without changing the event
- **AND** the review output lists the event as `no-task` with that reason
- **AND** a later explicit task attribution of the same event fails

#### Scenario: Event cannot be attributed

- **GIVEN** a recent event has an empty task, no usable branch, source issue or attribution, and no `no-task` classification
- **WHEN** a manual or automated checkpoint runs
- **THEN** it refuses, naming the event and the task and no-task attribution commands
- **AND** the event is not assigned to the task under review

### Requirement: Retrospective uses a short shared template with bounded project additions

The review-path SHALL present a short shared template covering what happened and its basis, the confirmed cause kept apart from a hypothesis (an unknown cause is acceptable), the fix kept apart from a workaround, repeats and remaining problems, and the required action with a verifiable result or the reason for none.

#### Scenario: Project adds a path-scoped question

- **GIVEN** a project question is limited to a path pattern
- **WHEN** the task changes a matching file
- **THEN** the review-path presents the question after the shared template
- **AND** a task that changes no matching file does not see it

#### Scenario: Project has no additions

- **WHEN** the project-owned file is absent
- **THEN** the shared template alone is presented and completion is unaffected

### Requirement: Shared candidates grow append-only and are draft until complete

A shared Requirement candidate manifest SHALL list the expected mandatory changes and the verified children integrated so far.

#### Scenario: Later child is appended

- **GIVEN** a draft candidate PR exists for the first verified child
- **WHEN** the next child is ready
- **THEN** its exact delta is added as new commits on the same branch and the manifest is extended
- **AND** the same PR is updated by fast-forward push without a force push or duplicate

#### Scenario: Divergent or reordered growth is refused

- **GIVEN** an existing candidate branch
- **WHEN** a revision changes, removes or reorders an earlier child, a child head changed, or the branch is not a fast-forward
- **THEN** publication stops before any push or PR mutation naming the exact boundary

#### Scenario: Interrupted run resumes

- **GIVEN** a draft or ready candidate PR already exists for the exact branch
- **WHEN** the supervisor is rerun
- **THEN** it resumes that branch and PR without creating another PR or candidate

#### Scenario: Completion applies the final gates

- **GIVEN** every mandatory child is present
- **WHEN** the candidate is made ready
- **THEN** full checks are valid for the exact final head and required CI passes on that head before the protected merge path runs
- **AND** the Requirement retrospective checkpoint is not a ready or merge precondition

### Requirement: Affected-group precheck precedes full validation

When a project opts in, for changed Python paths that trigger full validation or whose selection left commands to required CI the lifecycle SHALL first execute, within their canonical groups, the test modules that directly reference those paths according to a tested static mapping, and SHALL stop before the full set when the precheck fails. Paths without a mapping SHALL proceed directly to full validation.

#### Scenario: Precheck fails
- **GIVEN** a change to a template script referenced by test modules in two canonical groups
- **WHEN** archive or finish runs full validation and one mapped test module fails
- **THEN** validation stops before the full set with a failure descriptor marking the precheck phase

#### Scenario: Precheck unavailable
- **WHEN** the precheck runner exits without a usable aggregate result
- **THEN** validation stops before the full set with a precheck-phase failure descriptor naming the precheck unavailable
- **AND** evidence, when requested, records the failure and the unavailable precheck

#### Scenario: Precheck passes
- **WHEN** the mapped test modules pass
- **THEN** the full validation set still runs completely, locally apart from the commands left to required CI
- **AND** evidence distinguishes precheck feedback from full validation results

#### Scenario: Unmapped control-plane path
- **WHEN** a changed path has no mapping, such as the selector configuration or a CI workflow
- **THEN** no precheck is claimed and full validation runs directly

### Requirement: Materialized Requirement execution does not depend on pre-authoring freshness

Once every handoff of a Requirement has a linked materialized child, Requirement advance and terminal reconciliation SHALL use the linked children and their OpenSpec as canonical and SHALL NOT require fresh pre-authoring. A material contract conflict SHALL still stop explicitly.

#### Scenario: Delivery changes bound sources
- **GIVEN** a Requirement whose children are materialized and delivered
- **AND** the delivery changed sources bound by its pre-authoring snapshot
- **WHEN** advance runs terminal reconciliation
- **THEN** it completes without requiring pre-authoring refresh

#### Scenario: A child is not yet materialized
- **WHEN** a handoff has no linked child
- **THEN** advance requires fresh pre-authoring before materializing it

### Requirement: Lifecycle GitHub calls retry classified transient failures

Requirement advance and terminal reconciliation SHALL retry GitHub/network failures classified as transient within a bounded number of attempts with backoff, and SHALL fail closed immediately on non-transient failures. Only read calls SHALL be retried automatically; mutating calls SHALL run once.

#### Scenario: Connection reset during advance
- **WHEN** a GitHub call fails with a connection reset and then succeeds
- **THEN** advance continues without operator action

#### Scenario: Persistent or non-transient failure
- **WHEN** the failure is non-transient or persists past the bound
- **THEN** the command reports a retryable or failed state with the bounded error

### Requirement: Heavy validation coordinates through an opt-in machine pool

When the machine-local pool configuration named by `DEV_PLATFORM_MACHINE_POOL` is set, every top-level heavy validation run (selected-check execution, the canonical test-group runner and Requirement full-candidate validation) SHALL acquire its weight in tokens from the machine-wide pool before running, SHALL hold them through kernel-released leases inherited by its child processes, and SHALL release them when every holder exits.

#### Scenario: Pool is busy

- **GIVEN** the pool's tokens are held by other live runs
- **WHEN** a heavy validation run starts
- **THEN** it waits, printing who holds the tokens and its queue position
- **AND** it starts only after enough tokens are free, or fails after the wait timeout naming the holders

#### Scenario: Holder dies

- **WHEN** a process holding tokens and all its children exit, including by SIGKILL
- **THEN** its tokens become free without manual cleanup
- **AND** no live holder's tokens are taken

#### Scenario: Finalization waits behind development

- **GIVEN** a `development` run and a `finalize` run both wait
- **WHEN** tokens become free
- **THEN** the `finalize` run is admitted first

#### Scenario: Nested invocation

- **WHEN** a run holding a lease starts selected checks or the test-group runner as a child
- **THEN** the child reuses the lease and acquires no tokens

#### Scenario: Pool not configured or misconfigured

- **WHEN** `DEV_PLATFORM_MACHINE_POOL` is unset
- **THEN** the run prints `DEV_PLATFORM_MACHINE_POOL: not configured` and proceeds unpooled
- **WHEN** it names a missing or invalid configuration
- **THEN** the run fails naming the problem and runs nothing

#### Scenario: Memory pressure blocks admission on macOS

- **GIVEN** a pooled run on macOS whose `vm_stat` available memory is above the minimum
- **WHEN** the kernel memory pressure level is warn or critical
- **THEN** the run waits and its waiting line names memory pressure first with the current level
- **AND** at the normal level the run is admitted
- **AND** an unreadable or unknown level fails explicitly naming the measurement

#### Scenario: Free tokens and a load blocker

- **GIVEN** every token is free and the per-CPU load exceeds the limit
- **WHEN** a run waits
- **THEN** its waiting line and the status name the load with its value and limit first, not a shortage of tokens

#### Scenario: Recommended configuration leaves no idle tokens

- **GIVEN** 6 tokens and a run weight of 3 from `DEV_PLATFORM_TEST_JOBS`
- **WHEN** two heavy runs start
- **THEN** both are admitted together and no token stays free while runs are queued
- **AND** with a weight that does not divide the tokens the status warns and names the idle tokens

#### Scenario: Light selection

- **WHEN** a selected-check execution runs only commands labelled `configuration` or `syntax` and no affected-test precheck
- **THEN** it leases one token
- **AND** a selection with a `test` or unlabelled command leases the test parallelism

### Requirement: Friction routing never substitutes a missing platform destination or label configuration

The friction router SHALL route a `scope=platform` event only to the platform repository configured as `[promotion].repo` in the enabled operator configuration. When that setting is absent or the operator configuration cannot be read, the router SHALL NOT route the event to the project's own repository; it SHALL keep the event local and report an error that names the missing or unreadable setting.

#### Scenario: Platform repository is not configured

- **GIVEN** a project whose operator configuration has no `[promotion].repo`
- **WHEN** a recorded `scope=platform` friction event is routed
- **THEN** no issue or comment is created in the project's own repository
- **AND** the event remains pending with a reason that names `[promotion].repo`

#### Scenario: Label configuration cannot be read

- **WHEN** reading the configured process label fails or yields an empty value
- **THEN** the operation reports that configuration error
- **AND** it does not apply the default label in its place

### Requirement: The local friction log is read strictly with position-independent event identity

Reading the local friction log SHALL fail with an error naming the file, and the line when applicable, if the log is unreadable or a non-empty line is not a valid dated event object; it SHALL NOT return an empty or truncated event list in that case. Tolerating a degraded log SHALL be limited to output that reports the gap and to a checkpoint that explicitly accepts the `friction-log` gap.

#### Scenario: Malformed line in the log

- **GIVEN** the local friction log contains a line that is not valid JSON
- **WHEN** a command reads friction events without an accepted gap
- **THEN** it fails with an error naming the log file and that line number

#### Scenario: Unreadable log

- **WHEN** the local friction log exists but cannot be read
- **THEN** reading events fails with an error naming the file instead of returning no events

#### Scenario: Explicitly accepted gap

- **GIVEN** the local friction log contains a malformed line
- **WHEN** a checkpoint is recorded with `--accept-gap friction-log`
- **THEN** the valid events are used and the accepted gap is stored in the receipt

#### Scenario: Legacy event identity is stable

- **GIVEN** an event line recorded without an id
- **WHEN** the log is read again after other lines were appended or an earlier line was removed
- **THEN** its identity is the same on every read
- **AND** an attribution recorded under its earlier positional id resolves to that identity

### Requirement: One root cause keeps one open friction record

A friction issue SHALL be able to carry several fingerprint markers, and routing SHALL add an event as an occurrence of the open issue that carries the event's fingerprint marker.

#### Scenario: A known root recurs under a new category

- **GIVEN** an open friction issue N for a root, and an event with another category left in `candidate` state pointing at N
- **WHEN** the agent resolves the candidate with `--same-root` issue N
- **THEN** the event becomes an occurrence comment on issue N and no new issue is created
- **AND** a later event with that category is routed directly to issue N

#### Scenario: Open duplicates are consolidated

- **WHEN** `merge-roots` is run with target N and duplicates M1 and M2
- **THEN** N carries the fingerprint markers of M1 and M2 and lists them in a comment
- **AND** M1 and M2 are closed with a comment pointing to N
- **AND** repeating the command changes nothing

#### Scenario: Invalid target

- **WHEN** the named target is closed or is not a router-generated friction issue
- **THEN** the command fails with an error naming the issue and nothing is changed

### Requirement: A merged fix closes the friction records it references

When a pull request is merged, the friction issues referenced by `Fixes-Friction: owner/repo#N` lines in its body, a commit message or a changed OpenSpec `proposal.md` SHALL be closed with a comment naming the pull request and merge commit. Friction issues without such a reference SHALL NOT be closed automatically. A reference that is malformed, names another repository or names a non-friction issue SHALL fail the run naming the reference.

#### Scenario: Fix references a friction record

- **GIVEN** a merged PR whose proposal contains `Fixes-Friction: lehard/dev-platform#405`
- **WHEN** the close-on-merge run executes for that PR
- **THEN** issue #405 is closed with a comment naming the PR and its merge commit
- **AND** a rerun does not comment again

#### Scenario: Commit trailer references a friction record

- **GIVEN** a merged PR with a commit whose message contains `Fixes-Friction: lehard/dev-platform#405`
- **WHEN** the close-on-merge run executes for that PR
- **THEN** issue #405 is closed with a comment naming the PR and its merge commit

#### Scenario: No reference

- **WHEN** a merged PR has no `Fixes-Friction:` line
- **THEN** no friction issue is closed

#### Scenario: Reference to a non-friction issue

- **WHEN** a reference names an issue that is not a router-generated friction issue
- **THEN** the run fails with an error naming that reference and closes nothing

### Requirement: Ordinary lifecycle commands do not retry friction routing

`start`, `doctor`, `finish` and Requirement `advance` SHALL NOT invoke GitHub routing of locally retained friction events and SHALL NOT wait on it or print a routing-retry warning. Retained events SHALL remain pending and SHALL be retried only by the explicit `agent_friction.py route-pending` command.

#### Scenario: Doctor with pending routing
- **GIVEN** the local friction log holds an event whose GitHub routing is pending
- **WHEN** `doctor` (or `start`, which runs it) executes
- **THEN** it does not run `route-pending`
- **AND** it prints no friction routing retry warning

#### Scenario: Finish with pending routing
- **GIVEN** a pending friction route
- **WHEN** `finish` or `advance` reaches its completion preflight
- **THEN** it does not run `route-pending` and does not wait on GitHub routing

#### Scenario: Explicit retry
- **WHEN** an operator runs `agent_friction.py route-pending`
- **THEN** pending events are retried and the JSON result reports routed, failed and withheld counts

### Requirement: Routed coordinator events name their reason and candidate

A coordinator lifecycle event (`coordinator-review-repair`, `coordinator-retry`, `coordinator-integration-repair`, `lifecycle-blocked-escalation`, `lifecycle-validation-failure`, or any event attributed to the coordinator) SHALL carry a bounded `reason` and a `candidate` naming the task branch, the PR number when one exists, and the head.

#### Scenario: Coordinator retry is routed with its cause
- **GIVEN** the coordinator schedules a bounded retry of PR candidate 42 at head `abc` because a gate was unavailable
- **WHEN** the event is routed
- **THEN** the published body names the candidate (task branch, PR 42, head `abc`) and the reason

#### Scenario: Faceless coordinator event
- **GIVEN** a locally retained coordinator event with no reason or no candidate
- **WHEN** `route-pending` runs
- **THEN** no GitHub issue or comment is created for it
- **AND** its route is recorded as `withheld` naming the missing field and it is not retried

#### Scenario: Producer without a reason
- **WHEN** the coordinator emits a friction transition into review repair, integration repair or escalation without a named red gate, or with a red gate that has no cause or evidence
- **THEN** recording fails with an error naming the PR and the state

#### Scenario: Waiting on required checks is not friction
- **WHEN** the coordinator records `blocked-retryable` without a red gate while the candidate waits on its exact-head required checks
- **THEN** the transition is published and no friction event is recorded

### Requirement: Task reconcile passes the platform merge-commit hook

Where the platform `pre-merge-commit` hook is installed, the supported task reconcile SHALL complete its merge of authoritative `origin/<main_branch>` in its own task worktree without a manual override. Reconcile SHALL NOT rebase or force-push.

#### Scenario: Reconcile of a diverged task with the hook installed

- **GIVEN** a task worktree with its own commits, the platform `pre-merge-commit` hook installed, and an advanced `origin/main`
- **WHEN** the supported reconcile runs
- **THEN** it creates the merge commit of `origin/main` without a manual override
- **AND** the task head descends from both the previous task head and `origin/main`
- **AND** no intent remains in the worktree's git directory

#### Scenario: Ad-hoc merge in a task worktree

- **WHEN** a merge commit is attempted in a task worktree without a reconcile intent
- **THEN** the hook rejects it and no merge commit is created

#### Scenario: Intent does not admit another target or worktree

- **GIVEN** a reconcile intent in one task worktree
- **WHEN** a merge of another ref is attempted there, or any merge is attempted in another worktree, or `origin/main` has moved since the intent was recorded
- **THEN** the hook rejects it and no merge commit is created

#### Scenario: Integration copy

- **WHEN** a merge commit is attempted in the integration copy
- **THEN** the hook rejects it whatever intent exists

### Requirement: Task start reports a project behind the latest platform release

When a task starts in a managed downstream project, the platform SHALL compare the project's installed platform version with the latest published release of its platform source after pending-rollout reconciliation. The platform source repository itself is not applicable.

#### Scenario: Lagging project is reported and starts
- **GIVEN** a managed project on platform 2.0.0 whose platform source's latest release is v3.0.0
- **WHEN** a task starts
- **THEN** the start prints 2.0.0, v3.0.0 and `gh workflow run rollout.yml --repo <source> -f version=v3.0.0 -f repository=<project>`, and the task is created

#### Scenario: Current project starts silently
- **GIVEN** a managed project on the latest release
- **WHEN** a task starts
- **THEN** no lag report is printed

#### Scenario: Undeterminable latest release stops the start
- **GIVEN** the latest release of the platform source cannot be read
- **WHEN** a task starts
- **THEN** the start fails naming the cause and no task is created

### Requirement: The friction checkpoint proof ignores declared generated files

The content proof that binds a managed task's friction checkpoint SHALL exclude files declared in `[[generated_files]]` at the merge base of the task and main, so a merge-only reconcile that changes only such files keeps the checkpoint valid. `finish` SHALL carry a checkpoint it has just proven fresh over its own archive commit, only when that commit is the sole child of the proven candidate. Any other change to a task-owned path SHALL still make the checkpoint stale.

#### Scenario: Merge-only reconcile touches only a generated file

- **GIVEN** a recorded friction checkpoint for a managed task
- **WHEN** a reconcile merges main that changed only a declared generated file the task also changed
- **THEN** `agent_friction.py assert-checkpoint` passes without a new checkpoint

#### Scenario: Task content changed after the checkpoint

- **WHEN** a task-owned file other than a declared generated file changes after the checkpoint
- **THEN** `assert-checkpoint` fails naming the checkpoint command

#### Scenario: Finish archives a task with a fresh checkpoint

- **GIVEN** `finish` has proven the checkpoint fresh on candidate A
- **WHEN** its archive commit, the sole child of A, changes the task content
- **THEN** `finish` rebinds the checkpoint to that commit and continues

#### Scenario: Finish cannot prove its archive commit is the sole child

- **GIVEN** the parent of the current head is not the proven candidate
- **WHEN** `finish` tries to carry the checkpoint
- **THEN** it stops naming both commits and the checkpoint stays as recorded

### Requirement: Friction routing sanitizes, deduplicates and keeps a local fallback

Routing of friction candidates SHALL sanitize credential-like content and arbitrary raw evidence, deduplicate repeated occurrences with a stable non-secret fingerprint, and preserve a durable local fallback when GitHub routing is unavailable.

#### Scenario: A friction candidate is routed

- **WHEN** a friction candidate is routed
- **THEN** credential-like content and arbitrary raw evidence are sanitized
- **AND** repeated occurrences are deduplicated with a stable non-secret fingerprint
- **AND** a durable local fallback is preserved when GitHub routing is unavailable

### Requirement: Process and friction issues remain evidence inbox state

Process/friction issues SHALL remain evidence/inbox state. Process/friction issues SHALL NOT automatically create Development Backlog tasks, materialize OpenSpec changes, dispatch executors or start remediation. Generic human fixation creates or reuses a Business Requirement and stops. Execution of that Requirement or explicit direct technical intent follows its respective intake path.

#### Scenario: A process issue exists

- **WHEN** a process/friction issue exists
- **THEN** it remains evidence/inbox state
- **AND** it does not automatically create Development Backlog tasks, materialize OpenSpec changes, dispatch executors or start remediation

### Requirement: Managed-task intake establishes the task checkout before materializing the planning contract

For platform-owned feature-capable profiles, managed-task intake SHALL first establish the task branch or worktree and then materialize the referenced OpenSpec planning contract in that task checkout.

#### Scenario: Managed-task intake runs in a feature-capable profile

- **WHEN** managed-task intake runs for a platform-owned feature-capable profile
- **THEN** it first establishes the task branch or worktree
- **AND** then materializes the referenced OpenSpec planning contract in that task checkout

### Requirement: Local affected validation selects bounded groups for mapped paths

For changed paths with a maintained, tested and unambiguous dependency mapping, local affected validation SHALL be able to select canonical bounded test/check groups rather than requiring the complete unit suite solely because the path belongs to a broad language or directory class.

#### Scenario: A changed path has a maintained dependency mapping

- **WHEN** local affected validation runs for a changed path with a maintained, tested and unambiguous dependency mapping
- **THEN** it can select canonical bounded test/check groups
- **AND** it does not require the complete unit suite solely because the path belongs to a broad language or directory class

### Requirement: The generated-file declaration is read from the observed integration commit

The generated-file declaration SHALL be read only from the observed integration commit, never from the task branch; a malformed declaration SHALL fail explicitly, and a project without a declaration has no generated files.

#### Scenario: The generated-file declaration is malformed

- **WHEN** the generated-file declaration in the observed integration commit is malformed
- **THEN** the lifecycle fails explicitly
- **AND** a declaration on the task branch is never read

### Requirement: Evidence recorded under the behind-disjoint contract stays valid

Evidence recorded earlier under the behind-disjoint contract SHALL remain valid.

#### Scenario: Earlier behind-disjoint evidence is checked

- **WHEN** evidence recorded earlier under the behind-disjoint contract is checked
- **THEN** it remains valid

### Requirement: Standard and light profiles do not acquire mandatory multi-agent coordination

`standard` and `light` profiles SHALL NOT acquire mandatory multi-agent coordination semantics from the requirement that platform-owned multi-agent execution passes admission before implementation.

#### Scenario: A standard profile task starts

- **WHEN** a task starts under the `standard` or `light` profile
- **THEN** it does not acquire mandatory multi-agent coordination semantics from the multi-agent admission requirement

### Requirement: Executable and unclassified paths keep mapped or full validation

An executable/harness/control-plane surface, or any path that cannot be confidently classified, SHALL continue to select mapped or full validation as already required.

#### Scenario: A changed path cannot be confidently classified

- **WHEN** a changed path is an executable/harness/control-plane surface or cannot be confidently classified
- **THEN** it continues to select mapped or full validation as already required

### Requirement: The post-task retrospective precedes the final checkpoint in the ordinary lifecycle

The post-task process retrospective SHALL run before the final friction checkpoint and SHALL reuse the ordinary platform lifecycle rather than require a separate agent-specific hook or background state machine.

#### Scenario: A non-trivial task reaches completion

- **WHEN** a non-trivial platform-owned task reaches terminal completion
- **THEN** the post-task process retrospective runs before the final friction checkpoint
- **AND** it reuses the ordinary platform lifecycle rather than a separate agent-specific hook or background state machine

### Requirement: The post-task retrospective classifies its findings

The post-task process retrospective SHALL distinguish problems already fixed during the task, problems already represented by existing friction/process evidence, and new meaningful unresolved/unrecorded findings. One retrospective MAY legitimately produce `0..N` new friction events.

#### Scenario: The retrospective reviews problems

- **WHEN** the post-task process retrospective reviews the task's problems
- **THEN** it distinguishes problems already fixed, problems already represented by existing friction/process evidence, and new meaningful unresolved/unrecorded findings
- **AND** it may produce zero or more new friction events

### Requirement: A none retrospective result requires a current retrospective

A `none` result SHALL mean that the bounded post-task process retrospective ran and found no new meaningful unresolved/unrecorded findings; a bare checkpoint call without a current retrospective result is insufficient.

#### Scenario: A bare checkpoint is attempted

- **WHEN** a `none` checkpoint is attempted without a current retrospective result
- **THEN** it is insufficient to complete the task

### Requirement: The retrospective result is bound to current task execution state

The retrospective/checkpoint result SHALL be bound to current task execution state sufficiently to prevent a stale result from silently completing changed work. Supported machine-detectable lifecycle/process failures SHOULD continue recording friction directly without relying on model judgment.

#### Scenario: Work changes after a retrospective result

- **WHEN** the task execution state changes after a retrospective/checkpoint result was recorded
- **THEN** the stale result does not silently complete the changed work

### Requirement: The post-task review inspects the factual execution path

The bounded post-task review SHALL inspect the factual execution path, including meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process issues, and observed material drift even when another operator, runtime or lifecycle owns the state. Harmless deviations are not friction. A clean path retains a concise `none` checkpoint.

#### Scenario: The task path contained a manual workaround

- **WHEN** the bounded post-task review runs on a task path that contained a meaningful successful manual workaround
- **THEN** the review inspects that workaround as part of the factual execution path

### Requirement: A recurrence of a known open process issue is preserved

A known open issue does not dispose of a new occurrence: the recurrence SHALL be preserved through the existing friction/process issue path.

#### Scenario: A known open issue recurs

- **WHEN** the post-task review finds a new occurrence of an already open process issue
- **THEN** the recurrence is preserved through the existing friction/process issue path

### Requirement: An unreadable retrospective evidence source is named and accepted explicitly

An evidence source that is unreadable or only partially readable SHALL be named in the review and SHALL NOT be reported as the absence of problems; a checkpoint over such a source SHALL require an explicit acceptance of that gap, recorded in the receipt.

#### Scenario: An evidence source is partially readable

- **WHEN** an evidence source of the review is unreadable or only partially readable
- **THEN** the review names it and does not report it as the absence of problems
- **AND** a checkpoint over it requires an explicit acceptance of that gap, recorded in the receipt

### Requirement: Execution provenance prefers structured runtime evidence

Execution provenance SHALL prefer structured runtime metadata or platform-owned routing/launch evidence over free-form model self-identification.

#### Scenario: Both runtime metadata and model self-identification exist

- **WHEN** structured runtime metadata and free-form model self-identification are both available
- **THEN** execution provenance uses the structured runtime metadata or platform-owned routing/launch evidence

### Requirement: Execution provenance separates selected from runtime-confirmed values

The provenance contract SHALL distinguish selected/configured model or reasoning-effort values from runtime-confirmed values. If the supported current runtime cannot establish a value truthfully, the value SHALL remain explicitly unknown rather than be inferred from a prompt, global default, model statement or unsupported assumption.

#### Scenario: The runtime cannot confirm a model value

- **WHEN** the supported current runtime cannot establish a model or reasoning-effort value truthfully
- **THEN** the value remains explicitly unknown
- **AND** it is not inferred from a prompt, global default, model statement or unsupported assumption

### Requirement: Execution provenance stays bounded and sanitized when routed

Execution provenance SHALL remain bounded metadata, not a transcript or general tracing system. Public friction routing SHALL include only sanitized provenance needed for useful comparison; raw execution evidence and unnecessary machine-local identifiers SHALL remain local by default.

#### Scenario: Friction with provenance is routed publicly

- **WHEN** a friction event with execution provenance is routed publicly
- **THEN** only sanitized provenance needed for useful comparison is included
- **AND** raw execution evidence and unnecessary machine-local identifiers remain local by default

### Requirement: A friction event without task or task branch is classified no-task

A new friction event recorded with neither an explicit task nor a current task branch, from an integration checkout or an unknown or detached branch, SHALL be classified `no-task`; such a checkout SHALL NOT be assumed to be a task.

#### Scenario: Friction is recorded from an integration checkout

- **WHEN** a new friction event is recorded without an explicit task from an integration checkout
- **THEN** the event is classified `no-task`
- **AND** the integration checkout is not assumed to be a task

### Requirement: A legacy task-less friction event on a non-task branch reads as no-task

A legacy task-less event with no other attribution evidence whose recorded branch is a non-task name SHALL be read as `no-task` without rewriting history.

#### Scenario: A legacy event has a non-task branch

- **WHEN** a legacy task-less event with no other attribution evidence has a recorded branch with a non-task name
- **THEN** it is read as `no-task`
- **AND** history is not rewritten

### Requirement: An operator classifies a friction event as no-task append-only

An operator SHALL be able to classify a recorded event as `no-task` with a reason through an explicit append-only operation; an explicit `no-task` and an explicit task attribution of the same event SHALL conflict and fail.

#### Scenario: An event has both no-task and task attribution

- **WHEN** an operator classifies an event as `no-task` that also has an explicit task attribution
- **THEN** the attributions conflict and the operation fails

### Requirement: A no-task friction event does not affect retrospectives

A `no-task` event SHALL NOT be a signal of, nor block, any task or Requirement retrospective, and SHALL be listed as such in review and checkpoint output.

#### Scenario: A no-task event exists during a retrospective

- **WHEN** a task or Requirement retrospective runs while a `no-task` event exists
- **THEN** the event is neither a signal of nor a block on the retrospective
- **AND** it is listed as `no-task` in review and checkpoint output

### Requirement: Retrospective selection attributes legacy friction events by branch or source issue

Retrospective selection SHALL attribute a legacy event whose task is empty by its recorded branch or source issue without rewriting or duplicating history.

#### Scenario: A legacy event has an empty task

- **WHEN** retrospective selection reads a legacy event whose task is empty but whose recorded branch or source issue is usable
- **THEN** it attributes the event by that branch or source issue
- **AND** history is not rewritten or duplicated

### Requirement: An unattributable friction event blocks checkpoints as an explicit ambiguity

An event that has no task, no usable branch, source issue or attribution and no `no-task` classification SHALL be reported as an explicit ambiguity, SHALL NOT be assigned to the task under review, and SHALL make both the automated and the manual task and Requirement checkpoints refuse with the event ids and the attribution commands until it is attributed or classified.

#### Scenario: An event has no attribution at all

- **WHEN** an event has no task, no usable branch, source issue or attribution and no `no-task` classification
- **THEN** it is reported as an explicit ambiguity and not assigned to the task under review
- **AND** automated and manual task and Requirement checkpoints refuse with the event ids and the attribution commands until it is attributed or classified

### Requirement: A project adds at most five optional retrospective questions

A project MAY add up to five retrospective questions in a project-owned file, each optionally limited to changed paths; questions beyond five SHALL be ignored with a report, and a missing or invalid file SHALL leave the shared path working. Project questions SHALL NOT be mandatory for every task and SHALL NOT replace the shared template.

#### Scenario: A project file lists six questions

- **WHEN** a project-owned retrospective question file lists six questions
- **THEN** the questions beyond five are ignored with a report
- **AND** the project questions do not replace the shared template

### Requirement: An incomplete shared candidate is published only as a draft

An incomplete candidate SHALL be published only as a draft PR on its stable branch and manifest path.

#### Scenario: A candidate is incomplete

- **WHEN** a shared Requirement candidate is incomplete
- **THEN** it is published only as a draft PR on its stable branch and manifest path

### Requirement: A shared candidate manifest revision is an append-only fast-forward

A new manifest revision SHALL keep earlier children as an exact prefix with identical heads and SHALL be pushed only as a fast-forward.

#### Scenario: A new manifest revision is pushed

- **WHEN** a new shared candidate manifest revision is pushed
- **THEN** it keeps earlier children as an exact prefix with identical heads
- **AND** it is pushed only as a fast-forward

### Requirement: A shared candidate leaves draft only when complete and finalized

Ready and merge arming SHALL require a complete manifest, finalized children and full checks valid on the final head. Required CI SHALL pass on the exact head before ready. These pre-merge steps SHALL NOT require the Requirement retrospective. Terminal reconciliation SHALL require the same final gates and the retrospective checkpoint.

#### Scenario: A candidate is marked ready

- **WHEN** the shared candidate PR is marked ready or armed for merge
- **THEN** a complete manifest, finalized children and valid final-head full checks are required
- **AND** required CI has passed on the exact head
- **AND** the Requirement retrospective checkpoint is not required for these pre-merge steps

#### Scenario: Terminal close requires the retrospective

- **WHEN** terminal reconciliation closes the Requirement after delivery
- **THEN** the Requirement retrospective checkpoint remains mandatory
- **AND** a missing or stale checkpoint prevents terminal close

### Requirement: An unavailable affected-group precheck stops before the full set

An affected-group precheck whose runner produced no usable result (unavailable) SHALL also stop before the full set with a failure descriptor marking the precheck phase and naming it unavailable; it SHALL NOT be replaced by silently continuing with the full set.

#### Scenario: The precheck runner produces no usable result

- **WHEN** the affected-group precheck runner produces no usable result
- **THEN** the run stops before the full set with a failure descriptor marking the precheck phase and naming it unavailable
- **AND** it does not silently continue with the full set

### Requirement: Affected-group precheck results are separate feedback evidence

Affected-group precheck results SHALL be recorded separately from the executed validation commands as feedback evidence and SHALL NOT replace or shorten the full or protected validation set.

#### Scenario: A precheck passes

- **WHEN** an affected-group precheck passes
- **THEN** its results are recorded separately from the executed validation commands as feedback evidence
- **AND** the full or protected validation set is neither replaced nor shortened

### Requirement: Downstream projects retain the archived-child multi-child path

Downstream projects SHALL retain the existing archived-child multi-child path.

#### Scenario: A downstream project runs a multi-child Requirement

- **WHEN** a downstream project executes a multi-child Requirement
- **THEN** it retains the existing archived-child multi-child path

### Requirement: A single-child Requirement uses its child PR against main

A single-child Requirement SHALL use its child PR against main.

#### Scenario: A Requirement has one child

- **WHEN** a single-child Requirement is executed
- **THEN** its child PR targets main

### Requirement: Nested heavy validation runs reuse the parent machine pool lease

Nested heavy validation runs SHALL reuse the parent machine pool lease without acquiring more tokens, and the test runner's parallelism SHALL NOT exceed the lease weight.

#### Scenario: A heavy run starts another heavy run

- **WHEN** a pooled heavy validation run starts a nested heavy validation run
- **THEN** the nested run reuses the parent lease without acquiring more tokens
- **AND** the test runner's parallelism does not exceed the lease weight

### Requirement: Machine pool acquisition is all-or-nothing and priority ordered

Machine pool token acquisition SHALL be all-or-nothing and ordered by priority class (`finalize` before `development`) then arrival, and SHALL fail explicitly naming the holders after the configured wait timeout instead of running outside the pool.

#### Scenario: A finalize run and a development run wait

- **WHEN** a `finalize` run and an earlier `development` run wait for machine pool tokens
- **THEN** the `finalize` run acquires first, all-or-nothing
- **AND** a run still waiting after the configured wait timeout fails explicitly naming the holders

### Requirement: Machine pool acquisition waits on load, memory and memory pressure

Machine pool token acquisition SHALL wait while the per-CPU load exceeds the configured limit, available memory is below the configured minimum or, on macOS, the kernel memory pressure level is above normal (an unmeasurable or unknown value SHALL fail explicitly).

#### Scenario: Memory pressure is above normal on macOS

- **WHEN** machine pool token acquisition runs on macOS while the kernel memory pressure level is above normal
- **THEN** acquisition waits
- **AND** an unmeasurable or unknown memory pressure value fails explicitly

### Requirement: An unset machine pool runs unpooled while an invalid one fails

When the variable `DEV_PLATFORM_MACHINE_POOL` is unset the heavy validation run SHALL print `DEV_PLATFORM_MACHINE_POOL: not configured` and run unpooled; a set but missing or invalid configuration SHALL fail explicitly naming the key or path.

#### Scenario: The machine pool configuration path is missing

- **WHEN** `DEV_PLATFORM_MACHINE_POOL` is set to a path that does not exist
- **THEN** the heavy validation run fails explicitly naming the path

### Requirement: A non-test selected-check execution leases one machine pool token

A selected-check execution SHALL lease one machine pool token when every selected command is labelled with a non-test evidence type (`configuration` or `syntax`) and no affected-test precheck runs; otherwise its weight is the test parallelism bounded by the tokens, and an unlabelled command counts as a test command.

#### Scenario: Only configuration checks are selected

- **WHEN** every selected command is labelled `configuration` or `syntax` and no affected-test precheck runs
- **THEN** the selected-check execution leases one token
- **AND** an unlabelled command would count as a test command

### Requirement: A waiting machine pool run reports its actual blocker first

A waiting machine pool run SHALL report the actual blocker first (queue, load, memory, memory pressure, tokens or admission) with its current value and threshold, before the needed and free tokens, its queue position and the holders.

#### Scenario: A run waits on load

- **WHEN** a heavy validation run waits because the per-CPU load exceeds the configured limit
- **THEN** it reports load with its current value and threshold first
- **AND** then the needed and free tokens, its queue position and the holders

### Requirement: A read-only machine pool status command shows pool state and fit

A read-only machine pool status command SHALL show configuration, holders, waiters, load, memory, the head waiter's blocker in the same terms, and the effective run weight in the caller's environment with how many such runs fit and how many tokens stay idle, warning when the tokens are not a multiple of that weight.

#### Scenario: Pool tokens are not a multiple of the run weight

- **WHEN** the machine pool status command runs and the tokens are not a multiple of the effective run weight
- **THEN** it shows configuration, holders, waiters, load, memory, the head waiter's blocker, the effective run weight, how many such runs fit and how many tokens stay idle
- **AND** it warns that the tokens are not a multiple of that weight

### Requirement: Machine pool formats stay compatible across platform releases

The machine pool configuration keys and the slot, ticket and lease formats SHALL stay unchanged so that participants on different platform releases share one pool.

#### Scenario: Participants run different platform releases

- **WHEN** heavy validation runs from different platform releases use one machine pool
- **THEN** they share it through unchanged configuration keys and slot, ticket and lease formats

### Requirement: A broken friction process label configuration is an error

A read error of the process label configuration, or an empty or non-string configured label, SHALL be reported as an error and SHALL NOT be replaced by the default label.

#### Scenario: The configured process label is empty

- **WHEN** the friction router reads a process label configuration whose configured label is empty
- **THEN** it reports an error
- **AND** it does not replace the label with the default label

### Requirement: Local friction events without an id get a content-derived identity

A local friction log event recorded without an id SHALL receive an identity derived from its content rather than its position in the file, and an earlier positional reference SHALL resolve to that identity or fail with a named error.

#### Scenario: An event without an id is referenced

- **WHEN** an event recorded without an id is referenced by an earlier positional reference
- **THEN** the reference resolves to the identity derived from the event content or fails with a named error

### Requirement: A candidate friction event is resolved by an explicit decision

An event left in the `candidate` route state SHALL be resolvable by an explicit decision that either attaches it to a named open friction issue, which then also carries the event's fingerprint marker, or creates a new root issue.

#### Scenario: A candidate event is attached

- **WHEN** an explicit decision attaches a `candidate` event to a named open friction issue
- **THEN** the issue also carries the event's fingerprint marker

### Requirement: Duplicate open friction issues are consolidated explicitly

Already open duplicates of one root SHALL be consolidable into one issue by an explicit command that moves their markers and closes them with a reference to the kept issue.

#### Scenario: Two open issues share one root

- **WHEN** the consolidation command runs on open duplicate friction issues of one root
- **THEN** their markers move to the kept issue
- **AND** the duplicates are closed with a reference to the kept issue

### Requirement: A friction resolution target must be an open router-generated issue

A target that is not an open router-generated friction issue SHALL be a named error.

#### Scenario: The target issue is closed

- **WHEN** an attach decision or a consolidation names a target that is not an open router-generated friction issue
- **THEN** the operation fails with a named error

### Requirement: Other coordinator event producers fail without reason and candidate

Producers of coordinator lifecycle events other than the publication coordinator SHALL fail explicitly with a named error rather than record such an event without a bounded `reason` and a `candidate`.

#### Scenario: A producer lacks the candidate

- **WHEN** a producer other than the publication coordinator is about to record a coordinator lifecycle event without a `candidate`
- **THEN** it fails explicitly with a named error

### Requirement: The friction router renders or withholds coordinator events

The router SHALL render the reason and candidate of a coordinator lifecycle event in the published issue or comment, and SHALL NOT route a coordinator event that lacks either; such an event SHALL be recorded locally as `withheld` with the missing field named and SHALL NOT be retried.

#### Scenario: A coordinator event lacks its reason

- **WHEN** the router receives a coordinator event without a `reason`
- **THEN** it does not route the event
- **AND** the event is recorded locally as `withheld` naming the missing field and is not retried

### Requirement: Task reconcile records a one-shot merge intent

Before the single merge of authoritative `origin/<main_branch>`, task reconcile SHALL record a one-shot intent in the task worktree's own git directory naming the task branch and the commit of `origin/<main_branch>`, and SHALL remove it after the merge whatever the outcome.

#### Scenario: Reconcile merge fails

- **WHEN** task reconcile records the one-shot intent and its merge of `origin/<main_branch>` fails
- **THEN** the intent is removed after the merge

### Requirement: The merge-commit hook admits only an intended reconcile merge

The platform `pre-merge-commit` hook SHALL admit a merge commit only in a linked task worktree whose git directory holds the one-shot reconcile intent for the current branch, when `GIT_REFLOG_ACTION` is exactly `merge origin/<main_branch>` and `origin/<main_branch>` still points to the recorded commit, and SHALL consume the intent.

#### Scenario: origin main moved after the intent was recorded

- **WHEN** a merge commit is attempted in a linked task worktree holding the intent but `origin/<main_branch>` no longer points to the recorded commit
- **THEN** the hook does not admit the merge commit

### Requirement: The merge-commit hook keeps blocking every other merge commit

The platform `pre-merge-commit` hook SHALL keep blocking every other merge commit, including every merge commit in the integration copy, and SHALL NOT be removed or disabled.

#### Scenario: A merge commit is attempted in the integration copy

- **WHEN** a merge commit is attempted in the integration copy
- **THEN** the hook blocks it
- **AND** the hook is not removed or disabled

### Requirement: Task start warns and continues for a project behind the latest release

When the project is behind the latest published release of its platform source, task start SHALL print the project's version, the latest version and the exact Roll Out Platform command that opens the update pull request for this project, and SHALL continue the start (warn and continue). A project on the latest release SHALL start without the report.

#### Scenario: The project is behind

- **WHEN** a task starts in a managed downstream project whose installed platform version is behind the latest release
- **THEN** task start prints the project's version, the latest version and the exact Roll Out Platform command
- **AND** the start continues

### Requirement: Task start fails when the platform release comparison cannot be determined

When the project version, the platform source, the project repository or the latest release cannot be determined, task start SHALL fail with the cause instead of skipping the comparison.

#### Scenario: The latest release cannot be determined

- **WHEN** task start cannot determine the latest release of the platform source
- **THEN** task start fails with the cause
- **AND** the comparison is not skipped

