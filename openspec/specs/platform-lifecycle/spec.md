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

Platform friction SHALL remain local unless explicitly promoted. Promotion SHALL omit raw evidence by default, sanitize obvious credential-like content, and require an explicit authenticated action.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem and an authenticated promotion is explicitly requested
- **THEN** only sanitized structured evidence is sent to the central platform inbox

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

PR publication SHALL support an automatic task merge policy that completes ordinary agent work after required GitHub checks pass, while retaining an explicit manual-review policy. Temporary check-registration delay and repository-supported async merge policy SHALL be handled inside the same lifecycle invocation. Required-check registration and terminal state SHALL be determined from structured GitHub state for the current PR head, not from human-readable CLI message matching.

#### Scenario: Required checks are not registered immediately

- **GIVEN** `pr_merge_mode=auto`
- **AND** the task PR was just created or updated
- **WHEN** structured GitHub state shows that required checks for the current PR head are not registered yet
- **THEN** the platform waits for check registration for a bounded period
- **AND** continues waiting for the required checks once they appear
- **AND** does not require a manual rerun solely because registration was delayed within that bound

#### Scenario: Required-check registration wait expires

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** the bounded registration wait expires before required checks are visible for the current head
- **THEN** the PR and feature branch remain intact
- **AND** local main remains unchanged
- **AND** the lifecycle reports a resumable remote-pending state rather than inferring failure from CLI text
- **AND** rerunning the same task finish operation re-queries authoritative remote state

#### Scenario: Structured required check fails

- **GIVEN** required checks are registered for the current PR head
- **WHEN** structured GitHub state reports a required check in a failing terminal state
- **THEN** the platform does not merge the PR
- **AND** local main remains unchanged
- **AND** the failing required check is reported without relying on arbitrary log text

#### Scenario: Merge queue remains pending past the bounded wait

- **GIVEN** GitHub accepted auto-merge or merge-queue enrollment
- **WHEN** the bounded merge confirmation wait expires before the exact task PR reaches `MERGED`
- **THEN** the platform does not begin local-main reconciliation
- **AND** leaves the PR available for GitHub to continue processing
- **AND** a later rerun checks whether the exact task head has since merged and resumes safely

#### Scenario: Automatic task PR succeeds

- **GIVEN** `pr_merge_mode=auto`
- **WHEN** required PR checks succeed and GitHub accepts an ordinary protected merge
- **THEN** the platform confirms the PR is `MERGED`
- **AND** updates the local integration copy to the merged remote state
- **AND** completes normal board/worktree cleanup

#### Scenario: Repository requires auto-merge or merge queue

- **GIVEN** `pr_merge_mode=auto`
- **AND** required PR checks have succeeded
- **WHEN** GitHub rejects the ordinary merge form because repository policy requires asynchronous auto-merge or merge-queue enrollment
- **THEN** the platform tries supported non-bypass auto/queue merge forms
- **AND** waits for GitHub to report the PR as `MERGED` for a bounded period
- **AND** does not use an administrative bypass

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

- **WHEN** a task is waiting for required checks, auto-merge, or merge-queue completion
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

The platform lifecycle SHALL distinguish planned managed work from small direct
quick work before implementation begins. A Development Backlog issue explicitly
supplied as the task source SHALL use managed-task intake and OpenSpec
preflight. For platform-owned feature-capable profiles, managed-task intake
SHALL first establish the task branch or worktree and then materialize the
referenced OpenSpec planning contract in that task checkout. A small task
directly requested by the user MAY enter the existing execution lifecycle
without first creating a central backlog issue or ceremonial OpenSpec.

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

For an exact-head automatic task PR, the platform SHALL prefer to persist merge intent in native GitHub auto-merge / merge-queue state before entering a long local wait. Every protected merge request SHALL include an exact expected task-head guard.

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

#### Scenario: Native auto-merge is not available

- **WHEN** repository capability/policy does not allow the platform to persist remote automatic merge intent
- **THEN** the existing bounded foreground required-check and protected-merge path remains available
- **AND** the task remains safely resumable through the same exact branch/PR
- **AND** status reports degraded remote durability rather than claiming durable remote execution

### Requirement: Existing published PR recovery is distinct from first-publication freshness

The platform SHALL preserve the existing fresh-base prerequisite for first publication while allowing an already-existing exact-head task PR to continue through GitHub protection after the base advances. It SHALL NOT silently rewrite the candidate branch during recovery.

#### Scenario: Base advances after exact PR was opened

- **GIVEN** an exact-head task PR already exists
- **AND** the configured base advances before merge
- **WHEN** normal finish runs again
- **THEN** it re-observes the existing PR before applying first-publication stale-base rejection
- **AND** GitHub required checks / branch protection / merge queue determine whether integration may proceed

#### Scenario: Repository requires candidate branch update

- **GIVEN** an existing exact-head PR cannot integrate because repository policy requires an updated branch
- **AND** no supported queue/automatic integration path can satisfy that policy
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

