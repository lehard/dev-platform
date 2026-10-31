## MODIFIED Requirements

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

### Requirement: Local affected validation never replaces protected PR authority

The platform SHALL distinguish a conservative `local affected` feedback policy from a `protected full` merge-authority policy. A protected-main PR SHALL still require the complete authoritative platform validation set even when a local affected subset has succeeded.

#### Scenario: Proven local affected change

- **WHEN** every changed path is covered by maintained and tested mappings to bounded canonical test/check groups
- **THEN** local feedback executes those mapped groups without unrelated full-suite work
- **AND** a group selected by multiple changed paths is executed only once within the validation invocation
- **AND** the resulting success is not accepted as the protected PR required validation result

#### Scenario: Local path is unknown or high impact

- **WHEN** a changed path is unknown, ambiguously classified, or affects selector/check configuration, CI workflow, OpenSpec/lifecycle control-plane code or another explicitly high-impact surface
- **THEN** local affected validation selects the full authoritative set
- **AND** reports that the fallback was safety-driven

#### Scenario: Protected-main PR is evaluated

- **WHEN** a protected-main PR contains any platform change
- **THEN** CI executes every mandatory validation group in the complete authoritative validation set for the current head
- **AND** merge authority does not depend on a prior local affected run

### Requirement: New work reconciles an authoritative pending platform rollout first

Before a supported new task starts in a managed repository, the platform SHALL determine whether the repository has an authoritative eligible Dev Platform rollout PR that still needs adoption. For platform-owned task execution, this reconciliation SHALL occur before creating a new task branch or worktree. A safely adoptable rollout SHALL be merged and locally reconciled before product work starts; an unsafe or ambiguous rollout SHALL block new work with an actionable state.

#### Scenario: No pending rollout exists

- **WHEN** pre-task reconciliation finds no authoritative eligible rollout PR for the repository
- **THEN** normal task synchronization/start continues without a rollout-specific human step

#### Scenario: Current rollout is green and safe to adopt

- **GIVEN** pre-task reconciliation finds the current authoritative eligible rollout PR
- **AND** the exact current PR head satisfies required downstream GitHub gates and merge policy
- **AND** no rollout deferral is set for the session
- **WHEN** the supported task start proceeds
- **THEN** start announces the rollout merge and local synchronization it is about to perform
- **AND** the platform merges that exact rollout through ordinary non-bypass GitHub policy
- **AND** confirms the remote merge
- **AND** synchronizes the local integration branch to the merged remote state
- **AND** only then creates or enters the new task workspace

#### Scenario: Rollout checks or policy are not satisfied

- **GIVEN** an authoritative pending rollout exists
- **AND** no rollout deferral is set for the session
- **WHEN** its required checks are pending/failed, it conflicts, its head changes, required review remains unsatisfied, or another safety condition prevents ordinary merge
- **THEN** the platform does not start new product work on top of the older platform state
- **AND** reports a concrete pending/blocker state that can be retried after the condition changes
- **AND** does not force-push or bypass repository protection

#### Scenario: Rollout merged before local reconciliation completed

- **GIVEN** the authoritative rollout PR is already confirmed merged remotely
- **AND** local integration is still behind
- **AND** no rollout deferral is set for the session
- **WHEN** pre-task reconciliation is retried
- **THEN** the platform synchronizes local integration idempotently
- **AND** does not create or merge a second rollout PR

#### Scenario: Session defers a green pending rollout

- **GIVEN** an authoritative pending rollout PR is green and safe to adopt
- **AND** the session set `DEV_PLATFORM_DEFER_ROLLOUT=1` (directly or through `--defer-rollout`)
- **WHEN** a managed or quick task starts
- **THEN** the rollout PR remains open and unchanged and local integration is not synchronized for it
- **AND** start reports that the rollout was skipped, naming the PR and the session deferral
- **AND** start completes normally on the current platform state

#### Scenario: Session defers a pending rollout that is not green

- **GIVEN** an authoritative pending rollout PR whose checks are pending, failed or ambiguous
- **AND** the session set `DEV_PLATFORM_DEFER_ROLLOUT=1`
- **WHEN** a task starts
- **THEN** start reports the rollout as skipped with its observed state instead of blocking, and changes nothing