For `harness_mode=platform` and `pr_merge_mode=auto`, platform diagnostics SHOULD report whether repository-native auto-merge / queue capability is available to persist the remote waiting step. Task publication SHALL NOT silently enable or disable repository-level auto-merge settings.

#### Scenario: Repository auto-merge is disabled

- **WHEN** automatic task publication is configured but native auto-merge/queue is unavailable
- **THEN** doctor/status reports the foreground fallback accurately
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

The platform SHALL distinguish a conservative `local affected` feedback policy from a `protected full` merge-authority policy. A protected-main PR SHALL require the complete authoritative platform validation set even when a local affected subset has succeeded.

#### Scenario: Proven local affected change

- **WHEN** every changed path is mapped by a maintained and tested selector rule
- **THEN** local feedback may execute the mapped affected checks
- **AND** the resulting success is not accepted as the protected PR required validation result

#### Scenario: Protected-main PR is evaluated

- **WHEN** a protected-main PR contains any platform change
- **THEN** CI executes the complete authoritative validation set required by the protected publication contract
- **AND** merge authority does not depend on a prior local affected run

### Requirement: Validation selection fails closed

The validation selector SHALL choose the full authoritative set whenever a changed path is unknown, ambiguously classified, or affects selector/configuration, workflow, OpenSpec, lifecycle, or other explicitly high-impact control-plane code.

#### Scenario: Changed path has no proven selector mapping

- **WHEN** local affected validation receives a path without an explicit safe mapping
- **THEN** it selects the full validation set
- **AND** reports that the fallback was safety-driven

#### Scenario: Control-plane path changes

- **WHEN** a change touches validation selection/configuration, CI workflow, OpenSpec, or lifecycle control-plane code
- **THEN** local affected validation selects the full validation set

### Requirement: Parallel validation preserves resource isolation and aggregate authority

The platform SHALL run validation partitions concurrently only when each partition's mutable resources are isolated per worker or explicitly serialized. When CI uses partitions, it SHALL publish a stable aggregate required check that fails if any mandatory partition fails.

#### Scenario: Candidate partition shares mutable state

- **WHEN** the resource audit identifies a shared mutable database, artifact path, lock, port, external state, or process-global setting
- **THEN** the candidate is serialized or given proven per-worker isolation before concurrent execution is enabled

#### Scenario: Partitioned required validation fails

- **WHEN** any mandatory validation partition fails
- **THEN** the stable aggregate required check reports failure
- **AND** protected-main merge remains blocked

### Requirement: New work reconciles an authoritative pending platform rollout first

Before a supported new task starts in a managed repository, the platform SHALL determine whether the repository has an authoritative eligible Dev Platform rollout PR that still needs adoption. For platform-owned task execution, this reconciliation SHALL occur before creating a new task branch or worktree. A safely adoptable rollout SHALL be merged and locally reconciled before product work starts; an unsafe or ambiguous rollout SHALL block new work with an actionable state.

#### Scenario: No pending rollout exists

- **WHEN** pre-task reconciliation finds no authoritative eligible rollout PR for the repository
- **THEN** normal task synchronization/start continues without a rollout-specific human step

#### Scenario: Current rollout is green and safe to adopt

- **GIVEN** pre-task reconciliation finds the current authoritative eligible rollout PR
- **AND** the exact current PR head satisfies required downstream GitHub gates and merge policy
- **WHEN** the supported task start proceeds
- **THEN** the platform merges that exact rollout through ordinary non-bypass GitHub policy
- **AND** confirms the remote merge
- **AND** synchronizes the local integration branch to the merged remote state
- **AND** only then creates or enters the new task workspace

#### Scenario: Rollout checks or policy are not satisfied

- **GIVEN** an authoritative pending rollout exists
- **WHEN** its required checks are pending/failed, it conflicts, its head changes, required review remains unsatisfied, or another safety condition prevents ordinary merge
- **THEN** the platform does not start new product work on top of the older platform state
- **AND** reports a concrete pending/blocker state that can be retried after the condition changes
- **AND** does not force-push or bypass repository protection

#### Scenario: Rollout merged before local reconciliation completed

- **GIVEN** the authoritative rollout PR is already confirmed merged remotely
- **AND** local integration is still behind
- **WHEN** pre-task reconciliation is retried
- **THEN** the platform synchronizes local integration idempotently
- **AND** does not create or merge a second rollout PR

### Requirement: Project-owned harness preserves rollout preflight

A managed repository using `harness_mode=project` SHALL retain its repository-owned task/worktree lifecycle while still treating platform rollout reconciliation as a prerequisite to new work.

#### Scenario: Project owns task harness

- **GIVEN** a managed repository uses `harness_mode=project`
- **WHEN** the agent prepares to start new work
- **THEN** platform guidance/readiness exposes the pending-rollout reconciliation result before delegating task execution to the repository-owned harness
- **AND** Dev Platform does not replace the project-owned task/worktree implementation

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