#### Scenario: Deferral set but nothing is pending

- **GIVEN** `DEV_PLATFORM_DEFER_ROLLOUT=1` and no authoritative pending rollout
- **WHEN** a task starts
- **THEN** start proceeds as it does without the deferral

#### Scenario: Invalid deferral value

- **WHEN** `DEV_PLATFORM_DEFER_ROLLOUT` is set to a value other than empty or `1`
- **THEN** start fails before any rollout observation or mutation, naming the variable and the accepted value

#### Scenario: Deferral does not affect project-owned harnesses

- **GIVEN** a repository uses `harness_mode=project`
- **WHEN** a task starts with or without the deferral
- **THEN** platform reconciliation is skipped exactly as before

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

#### Scenario: Coordinator finalization checks the reviewed content on its proven base

- **GIVEN** a coordinator-mode finalization checkout of a reviewed candidate whose head forks from its proven base
- **AND** `origin/<main>` has advanced past that base
- **WHEN** selected checks are executed with that proven base
- **THEN** the freshness gate passes, naming the coordinator-finalization contract and the base
- **AND** the selected commands actually run and a failing command fails the invocation

#### Scenario: Proven base is not a general freshness bypass

- **WHEN** a proven base is passed together with evidence output, a contribution base or protected-full validation, without execution, outside the coordinator lifecycle mode, or with a commit that is not the merge base of the head and `origin/<main>`
- **THEN** the invocation fails before any command starts, naming the violated condition
- **AND** an invocation without a proven base on a stale head is still blocked by the fresh-base requirement

#### Scenario: Coordinator candidate behind main overlapping only in the generated manifest is handed off

- **GIVEN** a coordinator-managed candidate whose head does not contain the freshly fetched `origin/<main>`
- **AND** both the candidate and `origin/<main>` changed the declared generated platform manifest, and a trial merge conflicts only there
- **WHEN** evidence-producing selected checks, the developer handoff, re-admission or status run
- **THEN** the freshness gate passes, naming the behind-mergeable contract, the observed main, the merge base and the generated-file conflict
- **AND** the evidence records that contract
- **AND** no reconcile is required

#### Scenario: Coordinator candidate behind a disjoint main is handed off without reconcile

- **GIVEN** a coordinator-managed candidate whose head does not contain the freshly fetched `origin/<main>`
- **AND** the files `origin/<main>` changed since the merge base are disjoint from the candidate's changed files and a trial merge is clean
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the freshness gate passes under the behind-mergeable contract, naming the observed main and the merge base
- **AND** the evidence records that contract
- **AND** no reconcile is required

#### Scenario: Coordinator candidate overlapping main with a clean merge is handed off

- **GIVEN** a coordinator-managed candidate whose head does not contain `origin/<main>`
- **AND** `origin/<main>` changed an ordinary file the candidate also changed, and a trial merge is clean
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the freshness gate passes under the behind-mergeable contract, naming the overlapping path
- **AND** no reconcile is required

#### Scenario: Coordinator candidate overlapping main must reconcile

- **GIVEN** a coordinator-managed candidate whose head does not contain `origin/<main>`
- **AND** both changed a file that is not declared generated and a trial merge conflicts in it
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the lifecycle stops before any expensive command, naming the conflicting files and the reconcile command

#### Scenario: A candidate cannot declare its own conflict generated

- **GIVEN** a coordinator-managed candidate that adds a generated-file declaration for a file it conflicts in
- **AND** the observed `origin/<main>` does not declare that file
- **WHEN** evidence-producing selected checks or the developer handoff run
- **THEN** the conflict blocks as a real conflict

#### Scenario: Quick task under the queue behind a cleanly mergeable main is handed off

- **GIVEN** the coordinator lifecycle mode with the publication queue enabled on authoritative main
- **AND** a quick task without canonical managed provenance whose head does not contain `origin/<main>`
- **AND** a trial merge with the observed `origin/<main>` is clean or conflicts only in declared generated files
- **WHEN** evidence-producing selected checks or `finish` run
- **THEN** the freshness gate passes under the behind-mergeable contract with the same answer a coordinator-managed candidate gets
- **AND** no reconcile is required, and the queue merges main and gates on the integrated head

#### Scenario: Quick task under the queue with a real conflict must reconcile

- **GIVEN** a quick task under the enabled queue whose head conflicts with `origin/<main>` in a file that is not declared generated
- **WHEN** evidence-producing selected checks or `finish` run
- **THEN** the lifecycle stops before any expensive command, naming the conflicting files and the reconcile command

#### Scenario: Non-coordinator task keeps the fresh-base rule

- **GIVEN** a task the publication queue does not integrate (a task published without the coordinator queue, or a managed task that is not a coordinator candidate) whose head does not contain `origin/<main>`
- **WHEN** evidence-producing validation is requested
- **THEN** it is blocked by the fresh-base requirement even when the changed files are disjoint

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

A shared Requirement candidate manifest SHALL list the expected mandatory changes and the reviewed child contributions integrated so far.

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
- **THEN** the retrospective checkpoint exists and full checks pass on the exact final head before the existing protected merge path runs

### Requirement: Affected-group precheck precedes full validation

When a project opts in, for changed Python paths that trigger full validation the lifecycle SHALL first execute, within their canonical groups, the test modules that directly reference those paths according to a tested static mapping, and SHALL stop before the full set when the precheck fails. Paths without a mapping SHALL proceed directly to full validation.

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
- **THEN** the full validation set still runs completely
- **AND** evidence distinguishes precheck feedback from full validation results

#### Scenario: Unmapped control-plane path
- **WHEN** a changed path has no mapping, such as the selector configuration or a CI workflow
- **THEN** no precheck is claimed and full validation runs directly

### Requirement: Post-handoff lifecycle obligations are coordinator jobs

After developer handoff, friction capture for review, repair, integration, fallback and retry events, the task and Requirement retrospectives, terminal reconciliation of Issue/Project/Requirement state and safe local worktree cleanup SHALL be performed by coordinator-published jobs. No manual completion pass SHALL be required on the happy path.

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

### Requirement: Independent children execute in parallel as contributions

Where source/coordinator publication is enabled, children of a multi-child Requirement without unmet dependencies SHALL be able to start and proceed in parallel, each as a contribution PR to the Requirement integration branch with its own checks, verification, review and repair. A dependent child SHALL start from the integration branch after its predecessors are integrated.

#### Scenario: Two independent children
- **WHEN** a Requirement has two children without dependencies
- **THEN** both can be developed and reviewed at the same time

### Requirement: Requirement retrospective reads durable coordinator evidence

The Business Requirement retrospective SHALL include durable coordinator evidence recorded on the candidate pull requests of the Requirement and its linked children, in addition to the machine-local friction log, and SHALL treat it as it treats local events: it is listed by the review-path with its pull request, head, stage and worker, it may be linked or classified by the checkpoint, and mandatory lifecycle-failure and workaround signals among it SHALL be explained.

#### Scenario: Evidence recorded on a discarded runner

- **WHEN** the retrospective runs on a checkout whose local log contains no coordinator events
- **THEN** the review-path lists the durable events attributed to the Requirement with their pull request, head, stage and worker

#### Scenario: Mandatory durable signal

- **WHEN** a durable coordinator event is a high-severity lifecycle failure or carries a workaround or override trigger
- **THEN** the checkpoint requires it to be linked or classified like a local event

#### Scenario: Durable source unreadable

- **WHEN** GitHub or a trusted evidence record cannot be read
- **THEN** the review-path reports `coordinator-evidence` as unreadable
- **AND** the checkpoint refuses until the source is repaired or the gap is explicitly accepted

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

### Requirement: Routed coordinator events name their reason and candidate

A coordinator lifecycle event (`coordinator-review-repair`, `coordinator-retry`, `coordinator-integration-repair`, `lifecycle-blocked-escalation`, `lifecycle-validation-failure`, or any event attributed to the coordinator) SHALL carry a bounded `reason` and a `candidate` naming the task branch, the PR number when one exists, and the head.

#### Scenario: Coordinator retry is routed with its cause
- **GIVEN** the coordinator schedules a bounded retry of PR candidate 42 at head `abc` because a gate was unavailable
- **WHEN** the event is routed
- **THEN** the published body names the candidate (task branch, PR 42, head `abc`) and the reason

#### Scenario: Validation failure carries the failing check
- **WHEN** `finish` records `lifecycle-validation-failure`
- **THEN** the event reason names the failure class and failing check from the selector descriptor
- **AND** the candidate names the current branch and head

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

### Requirement: A contribution re-bases its integration job onto a moved requirement branch head

When a reviewed contribution's integration job was offered for a requirement integration branch head that has since moved, the coordinator worker SHALL NOT silently discard it. If the moved head still contains the contribution's recorded base, the worker SHALL re-offer the same integration job for the same contribution head and identity, bound to the moved head, without merging onto a head the job was not bound to.

#### Scenario: Another contribution integrated first

- **GIVEN** a contribution's integration job is bound to requirement branch head A
- **AND** the branch fast-forwarded to head B that contains the contribution base
- **WHEN** the worker runs the job
- **THEN** it publishes the same integration job bound to B and reports the target as moved
- **AND** it does not merge the contribution in that run

#### Scenario: Branch moves during the run

- **WHEN** the requirement branch moves after the worker checked it and before the protected merge
- **THEN** the worker re-offers the job bound to the newly observed head under the same base condition

#### Scenario: Base no longer contained

- **WHEN** the moved head does not contain the contribution base
- **THEN** the job fails naming the base and the moved head, and no job is re-offered

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

## ADDED Requirements

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

### Requirement: A session can explicitly defer platform rollout adoption

A session MAY explicitly defer rollout adoption with `DEV_PLATFORM_DEFER_ROLLOUT=1`, which the `--defer-rollout` flag of `start_task.py`, `start_managed_task.py`, `execute_managed_task.py` and `execute_requirement.py advance` sets for the process and its children. Any other non-empty value of the variable `DEV_PLATFORM_DEFER_ROLLOUT` SHALL be an explicit error naming it.

#### Scenario: The rollout deferral variable has another value

- **WHEN** `DEV_PLATFORM_DEFER_ROLLOUT` is set to a non-empty value other than `1`
- **THEN** task start fails with an explicit error naming the value

### Requirement: A deferred platform rollout is only observed

While the rollout adoption deferral is set, task start SHALL only observe the rollout: task start SHALL NOT merge, close, relabel or otherwise change the rollout PR, SHALL NOT synchronize local integration for it, and SHALL report that the rollout was skipped, naming the PR and the deferral.

#### Scenario: Task start runs with the rollout deferred

- **WHEN** task start runs while the rollout adoption deferral is set and a rollout PR is pending
- **THEN** task start does not merge, close, relabel or otherwise change the rollout PR
- **AND** it does not synchronize local integration for it
- **AND** it reports that the rollout was skipped, naming the PR and the deferral

### Requirement: Task start announces a rollout merge before performing it

Without the rollout adoption deferral, immediately before merging a rollout, start SHALL announce the PR, the merge and the local synchronization it is about to perform and how to defer them, and `agent_doctor.py` SHALL report a green pending rollout as one the next task start will merge.

#### Scenario: Task start is about to merge a rollout

- **WHEN** task start without the deferral is about to merge a rollout
- **THEN** it first announces the PR, the merge and the local synchronization it is about to perform and how to defer them
- **AND** `agent_doctor.py` reports a green pending rollout as one the next task start will merge

### Requirement: Coordinator finalization may validate against an explicit proven base

One bounded exception to the fresh task base requirement SHALL exist, for trusted coordinator finalization of a reviewed candidate. Selected-check execution SHALL accept an explicit proven base, and with it SHALL require that the head forks from exactly that commit on the remote integration branch's history, instead of requiring the head to contain the current remote integration branch.

#### Scenario: Coordinator finalization supplies a proven base

- **WHEN** selected-check execution receives an explicit proven base
- **THEN** it requires that the head forks from exactly that commit on the remote integration branch's history
- **AND** it does not require the head to contain the current remote integration branch

### Requirement: A proven base is accepted only for coordinator executed checks

The proven base of selected-check execution SHALL be accepted only for executed checks in the coordinator lifecycle mode. The proven base SHALL be refused, before any command starts and with an error naming the violated condition, when combined with evidence output, a contribution base or protected-full validation, or when the proven base is not the merge base of the head and the remote integration branch.

#### Scenario: A proven base is combined with evidence output

- **WHEN** selected-check execution receives a proven base together with evidence output, a contribution base or protected-full validation, or a proven base that is not the merge base of the head and the remote integration branch
- **THEN** it refuses before any command starts
- **AND** the error names the violated condition

### Requirement: Tasks integrated by the publication queue form a second fresh-base exception

A second bounded exception to the fresh task base requirement SHALL exist for a task the publication queue integrates: a coordinator-managed candidate, or, under the coordinator lifecycle mode with the queue enabled on the authoritative integration branch, a quick task without canonical managed provenance. The queue integrates such a task by merging the current integration branch and gating on required checks of the integrated head.

#### Scenario: A quick task runs under the queue-enabled coordinator mode

- **WHEN** a quick task without canonical managed provenance runs under the coordinator lifecycle mode with the queue enabled on the authoritative integration branch
- **THEN** it is a task the publication queue integrates
- **AND** the fresh task base exception for queue-integrated tasks applies to it

### Requirement: Queue-integrated tasks accept a behind-mergeable head

For a task the publication queue integrates, the task's developer evidence-producing validation, handoff, re-admission and status SHALL accept a head that does not contain the current remote integration branch when a trial merge of the head with the observed integration head is clean, or conflicts only in files that the project declares as generated in the committed check configuration of that observed integration commit; a path changed on both sides is not by itself a reason to block.

#### Scenario: A queue-integrated head is behind but merges cleanly

- **WHEN** a task the publication queue integrates has a head that does not contain the current remote integration branch and a trial merge with the observed integration head is clean or conflicts only in declared generated files
- **THEN** developer evidence-producing validation, handoff, re-admission and status accept the head
- **AND** a path changed on both sides does not by itself block

### Requirement: The behind-mergeable contract is reported and recorded

The lifecycle SHALL report the behind-mergeable contract with the observed integration head, the merge base, the paths changed on both sides and the generated-file conflicts, and record the behind-mergeable contract in the evidence.

#### Scenario: A behind-mergeable head is accepted

- **WHEN** the lifecycle accepts a head under the behind-mergeable contract
- **THEN** it reports the observed integration head, the merge base, the paths changed on both sides and the generated-file conflicts
- **AND** it records the behind-mergeable contract in the evidence

### Requirement: The generated-file declaration is read from the observed integration commit

The generated-file declaration SHALL be read only from the observed integration commit, never from the candidate; a malformed declaration SHALL fail explicitly, and a project without a declaration has no generated files.

#### Scenario: The generated-file declaration is malformed

- **WHEN** the generated-file declaration in the observed integration commit is malformed
- **THEN** the lifecycle fails explicitly
- **AND** a declaration in the candidate is never read

### Requirement: A non-generated conflict or missing merge base blocks queue-integrated validation

For a trial merge of a queue-integrated task head with the observed integration head, a conflict in any file other than the declared generated files or a missing merge base SHALL block before any expensive command, naming the conflicting files and the reconcile command.

#### Scenario: A trial merge conflicts in a non-generated file

- **WHEN** the trial merge conflicts in a file the project does not declare as generated, or no merge base exists
- **THEN** the lifecycle blocks before any expensive command
- **AND** it names the conflicting files and the reconcile command

### Requirement: Evidence recorded under the behind-disjoint contract stays valid

Evidence recorded earlier under the behind-disjoint contract SHALL remain valid.

#### Scenario: Earlier behind-disjoint evidence is checked

- **WHEN** evidence recorded earlier under the behind-disjoint contract is checked
- **THEN** it remains valid

### Requirement: Outside the bounded exceptions the fresh-base requirement is unchanged

Outside the two bounded exceptions for trusted coordinator finalization of a reviewed candidate and for a task the publication queue integrates, developer preflight, evidence-producing validation and protected CI SHALL keep the fresh-base requirement unchanged.

#### Scenario: Developer validation runs outside both exceptions

- **WHEN** developer preflight, evidence-producing validation or protected CI runs for a task outside both bounded exceptions
- **THEN** the fresh-base requirement applies unchanged

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

### Requirement: Child contributions reach a shared candidate through contribution PRs

Where source/coordinator publication is enabled, child contributions SHALL reach the candidate through contribution PRs targeting the Requirement integration branch and SHALL be merged into it by the coordinator after their own checks, verification and review.

#### Scenario: A child contribution is ready

- **WHEN** source/coordinator publication is enabled and a child contribution has passed its own checks, verification and review
- **THEN** the coordinator merges its contribution PR into the Requirement integration branch

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

Marking the shared candidate PR ready, arming merge, publication-queue admission and terminal reconciliation SHALL require a complete manifest, composition-level review of cross-child properties, a single finalization of all children, the Requirement retrospective checkpoint and full checks on the exact final head.

#### Scenario: A candidate is marked ready

- **WHEN** the shared candidate PR is to be marked ready, armed for merge, admitted to the publication queue or terminally reconciled
- **THEN** a complete manifest, composition-level review of cross-child properties, a single finalization of all children, the Requirement retrospective checkpoint and full checks on the exact final head are required

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

### Requirement: Post-handoff friction events are attributed to the candidate and its Requirement

Post-handoff review, repair, integration, fallback and retry events SHALL be attributed to the candidate task and its parent Requirement, and a Requirement retrospective SHALL accept events attributed to its linked children.

#### Scenario: A post-handoff repair event is recorded

- **WHEN** a repair event is recorded after developer handoff
- **THEN** it is attributed to the candidate task and its parent Requirement
- **AND** the Requirement retrospective accepts it as an event attributed to a linked child

### Requirement: Downstream projects retain the archived-child multi-child path

Downstream projects SHALL retain the existing archived-child multi-child path.

#### Scenario: A downstream project runs a multi-child Requirement

- **WHEN** a downstream project executes a multi-child Requirement
- **THEN** it retains the existing archived-child multi-child path

### Requirement: A single-child Requirement uses its child PR against main

A single-child Requirement SHALL use its child PR against main; a coordinator-managed child SHALL publish while active for review before finalization archives it.

#### Scenario: A Requirement has one child

- **WHEN** a single-child Requirement is executed
- **THEN** its child PR targets main
- **AND** a coordinator-managed child publishes while active for review before finalization archives it

### Requirement: An unreadable durable coordinator evidence source is reported as a gap

When the durable coordinator evidence source cannot be read or contains a malformed trusted record, the evidence source `coordinator-evidence` SHALL be reported as not fully readable and the checkpoint SHALL refuse it unless the gap is explicitly accepted; an unreadable source SHALL NOT be reported as an empty one.

#### Scenario: The coordinator evidence contains a malformed trusted record

- **WHEN** the durable coordinator evidence source contains a malformed trusted record
- **THEN** `coordinator-evidence` is reported as not fully readable
- **AND** the Requirement checkpoint refuses it unless the gap is explicitly accepted
- **AND** it is not reported as an empty source

### Requirement: Developer task retrospectives do not depend on GitHub coordinator evidence

Developer task retrospectives SHALL NOT depend on GitHub for durable coordinator evidence.

#### Scenario: A developer task retrospective runs without GitHub

- **WHEN** a developer task retrospective runs while GitHub is unavailable
- **THEN** it does not depend on GitHub for durable coordinator evidence

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

### Requirement: The publication coordinator takes the event reason from the named red gate

The publication coordinator SHALL take the coordinator lifecycle event reason from the transition's named red gate and SHALL fail the transition explicitly with a named error when the gate is missing or explains nothing; a `blocked-retryable` transition without a red gate waits on exact-head required checks, is not a failed gate and SHALL record no friction event.

#### Scenario: A blocked-retryable transition has no red gate

- **WHEN** the publication coordinator performs a `blocked-retryable` transition without a red gate
- **THEN** it waits on exact-head required checks
- **AND** it records no friction event

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

### Requirement: A contribution integration job fails when the moved head lost its base

If the moved requirement integration branch head no longer contains the contribution's recorded base, the coordinator worker SHALL fail the integration job naming the lost base.

#### Scenario: The moved head lost the contribution base

- **WHEN** the requirement integration branch head moved and no longer contains the contribution's recorded base
- **THEN** the coordinator worker fails the integration job naming the lost base

### Requirement: A coordinator worker that lost its claim publishes nothing

A coordinator worker that lost its claim SHALL publish nothing.

#### Scenario: A worker loses its claim

- **WHEN** a coordinator worker loses its claim during an integration job
- **THEN** it publishes nothing

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
