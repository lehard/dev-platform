# Completion Lifecycle Specification

## Purpose

The completion lifecycle SHALL make semantic OpenSpec verification and archive part of the agent-owned definition of done for non-trivial work, so completed changes cannot silently remain active or depend on the human user remembering cleanup steps.

## Requirements

### Requirement: Archive requires semantic verification evidence

The supported platform archive entrypoint SHALL require a successful semantic OpenSpec verification receipt before archiving a non-trivial change. Agents SHALL prefer `/opsx:verify` when available; environments without that workflow MAY perform the documented equivalent review across completeness, correctness, and coherence.

#### Scenario: Verified change archives

- **GIVEN** all implementation tasks are complete
- **AND** `verification.md` records an exact standalone `OpenSpec-Verify: PASS`
- **AND** `verification.md` records a truthful non-empty `Verification-Method`
- **AND** strict OpenSpec validation succeeds
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** OpenSpec archives the change and global strict validation is run

#### Scenario: Missing or failed verification blocks archive

- **GIVEN** a completed change has no PASS verification receipt or no documented verification method
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** archive is refused without mutating the change

### Requirement: Agents own the whole lifecycle

Repository-wide agent instructions SHALL define semantic verify, archive, and configured publication as part of completing non-trivial OpenSpec work so the human user is not expected to remember or relay those steps.

#### Scenario: Agent reports completion

- **WHEN** an agent reports a non-trivial OpenSpec task as complete
- **THEN** project checks, semantic verification, archive, and configured publication have already been completed or any blocking exception is stated explicitly

### Requirement: Unfinished automatic delivery remains explicit completion work

For a platform-owned task configured for automatic PR delivery, an agent SHALL NOT report the task as fully delivered while its exact task PR is still open/pending or while GitHub has merged it but safe local reconciliation remains incomplete.

#### Scenario: Automatic PR is still waiting remotely

- **GIVEN** local validation and OpenSpec lifecycle work are complete
- **AND** the exact task PR is still open, checking, auto-merge armed, queued, or otherwise pending
- **WHEN** the agent reports task status
- **THEN** it describes delivery as unfinished/recoverable rather than complete
- **AND** identifies normal finish/status as the supported continuation path

#### Scenario: Remote PR merged but local reconciliation remains

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration/board/worktree reconciliation is still pending
- **WHEN** completion status runs
- **THEN** it reports remote delivery complete but local completion work pending
- **AND** does not ask the human to manually reconstruct publication history

#### Scenario: Publication reaches an actionable blocker

- **WHEN** required checks fail, GitHub authentication/state is unavailable, the exact head changed, or repository policy requires an explicit branch update
- **THEN** the agent may stop automatic delivery
- **AND** reports the specific blocker and preserved remote/local state
- **AND** does not misrepresent the task as successfully delivered

#### Scenario: Historical process evidence blocks finish after merge

- **GIVEN** GitHub confirms the exact task PR is merged and local main and Project reconciliation succeed
- **AND** linked process evidence cannot be resolved
- **WHEN** read-only status is requested
- **THEN** it reports the exact PR as merged, names the pending process-evidence obligation, and does not report full completion
- **AND** finish remains resumable without republishing the PR.

#### Scenario: Explicit disposition of unavailable historical evidence

- **GIVEN** an exact linked historical process Issue is demonstrably unavailable with a definitive 404
- **WHEN** an operator explicitly records a bounded reason through the supported disposition command
- **THEN** the managed source Issue stores an auditable, exact-reference disposition and the command verifies it by read-back
- **AND** status and finish may treat only that reference as disposed while retaining the confirmed merge fact.

#### Scenario: Temporary GitHub failure

- **WHEN** GitHub authentication, permission, transport, or evidence observation is unavailable without definitive proof of historical absence
- **THEN** status reports the relevant obligation as unknown or pending and finish remains resumable
- **AND** no disposition or full completion is inferred.

#### Scenario: Required cleanup remains

- **GIVEN** exact merge and other reconciliation obligations are fulfilled
- **AND** required cleanup is deferred
- **WHEN** read-only status is requested
- **THEN** it reports the cleanup obligation and does not report full completion unless the existing shared cleanup policy classifies it as a terminal warning.

### Requirement: Verification evidence is truthful about executed automated coverage

A semantic verification receipt SHALL distinguish automated commands that actually executed from scopes with no applicable automated checks or invalid empty platform-owned coverage. The existence of a PASS receipt SHALL NOT convert an empty required platform-owned check set into successful automated verification.

#### Scenario: Required platform-owned coverage is empty

- **GIVEN** an active non-trivial change requires platform-owned project checks for an affected scope
- **AND** the applicable check mapping resolves to zero executable commands
- **WHEN** semantic verification/archive is attempted
- **THEN** completion is blocked on check-contract configuration
- **AND** an `OpenSpec-Verify: PASS` receipt alone SHALL NOT override that blocker

#### Scenario: Automated checks executed successfully

- **WHEN** applicable required platform-owned commands execute successfully
- **THEN** verification evidence may cite those exact executed checks
- **AND** archive proceeds only if all other existing semantic/strict-validation requirements are satisfied

#### Scenario: Project-owned harness supplies product verification

- **GIVEN** `harness_mode=project`
- **WHEN** semantic verification uses repository-owned CI/evidence for product behavior
- **THEN** Dev Platform SHALL preserve that ownership boundary
- **AND** SHALL not claim platform-managed product commands ran when they did not

### Requirement: OpenSpec archive performs deterministic readiness preflight before expensive validation or evidence mutation

For a platform-owned archive, the lifecycle SHALL validate static semantic-receipt prerequisites and applicable committed task state before executing expensive selected checks or writing authoritative automated-check evidence.

#### Scenario: Verification receipt is statically incomplete

- **GIVEN** `verification.md` lacks a required PASS, method or automated-evidence marker
- **WHEN** archive is requested
- **THEN** the lifecycle fails before running selected checks
- **AND** it does not create or overwrite authoritative `automated-checks.json`

#### Scenario: No applicable committed diff exists

- **GIVEN** the change is only uncommitted/untracked or otherwise has no applicable committed diff against the selected base
- **WHEN** archive is requested
- **THEN** the lifecycle fails with an actionable readiness diagnostic before running selected checks
- **AND** stale not-applicable automated evidence is not written

#### Scenario: Archive is ready

- **GIVEN** static readiness and committed applicable state are valid
- **WHEN** archive is requested
- **THEN** relevant checks run
- **AND** successful evidence is validated
- **AND** the existing strict archive sequence continues normally

### Requirement: Deferred worktree cleanup is task-scoped by default

When terminal completion defers worktree housekeeping, the normal recovery path SHALL identify and clean only the exact deferred task/worktree record. A cleanup invocation that does not name a target SHALL NOT silently process all deferred records. Global cleanup MAY be supported only through an explicit `--all` mode with bounded candidate visibility before mutation.

#### Scenario: One task is cleaned while another remains deferred

- **GIVEN** two or more valid deferred worktree records exist
- **WHEN** cleanup is invoked for one exact task/worktree
- **THEN** only that record/worktree may be removed
- **AND** unrelated deferred worktrees remain unchanged.

#### Scenario: Global cleanup is requested

- **GIVEN** multiple deferred records exist
- **WHEN** the operator explicitly requests `--all`
- **THEN** the command exposes the eligible candidate set before mutation
- **AND** each candidate must independently pass the existing safety/identity checks
- **AND** ambiguous records fail closed rather than being guessed.

### Requirement: Post-task retrospective truthfully accounts for meaningful lifecycle failures

Before non-trivial completion, the post-task retrospective SHALL consider bounded meaningful non-success evidence already produced by the current managed lifecycle, together with recorded manual workaround, non-default override, known-recurrence and observed-drift evidence attributed to the task.

#### Scenario: Lifecycle failure exists but retrospective claims none

- **GIVEN** the current task produced a meaningful lifecycle failure
- **AND** no disposition or existing friction linkage accounts for it
- **WHEN** the executor attempts `checkpoint --result none`
- **THEN** completion rejects the checkpoint with an actionable retrospective instruction.

#### Scenario: Clean task has no meaningful friction

- **GIVEN** the retrospective reviews the current task and finds no meaningful unresolved/unrepresented lifecycle friction
- **WHEN** it records `none`
- **THEN** the checkpoint remains valid without additional ceremony.

#### Scenario: Recorded workaround is omitted

- **GIVEN** the task recorded a successful manual workaround event
- **WHEN** the executor attempts `checkpoint --result none` without a link or disposition
- **THEN** completion rejects the checkpoint naming the event.

#### Scenario: Expected failure is explained

- **GIVEN** a recorded signal describes an intentionally failing step
- **WHEN** the executor classifies it as expected-behavior and records `none`
- **THEN** the checkpoint is accepted without a new finding.

#### Scenario: Known recurrence cannot be dismissed

- **GIVEN** a recorded known-recurrence event for the task
- **WHEN** the executor classifies it with a dismissing disposition
- **THEN** the classification is refused and the event must be linked as a finding.

### Requirement: Material verification can incorporate independent review perspectives

For material managed changes, Dev Platform SHALL support distinct contract-fidelity and engineering-quality review evidence bound to the exact candidate under verification. When independent review is required, each perspective SHALL be produced by a reviewer process that the platform itself launches through a provider adapter, and the evidence SHALL identify the reviewed candidate by its task-content identity.

#### Scenario: Independent reviews are available
- **WHEN** a material change reaches semantic verification
- **THEN** spec-fidelity and engineering-quality findings are produced from separate platform-launched review processes
- **AND** the findings identify the candidate they reviewed
- **AND** they are consumed by the existing verification lifecycle
- **AND** the verification receipt cites the accepted review evidence

#### Scenario: Independent runtime is unavailable
- **WHEN** configured independent review cannot be executed
- **THEN** the limitation is reported truthfully with an actionable next step
- **AND** Dev Platform does not fabricate independent-review evidence

#### Scenario: Candidate changes after review preparation
- **GIVEN** independent review evidence was recorded for a candidate task-content identity
- **WHEN** any task-owned path other than lifecycle receipts, review evidence or archive-derived spec materialization changes
- **THEN** the existing evidence is not accepted for the new candidate
- **AND** a fresh independent review is required

#### Scenario: Archive bookkeeping or an irrelevant main merge follows review
- **GIVEN** independent review evidence was recorded for a candidate
- **WHEN** the change is archived or a clean main merge touches no task-owned path
- **THEN** the evidence remains valid for the unchanged task content

### Requirement: Material review findings require explicit disposition

A material independent-review finding SHALL be fixed through a fresh review of the changed candidate, explicitly rejected with rationale in a disposition record bound to the immutable reviewer report, or retained as a blocker before terminal semantic verification can claim PASS.

#### Scenario: Material finding remains unresolved
- **WHEN** semantic verification evaluates a material reviewer finding with no accepted disposition
- **THEN** `OpenSpec-Verify: PASS` is not recorded solely because deterministic tests passed
- **AND** archive and publication remain blocked

#### Scenario: Material finding is rejected with rationale
- **GIVEN** a material finding on the current candidate
- **WHEN** a rejection with a non-empty rationale is recorded against the exact report digest
- **THEN** the finding no longer blocks completion
- **AND** the reviewer report itself is unchanged

#### Scenario: Independent review is configured but unavailable
- **GIVEN** independent review is required for the material managed change
- **AND** either required perspective is unavailable
- **WHEN** archive readiness is evaluated
- **THEN** archive is blocked with the recorded limitation
- **AND** the lifecycle does not claim independent evidence was obtained

### Requirement: Observable completion blockers precede expensive validation

Dev Platform SHALL evaluate all safely observable read-only and cheap completion gates, including, for checkouts with private lineage enabled, the existing private Backlog reference guard over the current public candidate, before starting expensive validation.

#### Scenario: One or more blockers are already observable

- **WHEN** cleanliness, OpenSpec/provenance, terminal state, freshness, scope, checkpoint, privacy or integration preflight reports a blocker
- **THEN** expensive validation does not start
- **AND** independently observable blockers are returned in one bounded actionable report

#### Scenario: Preflight is clear

- **WHEN** every current cheap completion gate passes
- **THEN** the canonical required checks run with unchanged verification semantics
- **AND** publication still performs required race-sensitive rechecks

#### Scenario: Private reference in candidate evidence

- **GIVEN** private lineage is enabled
- **AND** a candidate verification artifact contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the candidate-file surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Private reference in new commit message

- **GIVEN** private lineage is enabled
- **AND** a new candidate commit message contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the commit-message surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Clean candidate passes preflight

- **GIVEN** private lineage is enabled
- **WHEN** no supported public candidate surface contains a direct private reference
- **THEN** completion proceeds to the existing required validation without another privacy mechanism
- **AND** publication still applies the fail-closed current-candidate guard

#### Scenario: Guard script missing with private lineage enabled

- **GIVEN** private lineage is enabled
- **AND** `scripts/check_private_backlog_refs.py` is absent
- **WHEN** completion preflight or publication runs
- **THEN** it reports a blocker naming the missing guard script
- **AND** nothing is published

#### Scenario: Private lineage not enabled

- **GIVEN** private lineage is not enabled
- **WHEN** completion preflight or publication runs
- **THEN** the guard does not run
- **AND** the run reports that the private-reference guard is not applicable by configuration

### Requirement: Synchronous completion exposes bounded progress

The existing synchronous completion command SHALL expose its current lifecycle stage and test-group progress without requiring background polling processes.

#### Scenario: Completion runs for an extended period

- **WHEN** validation or protected publication remains in progress
- **THEN** the caller receives bounded stage progress and terminal output
- **AND** no new daemon, job queue or workflow engine is required

### Requirement: Completion evidence freshness follows proven task-content identity

Managed completion evidence SHALL NOT become stale solely because HEAD changed through a platform-owned lifecycle transition when the platform can mechanically prove that the validated task-owned content is unchanged.

#### Scenario: Archive commit changes HEAD but not task content

- **GIVEN** a managed task has fresh retrospective or automated-check evidence for its completed task content
- **AND** the normal archive lifecycle creates a bookkeeping/spec-fold commit without changing that validated task content
- **WHEN** terminal completion evaluates evidence freshness
- **THEN** the platform MAY accept the evidence if content equivalence is mechanically proven
- **AND** does not require a duplicate review solely because the commit SHA changed.

#### Scenario: Task content changes after validation

- **GIVEN** managed completion evidence exists for an earlier task-content identity
- **WHEN** implementation or other task-owned content changes afterward
- **THEN** the prior evidence is stale
- **AND** completion requires the relevant fresh validation or retrospective before publication.

#### Scenario: Reconciliation changes the base ambiguously

- **GIVEN** origin/base advances after validation
- **AND** the platform cannot prove the new base is irrelevant to the validated task content
- **WHEN** completion reconciles the task
- **THEN** evidence reuse is refused
- **AND** the task follows the required revalidation path.

### Requirement: Armed exact-head publication resumes through status before republishing

After the platform has proven an existing PR for the exact task head and a durable auto-merge/remote merge intent, a subsequent completion invocation SHALL first observe and reconcile that existing publication state. It SHALL NOT rerun first-publication push/create logic or expensive validation solely because the prior bounded local wait ended before GitHub reported `MERGED`.

#### Scenario: Auto-merge is armed but merge is still pending

- **GIVEN** an exact-head PR exists and auto-merge intent is durably verified
- **AND** required checks or GitHub merge processing are still pending
- **WHEN** local bounded waiting ends or completion is invoked again
- **THEN** the platform reports a resumable nonterminal state with an actionable status path
- **AND** does not repeat full validation or republish the same head solely because merge is not yet terminal.

#### Scenario: Existing remote intent materially changed

- **GIVEN** a prior publication state exists
- **BUT** the observed PR head, required-check state, merge intent or base relationship no longer matches the proven resumable state
- **WHEN** completion resumes
- **THEN** the cheap resume path fails closed
- **AND** routes to explicit reconciliation/revalidation appropriate to the observed change.

### Requirement: Expected nonterminal publication states are bounded diagnostics

Expected resumable states in the protected-main completion flow SHALL be surfaced as structured actionable outcomes rather than uncaught Python subprocess tracebacks. This classification SHALL NOT convert an actual publication failure into success.

#### Scenario: Project publish reports accepted auto-merge without terminal merge

- **GIVEN** GitHub accepted the exact-head auto-merge intent
- **BUT** the local bounded wait ended before the PR reached `MERGED`
- **WHEN** the finish wrapper receives that nonterminal outcome
- **THEN** it reports the existing PR/status and next action without a raw traceback
- **AND** preserves nonterminal state so the caller does not mistake it for completed delivery.

### Requirement: Task checklist counting matches upstream OpenSpec markers

Every platform gate that decides whether a change's tasks are complete (lifecycle readiness and archive, completed-change hygiene, managed delivery provenance and shared Requirement integration) SHALL count tasks.md checklist items using the same task-line semantics as upstream OpenSpec apply progress: an item with a `-`, `*`, `+`, `N.` or `N)` list marker followed by a checkbox is a task, and a task is complete only when its checkbox content is `x` or `X`.

#### Scenario: Alternative list markers keep a change incomplete

- **GIVEN** an active change whose only unchecked tasks are written as `+ [ ] task`, `1. [ ] task` or `1) [ ] task`
- **WHEN** lifecycle readiness or completed-change hygiene is evaluated
- **THEN** the change is reported as having incomplete tasks

#### Scenario: Unknown checkbox content is incomplete

- **GIVEN** an active change whose only open task is `- [~] partial`
- **WHEN** lifecycle readiness or completed-change hygiene is evaluated
- **THEN** the task counts as incomplete and the change is not treated as complete

#### Scenario: Standard checkboxes keep their meaning

- **GIVEN** tasks written as `- [ ]`, `- [x]` and `- [X]`
- **WHEN** tasks are counted
- **THEN** `- [ ]` is incomplete and `- [x]` and `- [X]` are complete

### Requirement: Independent review runs in a proven fresh read-only context

A required independent review SHALL be accepted only when the platform observed the reviewer launch, launched it as a new non-resumable process whose runtime-enforced tool or sandbox surface grants no repository write capability, and a before/after content check of the task worktree and integration checkout shows no mutation.

#### Scenario: Codex or Claude Code session requests review
- **GIVEN** a managed task routed through Codex or Claude Code
- **WHEN** the lifecycle runs independent review
- **THEN** the same platform command launches a same-provider reviewer through that provider's read-only adapter
- **AND** each report records platform-observed launch evidence and the enforced read-only mechanism

#### Scenario: Reviewer mutates the workspace
- **WHEN** the post-launch content check detects any change in the task worktree or integration checkout
- **THEN** the report is recorded as unavailable with the mutated paths as its limitation
- **AND** the platform does not repair or clean the mutation

#### Scenario: Reviewer runtime cannot be launched
- **GIVEN** the reviewer binary is missing, exits unsuccessfully, times out, or returns malformed output
- **WHEN** independent review runs
- **THEN** an unavailable report names the actionable limitation
- **AND** completion stays blocked

#### Scenario: Report was not launched by the platform
- **WHEN** a required review is evaluated with a report lacking platform-observed launch evidence
- **THEN** the report does not satisfy the requirement

### Requirement: Required independent review is an automatic, resumable lifecycle gate

When independent review is required, the lifecycle SHALL run a missing or stale review automatically during archive preflight before expensive validation, SHALL re-validate current review evidence before publication, and SHALL expose the derived review state and next command through task status and Requirement advance from file-backed evidence without a separate state store.

#### Scenario: Archive runs without prior review
- **GIVEN** a required managed change with no current review evidence
- **WHEN** the archive helper runs
- **THEN** it launches the independent review before expensive validation
- **AND** continues only if the evidence validates, otherwise stops with findings and next commands

#### Scenario: Finish with stale review
- **GIVEN** the candidate changed after review
- **WHEN** finish is invoked
- **THEN** publication is refused before any remote mutation with an instruction to rerun review

#### Scenario: New session resumes
- **WHEN** a new Codex or Claude Code session reads task status or Requirement advance
- **THEN** it sees the review state and the exact next command

#### Scenario: Quick task
- **GIVEN** work without managed provenance
- **WHEN** it completes
- **THEN** no independent review is required

### Requirement: Reviewer runtime readiness is proven before review perspectives launch

Before launching any independent review perspective, the platform SHALL prove that the selected reviewer runtime is usable on the current host and account with the exact selected model, using one bounded probe launched through the same read-only adapter.

#### Scenario: Reviewer CLI is not logged in or cannot be executed
- **GIVEN** a required independent review
- **AND** the resolved reviewer binary is missing or its probe exits unsuccessfully
- **WHEN** the review runs
- **THEN** both perspectives are recorded as unavailable with a limitation naming the runtime's bounded error and the next step
- **AND** no review perspective is launched
- **AND** the candidate does not pass the review gate

#### Scenario: Selected model is not available to the current account
- **GIVEN** the probe with the exact selected model is rejected by the runtime
- **WHEN** readiness is evaluated
- **THEN** the limitation identifies the provider and model and directs the operator to change the binding or the account
- **AND** no unconfigured model or provider is tried

#### Scenario: Readiness is checked before implementation
- **WHEN** an agent runs the standalone readiness command after routing a managed task
- **THEN** it receives the resolved provider, model and binary with a ready or not-ready result and an actionable limitation
- **AND** no review evidence is written

### Requirement: Reviewer context excludes lifecycle-generated evidence

The candidate diff and prompt given to an independent reviewer SHALL cover exactly the task-owned content that the review task-content identity binds. Lifecycle receipts, review evidence and archive-derived spec materialization SHALL NOT be presented as candidate content, and the request SHALL record which lifecycle paths were excluded.

#### Scenario: Previous review evidence is committed in the candidate
- **GIVEN** the candidate branch contains committed review requests, reports, dispositions, automated-check evidence or a verification receipt
- **WHEN** a reviewer is launched
- **THEN** the reviewer diff omits those paths
- **AND** the prompt identifies them as lifecycle evidence that is not reviewed

#### Scenario: Unchanged final candidate completes with one review round
- **GIVEN** a required managed change whose independent review is ready
- **WHEN** archive, lifecycle evidence commits and finish follow without a task-owned content change
- **THEN** no additional review round is launched
- **AND** the existing review evidence satisfies the gate

#### Scenario: Task-owned content changes after review
- **WHEN** any path included in the review identity changes
- **THEN** the review evidence is stale and a fresh review is required

### Requirement: Independent review reports retain runtime-returned usage

When a reviewer runtime returns structured usage for a review launch, the platform SHALL retain it in that perspective's report as a bounded, runtime-local usage block with a value, source and status per field. It SHALL NOT retain prompts, responses or monetary cost. Unsupported, malformed or ambiguous fields SHALL be unknown, never zero. The block SHALL NOT affect review acceptance, freshness or disposition binding, and reports without it SHALL remain valid.

#### Scenario: Claude Code reviewer returns usage
- **GIVEN** a Claude Code reviewer launch returns a structured result with usage and duration fields
- **WHEN** the report is written
- **THEN** those fields are recorded as runtime-confirmed measurements under the Claude runtime

#### Scenario: Codex reviewer emits more than one completion
- **GIVEN** a Codex reviewer launch emits more than one completion usage event
- **WHEN** the report is written
- **THEN** its token fields are unknown rather than summed

#### Scenario: Historical report without usage
- **WHEN** a report written before this change is validated
- **THEN** it remains valid and its usage reads as unknown

### Requirement: Developer completion is a handoff at a verified PR

For a coordinator-managed candidate, developer completion SHALL end at a handoff: selected checks and semantic verification evidence for the still-active change, an exact-head PR, a developer friction checkpoint bound to the handoff task content, admission to the coordinator and release of the developer's writer claim. Handoff SHALL NOT wait for review, CI, main movement or merge.

#### Scenario: Developer finishes
- **WHEN** the developer runs finish for a coordinator-managed candidate
- **THEN** the PR exists, the candidate is review-pending and the developer session is free

### Requirement: Review and repair run as candidate jobs

Independent Review for a coordinator-managed candidate SHALL run as a job on the exact PR head with the existing fresh-context, read-only and two-perspective guarantees.

#### Scenario: Finding is repaired
- **GIVEN** review reports a fixable material finding
- **WHEN** the repair job changes task content
- **THEN** review runs again for the new identity

#### Scenario: Rejection proposed
- **WHEN** a worker proposes rejecting a material finding
- **THEN** the candidate waits for a human decision

#### Scenario: Provider limit during repair
- **GIVEN** a repair writer exits non-zero and the provider runtime then fails its readiness probe
- **WHEN** the worker records the outcome
- **THEN** the candidate is blocked-retryable with a provider-unavailable cause naming the limitation
- **AND** the repair round count is unchanged and the same round is offered again

#### Scenario: Repair fails with a usable runtime
- **GIVEN** a repair writer exits non-zero and the provider runtime passes its readiness probe
- **WHEN** the worker records the outcome
- **THEN** the candidate is blocked-escalation

#### Scenario: Provider unavailable repeatedly
- **WHEN** the same round is unavailable three consecutive attempts
- **THEN** the candidate remains blocked-retryable with unavailable evidence and no automatic job

#### Scenario: Unavailable runtime during review
- **WHEN** a review finds its provider runtime unavailable
- **THEN** the candidate is blocked-retryable and its record names the provider-unavailable cause and limitation

### Requirement: Gate evidence is reused for unchanged task content

Required-check, selected-check and review evidence SHALL be bound to the task-content identity it verified and SHALL be reused by later lifecycle steps when that identity is unchanged; changed or unprovable identity SHALL require the gate again.

#### Scenario: Bookkeeping commit after review
- **WHEN** only lifecycle evidence paths change
- **THEN** review and check evidence remain valid

#### Scenario: Clean main merge re-admitted with unchanged task content
- **GIVEN** a candidate whose independent review passed and which waits in a re-admissible state
- **WHEN** the developer merges the advanced `main` cleanly, with no task-path overlap, and re-admits the new head in the same PR
- **THEN** the review-pending record keeps the passed review rebound to the new identity
- **AND** the review job completes from the kept review without launching a reviewer

#### Scenario: Substantive conflict fix
- **WHEN** a re-admitted head or an integration repair changes task content, for example by resolving a conflict in a task path
- **THEN** the passed review is not kept and a new independent review runs for the new identity

### Requirement: Completed OpenSpec changes cannot remain active at integration

For non-trivial OpenSpec work, the platform SHALL treat a change with a completed task checklist as not admissible to integration and not mergeable until the change is archived. A coordinator-managed candidate MAY be published as a PR while its completed change is still active, until review and repair have finished.

#### Scenario: Completed active change blocks finish

- **GIVEN** an active OpenSpec change with one or more task checkboxes
- **AND** every task checkbox is complete
- **WHEN** the candidate is admitted to integration or merged, or a non-coordinator flow publishes it
- **THEN** the flow fails with an instruction to verify and archive the change

#### Scenario: In-progress active change is allowed

- **GIVEN** an active OpenSpec change with at least one incomplete task
- **WHEN** lifecycle hygiene is checked
- **THEN** the change is not treated as stale solely because it is active

### Requirement: Finalization follows review and repair

A coordinator-managed candidate SHALL be archived by a finalize job only after required checks and Independent Review pass for its current task-content identity, using that reused evidence.

#### Scenario: Review passes
- **WHEN** review and checks pass for the candidate identity
- **THEN** finalize archives the change and the candidate becomes ready

#### Scenario: Main advances between review repair and finalize
- **GIVEN** a candidate whose task content changed in a review repair and whose selected-checks gate is therefore not reusable
- **AND** other PRs advanced `main` after the review
- **WHEN** the finalize job re-establishes selected checks
- **THEN** the real selected checks run against the proven base of the reviewed content
- **AND** the candidate is not blocked because its head does not contain current `main`

#### Scenario: Re-established check fails
- **WHEN** a selected check fails under the proven-base contract
- **THEN** finalization does not archive and the candidate is escalated naming the failure

#### Scenario: Finalization does not actualize the base
- **GIVEN** `main` advanced after review
- **WHEN** finalization archives the candidate
- **THEN** any pushed finalization commit has the claimed head as its only parent and contains no merge of `main`

### Requirement: Archive hygiene exempts only its exact target

While `openspec_lifecycle.py archive <change>` runs the selected or protected validation checks, the OpenSpec lifecycle hygiene check SHALL exempt only that exact completed active archive target.

#### Scenario: Verified change passes its own archive checks
- **GIVEN** a completed, verified active change and the standard check mapping that includes the hygiene check
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** the hygiene check inside the archive validation passes for that change
- **AND** the change is archived and the ordinary hygiene check then passes

#### Scenario: Ordinary hygiene still blocks a completed active change
- **GIVEN** a completed change that is still active
- **WHEN** the ordinary hygiene check runs outside an archive validation
- **THEN** it fails naming the change

#### Scenario: A second completed active change blocks archive
- **GIVEN** two completed active changes
- **WHEN** one of them is archived
- **THEN** hygiene inside archive validation fails naming the other change and nothing is archived

#### Scenario: Invalid archive target fails closed
- **GIVEN** an archive target that is nonexistent, malformed, ambiguous or not completed
- **WHEN** hygiene runs in the archive context
- **THEN** it fails with an explicit error before any canonical state is changed
- **AND** the archive entry point applies this target validation in every mode, including `--finalize`, before any canonical state changes, while `--finalize` still runs no checks and needs no exemption

#### Scenario: Failed archive leaves no bypass
- **GIVEN** archive validation fails after the exemption was applied
- **WHEN** the ordinary hygiene check runs afterwards
- **THEN** it blocks the still-active completed change

#### Scenario: Context issued for another checkout is ignored
- **GIVEN** an archive context naming a different checkout root than the one being checked
- **WHEN** hygiene runs in the checked checkout
- **THEN** no exemption applies and no error is raised because of the context
- **AND** a completed active change in the checked checkout still blocks as in the ordinary check

#### Scenario: Malformed archive context fails explicitly
- **GIVEN** a context in which only one of the target and root variables is set, or either value is empty or whitespace-only, or the root is not an absolute path
- **WHEN** hygiene runs
- **THEN** it fails with an explicit error naming the offending variable and exempts nothing

#### Scenario: Matching context with a non-completed target fails explicitly
- **GIVEN** a context issued for the checked checkout whose target is not an existing completed active change
- **WHEN** hygiene runs
- **THEN** it fails with an explicit error naming the target rather than ignoring the context

### Requirement: Private-reference guard precedes child archive

For checkouts with private lineage enabled, the lifecycle SHALL run the existing private Backlog reference guard over the current public candidate before archive launches independent review, selected checks, writes automated evidence, or mutates OpenSpec. This SHALL apply to ordinary archive and coordinator finalization.

#### Scenario: Private reference in child proposal or design
- **GIVEN** a privacy-enabled child candidate has a supported direct private Issue reference in proposal.md or design.md
- **WHEN** archive is requested
- **THEN** archive fails before review, expensive checks, evidence writes and OpenSpec mutation
- **AND** diagnostic categories and opaque fingerprints guide repair without exposing private identifiers

#### Scenario: Private reference in inherited archived artifact
- **GIVEN** a privacy-enabled candidate contains a supported private Issue reference in an archived proposal or design
- **WHEN** archive is requested
- **THEN** the current candidate guard blocks before archive mutation

#### Scenario: Configured guard unavailable
- **GIVEN** private lineage is enabled and the repository guard is missing
- **WHEN** archive is requested
- **THEN** archive fails explicitly and does not substitute another scanner or proceed

#### Scenario: Clean or opted-out child
- **WHEN** the configured guard passes or private lineage is disabled
- **THEN** archive continues through its existing required verification gates

### Requirement: Private-reference guard precedes shared candidate full checks
For checkouts with private lineage enabled, the shared Requirement publisher SHALL run the existing current-candidate private-reference guard before local full validation and public publication for complete and draft candidates. The existing publication-time guard SHALL remain in place to catch changes after the early gate.

#### Scenario: Shared candidate contains private reference
- **GIVEN** a shared candidate contains a supported direct private Issue reference in an archived child artifact
- **WHEN** the shared publisher runs
- **THEN** it fails before full validation or public mutation with non-disclosing repair guidance

#### Scenario: Clean shared candidate
- **WHEN** the early guard passes for a complete shared candidate
- **THEN** the full mandatory checks still run and protected publication retains its privacy recheck

### Requirement: Lifecycle behavior is selected from the committed contract before source-only logic

Archive, publication and Requirement lifecycle entrypoints SHALL select portable or coordinator behavior from the committed `.dev-platform.toml` contract through one repository-owned selector before importing or evaluating any source-only coordinator logic.

#### Scenario: Downstream archive stays portable
- **WHEN** a downstream-contract checkout runs `openspec_lifecycle.py archive` for a completed verified change and the coordinator modules are unavailable
- **THEN** archive completes through the portable review and checks path without importing `pr_review_gate`, `publication_queue` or `lifecycle_workers`

#### Scenario: Downstream ignores coordinator candidacy
- **WHEN** a downstream-contract checkout has ambiguous or malformed managed provenance and the candidate question is asked
- **THEN** it answers not-a-coordinator-candidate without resolving provenance and without raising

#### Scenario: Unsupported source combination fails explicitly
- **WHEN** the source contract declares `scm_provider=gitlab`, `publish_mode=direct` or `harness_mode=project`
- **THEN** Requirement lifecycle selection raises an error naming the key and value and does not fall back to the legacy or portable path

#### Scenario: Supported source contract keeps coordinator behavior
- **WHEN** the source contract declares the supported combination
- **THEN** coordinator candidacy and publication support are evaluated exactly as before, and provenance errors still propagate

### Requirement: Archive rejects a new capability without an authored Purpose before mutation

Before review, selected checks, evidence writes or any OpenSpec mutation, the archive lifecycle SHALL reject a change whose delta creates a capability absent from the main specs unless that delta carries a non-empty, non-placeholder `## Purpose`. A placeholder SHALL include `TBD`, `TODO` or `FIXME` text and the sentence OpenSpec archive writes for a missing Purpose.

#### Scenario: New capability delta without Purpose
- **GIVEN** an active change whose delta creates capability `foo` with no `## Purpose`
- **WHEN** archive is requested
- **THEN** archive fails naming `specs/foo/spec.md` and the missing Purpose
- **AND** the change remains active, no main spec is written and no evidence is written

#### Scenario: Placeholder Purpose
- **WHEN** the new-capability delta Purpose is `TBD` or the archive placeholder sentence
- **THEN** archive fails before mutation with the same diagnostic

#### Scenario: Authored Purpose
- **GIVEN** the new-capability delta carries an authored `## Purpose`
- **WHEN** archive completes
- **THEN** the main spec Purpose is the authored text
- **AND** `openspec validate --all --strict` passes with no `TBD` in `openspec/specs`

### Requirement: Archive requires a committed package before expensive work

For a non-finalization archive, the lifecycle SHALL reject uncommitted or untracked authored files of the change (proposal, design, tasks, delta specs, verification receipt) and of the main specs before review, selected checks or evidence writes. Evidence files that the lifecycle helpers themselves generate SHALL NOT block. The diagnostic SHALL list the paths and the commit command.

#### Scenario: Uncommitted tasks or receipt
- **GIVEN** `tasks.md` or `verification.md` of the change has uncommitted edits
- **WHEN** archive is requested
- **THEN** archive fails naming those paths and the commit command
- **AND** no review, selected check or evidence write runs

### Requirement: Archive is rehearsed and recoverable

Before mutating the checkout, archive SHALL run `openspec archive` and `openspec validate --all --strict` on a disposable copy of the OpenSpec tree and SHALL stop with the failing items if either fails, leaving the checkout unchanged.

#### Scenario: Rehearsal fails
- **WHEN** rehearsal strict validation fails
- **THEN** archive exits non-zero with the failing items
- **AND** the change is still active and `openspec/specs` is unchanged

#### Scenario: Real post-validation fails
- **GIVEN** rehearsal passed but the real `validate --all --strict` fails
- **WHEN** archive handles the failure
- **THEN** the pre-archive OpenSpec tree is restored exactly
- **AND** the error names the failing items and states that the same command can be rerun

### Requirement: Archive failures report failing items

Archive, rehearsal, recovery and post-review finalization SHALL report OpenSpec failures by their failing items and diagnostics, not by a fixed-length tail of combined output. When no failing item line is recognisable, the whole output SHALL be reported.

#### Scenario: Finalization archive fails on validation
- **WHEN** finalization archive fails because strict validation rejects an item
- **THEN** the error contains that item and its reason
- **AND** progress or INFO lines alone are never the reported cause

### Requirement: Archive readiness is checked before review spend

Developer handoff, offering or launching a composition review, and composition finalization SHALL evaluate the same archive-content readiness predicate (all tasks complete; meaningful Purpose for each capability first created in contribution order) and SHALL stop with the named children and problems before spending a review round or archiving any child.

#### Scenario: Composition child has unticked tasks
- **GIVEN** a complete Requirement composition whose child has an unticked task
- **WHEN** the composition draft is published or a composition review job starts
- **THEN** no review is offered or launched
- **AND** the error names the child and its incomplete tasks

#### Scenario: Finalization meets a child without Purpose
- **WHEN** composition finalization starts and a child creates a capability without an authored Purpose
- **THEN** finalization fails before archiving any child, naming the child and delta

#### Scenario: Archive and hygiene stay compatible
- **WHEN** archive runs its validation subprocess for its exact completed target
- **THEN** lifecycle hygiene still exempts only that target

### Requirement: Finish reuses check evidence for unchanged task content

`finish` SHALL NOT execute the selected local checks again when recorded selected-check evidence proves that the task content being published passed the checks finish requires.

#### Scenario: Unchanged archived content

- **GIVEN** a managed task in a `portable` project whose archive executed the selected checks successfully and wrote version-2 evidence
- **AND** only the archive materialization and lifecycle evidence changed afterwards and main did not advance
- **WHEN** finish runs
- **THEN** finish prints that the archive evidence was reused
- **AND** the selected checks are executed once over archive and finish

#### Scenario: Clean rebase with an unchanged own diff

- **GIVEN** a managed or quick task whose recorded evidence passed
- **AND** main advanced without touching any task path and the task merged it cleanly
- **WHEN** finish runs in the `portable` or `coordinator` lifecycle
- **THEN** finish prints that the evidence was reused and does not execute the selected checks
- **AND** the coordinator developer handoff accepts the same evidence

#### Scenario: Task content changed after archive

- **WHEN** a source or test path of a managed task changes after its validation
- **THEN** the existing evidence gate stops publication, naming the stale evidence
- **AND** for a quick task finish prints that the task content differs and executes the required checks

#### Scenario: Base changed after archive

- **GIVEN** main advanced after archive by changing a path the task also changes and the task branch was reconciled with it
- **WHEN** finish runs
- **THEN** for a managed task the existing evidence gate stops publication, naming the stale evidence
- **AND** for a quick task finish prints that the evidence is not reusable because main changed a task path and executes the required checks

#### Scenario: Required selection not covered

- **WHEN** the selection finish requires now contains a command that the evidence does not show as executed successfully
- **THEN** finish prints the uncovered command as the reason and executes the required checks

#### Scenario: Quick task without recorded evidence

- **GIVEN** a quick task with no machine-local evidence record
- **WHEN** finish runs
- **THEN** finish prints that no quick-task evidence is recorded, executes the required checks and records evidence for the next finish

#### Scenario: Coordinator lifecycle unchanged

- **WHEN** finish runs for a coordinator-managed candidate
- **THEN** finish runs no checks and the developer handoff accepts the evidence by the same task-content proof as before

### Requirement: Declared generated files are not task-content identity

Task-content identity for review and for Requirement composition SHALL exclude files that the project declares generated in the committed check configuration at the main commit the candidate is based on (the merge base of the candidate head and the remote integration branch), never in the candidate. Every other task path SHALL remain in identity.

#### Scenario: Only the generated manifest is regenerated on an archived candidate
- **GIVEN** an archived candidate whose gates are bound to its task-content identity
- **WHEN** the publication queue merges main and regenerates only the declared generated manifest
- **THEN** the task-content identity is unchanged and the gates are kept

#### Scenario: An ordinary task path changes together with the manifest
- **GIVEN** an archived candidate
- **WHEN** a task path that is not declared generated changes together with the manifest
- **THEN** the task-content identity changes

#### Scenario: A candidate declares its own file generated
- **GIVEN** a candidate that adds a generated-file declaration absent from the main commit it is based on
- **WHEN** its task-content identity is computed
- **THEN** that file stays in identity

#### Scenario: A declared file has no required check
- **WHEN** a declaration's check is not in the protected full validation set
- **THEN** reading the declaration fails explicitly, naming the file

### Requirement: Managed selected-check runs refuse observable blockers before any command

`select_checks.py --execute` in a registered managed task checkout whose change is still active (`openspec/changes/<change>/` exists) SHALL refuse, before the affected-test precheck and before any selected command starts, when the run cannot produce usable handoff evidence: when no `--evidence` path is given, or when the managed change is not archive-ready (incomplete or missing `tasks.md` checkboxes, or a new-capability delta without an authored `## Purpose`).

#### Scenario: Managed run without evidence

- **GIVEN** a registered managed task checkout
- **WHEN** `select_checks.py --execute` runs without `--evidence`
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names `--evidence openspec/changes/<change>/automated-checks.json`

#### Scenario: Last task checkbox still open

- **GIVEN** a registered managed task whose `tasks.md` has an unchecked item
- **WHEN** `select_checks.py --execute --evidence ...` runs
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names the incomplete task count, so ticking the box happens before the only full run

#### Scenario: Archive-ready managed run proceeds

- **GIVEN** a registered managed task with evidence requested and all tasks complete
- **WHEN** `select_checks.py --execute --evidence ...` runs
- **THEN** the existing freshness and scope gates and the selected commands run unchanged

#### Scenario: Archived managed change keeps the existing path

- **GIVEN** a registered managed task whose change is already archived
- **WHEN** a completion command runs `select_checks.py --execute` without `--evidence`
- **THEN** neither refusal applies and validation runs as before

#### Scenario: Stale generated manifest

- **GIVEN** the generated platform manifest no longer matches the sources
- **WHEN** the platform's full validation set runs
- **THEN** the manifest check fails before `run_test_groups.py --all` starts

### Requirement: Selected checks run once per task content

An evidence-producing `select_checks.py --execute` (a managed run with `--evidence`, or a quick run with `--task-evidence`) SHALL refuse before the affected-test precheck and before any selected command starts when the evidence already recorded at that path is reusable for the current task content by the rule finish uses (`check_evidence_reuse`).

#### Scenario: Repeated managed run over unchanged content

- **GIVEN** a managed task whose `automated-checks.json` records a successful run covering the current required selection for unchanged task content
- **WHEN** `select_checks.py --execute --evidence openspec/changes/<change>/automated-checks.json` runs again
- **THEN** it exits non-zero before any selected command starts
- **AND** the message names the evidence and says archive and finish reuse it

#### Scenario: Repeated quick run over unchanged content

- **GIVEN** a quick task whose machine-local evidence is reusable for its current content
- **WHEN** `select_checks.py --execute --task-evidence` runs again
- **THEN** it exits non-zero before any selected command starts, naming the evidence

#### Scenario: Content changed since the evidence

- **WHEN** the task content differs from the content the existing evidence proves, or the evidence failed
- **THEN** the run prints why the evidence is not reusable and executes the selected checks

#### Scenario: Archive after a green evidence run

- **GIVEN** a managed task in a `portable` project whose `select_checks --execute --evidence` run succeeded and whose content did not change afterwards
- **WHEN** archive runs
- **THEN** archive prints that the evidence was reused and executes no selected command
- **AND** finish reuses the same evidence, so the checks run once over evidence, archive and finish

#### Scenario: Archive without reusable evidence

- **WHEN** archive runs with no evidence or with evidence that is not reusable
- **THEN** archive prints the reason and runs the selected checks with evidence as before

### Requirement: Private-reference guard precedes selected-check runs

For checkouts with private lineage enabled, `select_checks.py --execute` SHALL run the existing current-candidate private-reference guard before the affected-test precheck and before any selected command. A missing configured guard or a failed guard SHALL stop explicitly with the guard's non-disclosing diagnostics. Checkouts without private lineage enabled SHALL keep their existing behavior.

#### Scenario: Private reference before a full run

- **GIVEN** a privacy-enabled checkout whose candidate contains a supported private Issue reference
- **WHEN** `select_checks.py --execute` runs
- **THEN** it exits non-zero before any selected command starts with the guard's diagnostic

#### Scenario: Clean or opted-out checkout

- **WHEN** the guard passes or private lineage is disabled
- **THEN** the existing gates and selected commands run unchanged

### Requirement: Expensive lifecycle commands run one shared preflight of known conditions

`select_checks.py --execute` and `finish_task.py` (first submission, developer handoff and re-submission) SHALL, before the affected-test precheck, any selected command or any other expensive operation, evaluate one ordered registry of cheap conditions in `lifecycle_preflight.py`.

#### Scenario: Task without a board claim

- **GIVEN** the agent board capability is required and the task's worktree has no claim
- **WHEN** `select_checks.py --execute` runs
- **THEN** it exits non-zero within seconds, before any selected command starts
- **AND** the message names the missing claim and the `agent_board.py` command that registers it

#### Scenario: Project cheap gate fails

- **GIVEN** `preflight_commands` lists the writer-guard baseline test and a new direct file-creation site is not in the baseline
- **WHEN** `select_checks.py --execute` or `finish_task.py` runs
- **THEN** it exits non-zero before the full validation set starts, naming the command and the unregistered site

#### Scenario: Task behind a conflicting main

- **GIVEN** main moved so the task is not behind-mergeable
- **WHEN** a lifecycle command runs the preflight
- **THEN** it refuses before validation with the conflicting files and the `reconcile` command
- **AND** a task that is behind-mergeable passes as it does for the gate today

#### Scenario: Several refusals at once

- **WHEN** two conditions are violated
- **THEN** one error names both, each with its repair command

#### Scenario: Preflight output

- **WHEN** every condition passes or is not applicable
- **THEN** the command prints each condition id with its result and the validation proceeds unchanged

#### Scenario: Not applicable is explicit

- **GIVEN** a disposable checkout declared with `--scope-gate not-applicable`, or a project without `preflight_commands`
- **WHEN** the preflight runs
- **THEN** the affected condition is printed as `not-applicable` with the configuration fact, never silently skipped

#### Scenario: Gate and preflight agree

- **WHEN** the same state is evaluated by a gate function and by its preflight condition
- **THEN** both give the same verdict and the same violated-condition message

#### Scenario: Committed evidence bound to an old base

- **GIVEN** a managed task whose committed selected-check evidence is a publication gate and whose content proof no longer matches after main moved under the task
- **WHEN** `finish_task.py` runs the preflight
- **THEN** it refuses before validation naming the evidence path and the exact `select_checks.py --base origin/main --execute --evidence <path>` refresh command

### Requirement: Reconcile reports committed evidence a base move invalidated

After `reconcile` merges authoritative main into a managed task, it SHALL evaluate the task's committed selected-check evidence with the content-proof comparison the evidence gate uses.

#### Scenario: Main changed a task path

- **GIVEN** an archived managed change with committed evidence and a main commit that changed a path of the task
- **WHEN** `reconcile` merges that main
- **THEN** it exits non-zero after the merge with the evidence path and the refresh command

#### Scenario: Main changed only unrelated paths

- **GIVEN** committed evidence and a main commit touching no task path
- **WHEN** `reconcile` merges that main
- **THEN** it succeeds and reports no stale evidence

#### Scenario: Active change in the portable lifecycle

- **GIVEN** an active managed change outside the coordinator lifecycle
- **WHEN** `reconcile` or the preflight evaluates its evidence
- **THEN** the condition is not applicable because archive revalidates non-reusable evidence

### Requirement: A developer does not archive a coordinator candidate

Under the coordinator lifecycle a developer archive of a coordinator-managed candidate SHALL be refused before any review, check or OpenSpec change, naming the handoff command, because the candidate is handed off with its change still active and the coordinator's finalize archives it. The finalize archive SHALL be unchanged.

#### Scenario: Developer archives a coordinator candidate

- **GIVEN** the coordinator lifecycle with the publication queue enabled and an active coordinator-managed candidate
- **WHEN** the developer runs `openspec_lifecycle.py archive <change>` without `--finalize`
- **THEN** it fails before any work, naming the handoff command
- **AND** the change stays active

#### Scenario: Coordinator finalize archives

- **WHEN** finalize runs `openspec_lifecycle.py archive <change> --finalize` for a reviewed candidate
- **THEN** the archive proceeds as before

### Requirement: Completion status derives unfinished automatic delivery from Git and GitHub state

Completion/doctor status SHALL derive the condition that a platform-owned task configured for automatic PR delivery has its exact task PR still open/pending, or merged by GitHub while safe local reconciliation remains incomplete, from current Git/GitHub state and identify the supported next operation without requiring the human user to remember a Git hand-off.

#### Scenario: Unfinished automatic delivery is derived and the next operation named

- **GIVEN** a platform-owned task configured for automatic PR delivery whose exact task PR is open/pending, or merged with safe local reconciliation incomplete
- **WHEN** completion/doctor status runs
- **THEN** it derives that condition from current Git/GitHub state
- **AND** it identifies the supported next operation without requiring the human user to remember a Git hand-off

### Requirement: Managed task status distinguishes exact PR merge from terminal completion

For a managed task, read-only status SHALL distinguish confirmed exact PR merge from full terminal completion.

#### Scenario: Merged managed task is not yet terminally complete

- **GIVEN** a managed task whose exact PR merge is confirmed
- **WHEN** read-only status is requested
- **THEN** it reports the confirmed exact PR merge separately from full terminal completion

### Requirement: Full completion requires fulfilled post-merge obligations

Full completion SHALL be reported only when mandatory post-merge local, Project, linked process-evidence, and required cleanup obligations are fulfilled or have an explicitly supported terminal disposition. Status SHALL derive full completion from existing authoritative lifecycle and obligation evidence without a second terminal state ledger.

#### Scenario: Post-merge obligations decide full completion

- **WHEN** status decides whether to report full completion
- **THEN** full completion is reported only when mandatory post-merge local, Project, linked process-evidence, and required cleanup obligations are fulfilled or have an explicitly supported terminal disposition
- **AND** status derives this from existing authoritative lifecycle and obligation evidence without a second terminal state ledger

### Requirement: A failed post-merge obligation does not turn the merge into failure

A failed or unknown post-merge obligation SHALL be reported as pending or blocking without changing the confirmed merge fact to failure.

#### Scenario: Post-merge obligation fails or is unknown

- **GIVEN** a confirmed merge
- **WHEN** a post-merge obligation is failed or unknown
- **THEN** the obligation is reported as pending or blocking
- **AND** the confirmed merge fact is not changed to failure

### Requirement: A none retrospective checkpoint requires every mandatory signal to be disposed

A `none` checkpoint SHALL NOT be accepted while any mandatory signal of the post-task retrospective (bounded meaningful non-success evidence already produced by the current managed lifecycle, or recorded manual workaround, non-default override, known-recurrence or observed-drift evidence attributed to the task) remains without an explicit disposition as resolved-in-task, expected-behavior, already represented by durable friction evidence, or newly recorded.

#### Scenario: Undisposed mandatory signal blocks a none checkpoint

- **GIVEN** a mandatory post-task retrospective signal without an explicit disposition
- **WHEN** a `none` checkpoint is submitted
- **THEN** the checkpoint is not accepted
- **AND** an accepted disposition is resolved-in-task, expected-behavior, already represented by durable friction evidence, or newly recorded

### Requirement: A new occurrence of an open problem is preserved as evidence

A new occurrence of an already open problem SHALL be preserved as recorded evidence and SHALL NOT be dismissed by disposition.

#### Scenario: Already open problem occurs again

- **WHEN** a new occurrence of an already open problem is observed
- **THEN** it is preserved as recorded evidence
- **AND** it is not dismissed by disposition

### Requirement: The private reference guard runs again at publication time

For checkouts with private lineage enabled the existing private Backlog reference guard SHALL still run at publication time to cover changes after preflight.

#### Scenario: Changes after preflight are guarded at publication

- **GIVEN** a checkout with private lineage enabled
- **WHEN** publication runs after preflight
- **THEN** the existing private Backlog reference guard runs again to cover changes after preflight

### Requirement: A missing private reference guard script blocks completion

For checkouts with private lineage enabled a missing private Backlog reference guard script SHALL be a blocker naming the missing guard script.

#### Scenario: Guard script is missing

- **GIVEN** a checkout with private lineage enabled
- **WHEN** the private Backlog reference guard script is missing
- **THEN** it is a blocker naming the missing guard script

### Requirement: The private reference guard is not applicable without private lineage

For checkouts without private lineage enabled the private Backlog reference guard SHALL NOT run and completion and publication SHALL report that the guard is not applicable by configuration.

#### Scenario: Checkout without private lineage

- **GIVEN** a checkout without private lineage enabled
- **WHEN** completion or publication runs
- **THEN** the private Backlog reference guard does not run
- **AND** completion and publication report that it is not applicable by configuration

### Requirement: Reused completion evidence keeps its original commit provenance

Managed completion evidence SHALL retain its original commit provenance.

#### Scenario: Evidence reused after a lifecycle transition

- **WHEN** managed completion evidence is reused after HEAD changed through a platform-owned lifecycle transition
- **THEN** the evidence retains its original commit provenance

### Requirement: Completion evidence reuse requires a content-equivalence proof

Reuse of managed completion evidence SHALL require a deterministic auditable content-equivalence proof.

#### Scenario: Evidence reuse is proven

- **WHEN** managed completion evidence is reused
- **THEN** the reuse is backed by a deterministic auditable content-equivalence proof

### Requirement: Changed or unprovable task content makes completion evidence stale

If task-owned content changed or equivalence cannot be proven, the relevant managed completion evidence SHALL be treated as stale and the required validation or retrospective SHALL run again.

#### Scenario: Task-owned content changed

- **WHEN** task-owned content changed or equivalence cannot be proven
- **THEN** the relevant evidence is treated as stale
- **AND** the required validation or retrospective runs again

### Requirement: Unrecognized checkbox content counts as an incomplete task

When a platform gate counts tasks.md checklist items, any checkbox content other than `x` or `X` SHALL count as incomplete.

#### Scenario: Task checkbox holds other content

- **WHEN** a platform gate counts a tasks.md task whose checkbox content is neither `x` nor `X`
- **THEN** the task counts as incomplete

### Requirement: The reviewer provider follows the task route by default

The reviewer provider SHALL default to the current task route's provider; cross-provider review SHALL happen only by explicit configuration.

#### Scenario: Reviewer provider without explicit configuration

- **WHEN** no cross-provider review is explicitly configured
- **THEN** the reviewer provider is the current task route's provider

### Requirement: The canonical review contract is model-neutral

The canonical review contract SHALL NOT name a concrete model or provider API.

#### Scenario: Review contract is read

- **WHEN** the canonical review contract is inspected
- **THEN** it names no concrete model or provider API

### Requirement: Independent review applies only to managed changes in enabling repositories

Independent review SHALL be required only for changes with managed provenance in a repository that enables independent review; quick tasks without managed provenance SHALL NOT receive review ceremony.

#### Scenario: Quick task without managed provenance

- **WHEN** a quick task without managed provenance completes
- **THEN** it receives no review ceremony

#### Scenario: Managed change in an enabling repository

- **WHEN** a change with managed provenance completes in a repository that enables independent review
- **THEN** independent review is required

### Requirement: Unproven reviewer readiness records the review as unavailable

When reviewer runtime readiness cannot be proven, the platform SHALL record the review as unavailable with a concrete actionable limitation and SHALL NOT launch the independent review perspectives.

#### Scenario: Readiness probe fails

- **WHEN** reviewer runtime readiness cannot be proven
- **THEN** the review is recorded as unavailable with a concrete actionable limitation
- **AND** no independent review perspective is launched

### Requirement: Reviewer readiness is available as a standalone command

The platform SHALL expose the reviewer runtime readiness check as a standalone command.

#### Scenario: Operator checks reviewer readiness

- **WHEN** an operator runs the standalone readiness command
- **THEN** the same reviewer runtime readiness check runs

### Requirement: Reviewer provider substitution follows only a configured ordered list

The platform SHALL NOT substitute another reviewer model or provider unless configuration declares an ordered provider list; then each configured provider is probed in order, the review records the requested provider, the executed provider and the fallback reason, and when every configured provider is unavailable the candidate becomes blocked-retryable and is retried automatically rather than escalated to a human.

#### Scenario: No ordered provider list

- **WHEN** the selected reviewer runtime is unavailable and no ordered provider list is configured
- **THEN** no other model or provider is substituted

#### Scenario: Ordered provider list configured

- **GIVEN** configuration declares an ordered provider list
- **WHEN** reviewer readiness is probed
- **THEN** each configured provider is probed in order
- **AND** the review records the requested provider, the executed provider and the fallback reason
- **AND** when every configured provider is unavailable the candidate becomes blocked-retryable and is retried automatically rather than escalated to a human

### Requirement: A fixable review finding produces a bounded repair job

A fixable finding of Independent Review for a coordinator-managed candidate SHALL produce a bounded repair job executed without the original developer.

#### Scenario: Review reports a fixable finding

- **WHEN** Independent Review of a coordinator-managed candidate reports a fixable finding
- **THEN** a bounded repair job is produced
- **AND** it is executed without the original developer

### Requirement: Changed candidate task content makes review stale

For a coordinator-managed candidate, changed task content SHALL make review stale.

#### Scenario: Candidate task content changes

- **WHEN** the task content of a coordinator-managed candidate changes
- **THEN** its review becomes stale

### Requirement: Rejected material findings or exhausted repair escalate the candidate

For a coordinator-managed candidate, a proposal to reject a material finding, or exhausted repair rounds, SHALL move the candidate to blocked-escalation.

#### Scenario: Material finding rejection is proposed

- **WHEN** a proposal to reject a material finding is made, or repair rounds are exhausted
- **THEN** the candidate moves to blocked-escalation

### Requirement: Candidate jobs retain the originating reviewer provider

Review and repair jobs SHALL retain the originating task's resolved reviewer provider or explicitly configured ordered providers across repair and retry until an operator re-offers the job on other supported providers. Workers SHALL NOT substitute their local route.

#### Scenario: Worker with a different local route runs a job

- **WHEN** a worker runs a review or repair job across repair or retry
- **THEN** the job uses the originating task's resolved reviewer provider or explicitly configured ordered providers
- **AND** the worker does not substitute its local route until an operator re-offers the job on other supported providers

### Requirement: An unavailable provider runtime leaves the candidate blocked-retryable

An unavailable provider runtime (login, usage limit or failure to start) during review or repair SHALL leave the candidate blocked-retryable with a named provider-unavailable cause and SHALL NOT escalate it or spend a repair round.

#### Scenario: Provider runtime is unavailable during a job

- **WHEN** the provider runtime is unavailable (login, usage limit or failure to start) during review or repair
- **THEN** the candidate is blocked-retryable with a named provider-unavailable cause
- **AND** it is not escalated and no repair round is spent

### Requirement: Unavailable review or repair retries are bounded

Unavailable review or repair SHALL retry the same round at most three consecutive attempts, then remain blocked-retryable with unavailable evidence and no automatic job until an operator resumes it.

#### Scenario: Third consecutive unavailable attempt

- **WHEN** review or repair has been unavailable for three consecutive attempts of the same round
- **THEN** it remains blocked-retryable with unavailable evidence
- **AND** no automatic job runs until an operator resumes it

### Requirement: A failing repair writer with a usable runtime escalates

A repair writer that fails while its runtime is usable SHALL still be an operational escalation.

#### Scenario: Repair writer fails

- **WHEN** a repair writer fails while its runtime is usable
- **THEN** the failure is an operational escalation

### Requirement: Publication leaves review and repair retry states untouched

Publication SHALL leave review-owned and repair-owned retry states untouched.

#### Scenario: Publication meets a retry state

- **WHEN** publication runs while a review-owned or repair-owned retry state exists
- **THEN** the retry state is left untouched

### Requirement: Job workers confirm ownership before side effects

Workers of review and repair jobs SHALL confirm unexpired ownership of the exact job and originating head immediately before push and candidate advancement; lost ownership SHALL abandon without further side effects.

#### Scenario: Ownership lost before push

- **WHEN** a worker is about to push or advance the candidate
- **THEN** it confirms unexpired ownership of the exact job and originating head
- **AND** when ownership is lost it abandons without further side effects

### Requirement: Repair rejects lifecycle evidence paths

Repair SHALL reject lifecycle evidence paths at any depth, including evidence directories.

#### Scenario: Repair touches an evidence path

- **WHEN** a repair change touches a lifecycle evidence path at any depth, including an evidence directory
- **THEN** repair rejects it

### Requirement: A published trusted repair completion recovers without rerunning the writer

A trusted repair completion published before interrupted advancement SHALL recover on the next run without rerunning the repair writer.

#### Scenario: Advancement interrupted after repair publication

- **GIVEN** a trusted repair completion was published before advancement was interrupted
- **WHEN** the next run starts
- **THEN** it recovers the completion without rerunning the repair writer

### Requirement: Integration events do not invalidate a passed review

A clean merge of `main`, a `main` advance, lifecycle archiving and a coordinator update SHALL NOT by themselves invalidate a passed independent review.

#### Scenario: Main advances after review passed

- **GIVEN** a passed independent review
- **WHEN** a clean merge of `main`, a `main` advance, lifecycle archiving or a coordinator update happens
- **THEN** that event by itself does not invalidate the passed review

### Requirement: Re-admission keeps gates still bound to the new task content

When a developer re-admits a descendant head in place of an admitted head through queue supersession, the new review-pending record SHALL keep every recorded gate that is still provably bound to the new task-content identity, except required checks and the gates the new handoff supplies. A kept passed review SHALL complete the review job without launching a reviewer.

#### Scenario: Descendant head re-admitted through queue supersession

- **WHEN** a developer re-admits a descendant head in place of an admitted head through queue supersession
- **THEN** the new review-pending record keeps every recorded gate still provably bound to the new task-content identity, except required checks and the gates the new handoff supplies
- **AND** a kept passed review completes the review job without launching a reviewer

### Requirement: Re-admission carries no failed review and keeps finding refusals

Re-admission SHALL NOT carry a failed review, and SHALL NOT relax any refusal of re-admission over finding-level escalations or material findings.

#### Scenario: Re-admission after a failed review

- **WHEN** a head is re-admitted
- **THEN** a failed review is not carried
- **AND** any refusal of re-admission over finding-level escalations or material findings still applies

### Requirement: Finalization preserves task-content identity

Finalization of a coordinator-managed candidate SHALL NOT change task-content identity; a later task-content change SHALL return the candidate to review and finalization.

#### Scenario: Task content changes after finalization

- **WHEN** a finalize job runs
- **THEN** it does not change task-content identity
- **AND** a later task-content change returns the candidate to review and finalization

### Requirement: Finalization re-establishes selected checks on the reviewed base

When selected checks must be re-established during finalization, the finalize job SHALL run the real selected checks against the proven base of the reviewed task content. That base is the task-content base of the identity proven equivalent to the candidate's recorded identity, and the checks SHALL use the bounded coordinator-finalization freshness contract rather than require the head to contain current `main`.

#### Scenario: Selected checks re-established during finalization

- **WHEN** selected checks must be re-established during finalization
- **THEN** the finalize job runs the real selected checks against the task-content base of the identity proven equivalent to the candidate's recorded identity
- **AND** the checks use the bounded coordinator-finalization freshness contract rather than require the head to contain current `main`

### Requirement: Finalization check evidence records its freshness contract and base

The harness-executed evidence of selected checks re-established during finalization SHALL record the bounded coordinator-finalization freshness contract and the proven base.

#### Scenario: Finalization records selected-check evidence

- **WHEN** the finalize job records harness-executed selected-check evidence
- **THEN** the evidence records the bounded coordinator-finalization freshness contract and the proven base

### Requirement: Finalization only fast-forwards the claimed head

Finalization SHALL NOT fetch or merge `main`, and the only push of finalization SHALL be a fast-forward of the claimed head with the archive move.

#### Scenario: Finalize job pushes

- **WHEN** a finalize job runs
- **THEN** it does not fetch or merge `main`
- **AND** its only push is a fast-forward of the claimed head with the archive move

### Requirement: A failing finalization selected check escalates the candidate

During finalization, a failing selected check SHALL still escalate the candidate.

#### Scenario: Selected check fails in finalization

- **WHEN** a selected check fails during finalization
- **THEN** the candidate is escalated

### Requirement: An unbound verification receipt still needs the developer handoff

During finalization, an unbound semantic-verification receipt SHALL still require the developer's handoff.

#### Scenario: Semantic-verification receipt is unbound

- **WHEN** finalization meets an unbound semantic-verification receipt
- **THEN** the developer's handoff is still required

### Requirement: The archive hygiene exemption is scoped to the archive validation subprocess

The archive target exemption from the OpenSpec lifecycle hygiene check SHALL exist only for the validation subprocess of the `openspec_lifecycle.py archive <change>` invocation that issued it, and SHALL NOT alter ordinary hygiene outside that context.

#### Scenario: Hygiene outside archive validation

- **WHEN** the OpenSpec lifecycle hygiene check runs outside the validation subprocess of an archive invocation
- **THEN** no archive target exemption applies and ordinary hygiene is unchanged

### Requirement: The archive hygiene exemption fails closed on an invalid target

The archive target exemption from the OpenSpec lifecycle hygiene check SHALL fail closed when the target is missing, malformed, absent or not a completed active change.

#### Scenario: Archive target is not a completed active change

- **WHEN** the exempted target is missing, malformed, absent or not a completed active change
- **THEN** the exemption fails closed

### Requirement: Lifecycle hygiene stays a mandatory check

The OpenSpec lifecycle hygiene check SHALL remain in the mandatory check groups.

#### Scenario: Mandatory check groups are listed

- **WHEN** the mandatory check groups are resolved
- **THEN** they include the OpenSpec lifecycle hygiene check

### Requirement: The archive hygiene exemption is bound to its checkout

The archive target exemption from the OpenSpec lifecycle hygiene check SHALL be bound to the checkout that archive issued it for: a context issued for a different checkout SHALL be ignored and hygiene SHALL run as the ordinary check, which is scoping and not a masked failure.

#### Scenario: Exemption context from another checkout

- **WHEN** the hygiene check sees an exemption context issued for a different checkout
- **THEN** the context is ignored
- **AND** hygiene runs as the ordinary check

### Requirement: A malformed archive hygiene exemption context fails explicitly

For the archive target exemption from the OpenSpec lifecycle hygiene check, a half-set context, an empty value of either context variable, or a non-absolute checkout root SHALL fail explicitly naming the variable.

#### Scenario: Exemption context is half-set

- **WHEN** the exemption context is half-set, either context variable is empty, or the checkout root is not absolute
- **THEN** the check fails explicitly naming the variable

### Requirement: A missing or failed private reference guard stops archive

For checkouts with private lineage enabled, a missing configured private Backlog reference guard or failed private Backlog reference guard SHALL stop explicitly with actionable diagnostics.

#### Scenario: Guard is missing or fails before archive

- **GIVEN** a checkout with private lineage enabled
- **WHEN** the configured private Backlog reference guard is missing or fails
- **THEN** the lifecycle stops explicitly with actionable diagnostics

### Requirement: Archive without private lineage keeps its behavior

Checkouts without private lineage enabled SHALL retain their existing archive behavior.

#### Scenario: Checkout without private lineage archives

- **GIVEN** a checkout without private lineage enabled
- **WHEN** archive runs
- **THEN** its existing archive behavior is retained

### Requirement: A downstream contract selects portable lifecycle behavior

A downstream `.dev-platform.toml` contract (`platform_version` other than `source`) SHALL select portable lifecycle behavior.

#### Scenario: Downstream contract

- **GIVEN** a committed `.dev-platform.toml` contract whose `platform_version` is other than `source`
- **WHEN** a lifecycle entrypoint selects its behavior
- **THEN** portable behavior is selected

### Requirement: The source contract selects coordinator behavior only for the GitHub PR platform mode

The source `.dev-platform.toml` contract SHALL select coordinator lifecycle behavior only for `harness_mode=platform`, `publish_mode=pr` and `scm_provider=github`; any other source combination, or a missing `platform_version`, SHALL fail with a named error and SHALL NOT switch to another path.

#### Scenario: Source contract with the platform GitHub PR combination

- **GIVEN** the source contract with `harness_mode=platform`, `publish_mode=pr` and `scm_provider=github`
- **WHEN** a lifecycle entrypoint selects its behavior
- **THEN** coordinator behavior is selected

#### Scenario: Other source combination or missing platform_version

- **WHEN** the source contract has any other combination, or `platform_version` is missing
- **THEN** selection fails with a named error
- **AND** it does not switch to another path

### Requirement: A missing new-capability Purpose diagnostic names the file and section

The archive diagnostic for a new-capability delta without a non-empty, non-placeholder `## Purpose` SHALL name the delta file and the missing section.

#### Scenario: New capability delta lacks a Purpose

- **WHEN** archive rejects a new-capability delta without an authored `## Purpose`
- **THEN** the diagnostic names the delta file and the missing section

### Requirement: An authored new-capability Purpose reaches the main spec

When a delta that creates a capability absent from the main specs carries an authored Purpose, archive SHALL write the authored Purpose to the new main spec and the archived tree SHALL pass `openspec validate --all --strict` without manual edits.

#### Scenario: New capability delta carries an authored Purpose

- **WHEN** archive runs on a new-capability delta with an authored Purpose
- **THEN** the Purpose is written to the new main spec
- **AND** the archived tree passes `openspec validate --all --strict` without manual edits

### Requirement: A failed real archive validation restores the OpenSpec tree

If the real post-archive strict validation still fails, the lifecycle SHALL restore the exact OpenSpec tree captured immediately before the real archive, SHALL exit non-zero with the failing items, and SHALL allow the same archive command to be rerun after the fix without manual spec edits.

#### Scenario: Real post-archive validation fails

- **WHEN** the real post-archive strict validation fails
- **THEN** the exact OpenSpec tree captured immediately before the real archive is restored
- **AND** the lifecycle exits non-zero with the failing items
- **AND** the same archive command can be rerun after the fix without manual spec edits

### Requirement: One rule decides finish check evidence reuse

One `finish` evidence reuse rule SHALL decide for managed and quick tasks in the `portable` and `coordinator` lifecycles: the evidence outcome is success, the current required selection is ready and every one of its commands was executed successfully by the evidence, and the evidence's task-content proof is equivalent to the current one — equal task-content digest and scope, and when the bases differ, the recorded base is an ancestor of the current base and no task path changed between them.

#### Scenario: Evidence satisfies the reuse rule

- **WHEN** the evidence outcome is success, the current required selection is ready, every one of its commands was executed successfully by the evidence, and the task-content proofs are equivalent
- **THEN** the evidence proves the task content for managed and quick tasks in both lifecycles

#### Scenario: Bases differ

- **WHEN** the recorded base differs from the current base
- **THEN** the proofs are equivalent only when task-content digest and scope are equal, the recorded base is an ancestor of the current base and no task path changed between them

### Requirement: A main merge without task path changes keeps check evidence reusable

A clean merge or rebase on an advanced `main` that changed no task path SHALL keep recorded selected-check evidence reusable.

#### Scenario: Clean merge of advanced main

- **WHEN** a clean merge or rebase on an advanced `main` changed no task path
- **THEN** the recorded selected-check evidence stays reusable

### Requirement: Check evidence reuse keeps the publication freshness gate

Reuse of recorded selected-check evidence SHALL NOT relax the freshness gate that decides whether a head may publish.

#### Scenario: Reused evidence on a stale head

- **WHEN** finish reuses selected-check evidence
- **THEN** the freshness gate that decides whether a head may publish still applies unchanged

### Requirement: Finish reports check evidence reuse

Finish SHALL print whether the selected-check evidence was reused or why it was not, and SHALL run the required validation when reuse is not proven.

#### Scenario: Reuse not proven

- **WHEN** finish evaluates selected-check evidence
- **THEN** it prints whether the evidence was reused or why it was not
- **AND** it runs the required validation when reuse is not proven

### Requirement: Managed task check evidence is the change's automated checks file

A managed task's selected-check evidence SHALL be its change's `automated-checks.json`; unreadable, failed or mismatched managed evidence SHALL continue to stop publication.

#### Scenario: Managed evidence is unreadable

- **WHEN** a managed task's `automated-checks.json` is unreadable, failed or mismatched
- **THEN** publication stops

### Requirement: Quick task check evidence is recorded machine-locally

A quick task's selected-check evidence SHALL be recorded machine-locally in its worktree's git directory on explicit request, never in the tree, with a quick-task content proof of its own diff from the merge base with the remote main excluding declared generated files.

#### Scenario: Quick task evidence is requested

- **WHEN** quick-task selected-check evidence is explicitly requested
- **THEN** it is recorded in the worktree's git directory and never in the tree
- **AND** it carries a quick-task content proof of its own diff from the merge base with the remote main excluding declared generated files

### Requirement: Finish requests quick task check evidence

Finish SHALL request quick-task selected-check evidence when it runs a quick task's checks, and an absent quick-task evidence record SHALL be a named reason to run the checks.

#### Scenario: Quick task without an evidence record

- **WHEN** finish runs a quick task's checks
- **THEN** it requests the quick-task evidence record
- **AND** an absent record is reported as a named reason to run the checks

### Requirement: Required CI remains the merge gate

Required CI on the exact pull request head SHALL remain the merge gate.

#### Scenario: Finish reused evidence

- **WHEN** finish reused selected-check evidence
- **THEN** required CI on the exact pull request head still gates the merge

### Requirement: A generated-file declaration names a protected verifying check

A generated-file declaration in the committed check configuration SHALL name the required check that verifies the file, and that required check SHALL be part of the repository-owned protected full validation set.

#### Scenario: Valid declaration

- **WHEN** a project declares a file generated
- **THEN** the declaration names the required check that verifies the file
- **AND** that check is part of the repository-owned protected full validation set

### Requirement: An invalid generated-file declaration fails explicitly

A generated-file declaration without a required check that verifies the file and is part of the repository-owned protected full validation set, a malformed declaration or a missing check configuration at the main commit the candidate is based on SHALL fail explicitly rather than exclude or include the file silently.

#### Scenario: Declaration without a protected check

- **WHEN** a declaration lacks such a check, is malformed, or the check configuration is missing at the base main commit
- **THEN** identity computation fails explicitly
- **AND** the file is neither excluded nor included silently

### Requirement: A managed selected-check refusal names the blocker and next action

The refusal of `select_checks.py --execute` in a registered managed task checkout whose change is still active SHALL name the blocker and the next action.

#### Scenario: Managed run is refused

- **WHEN** `select_checks.py --execute` refuses in a registered managed task checkout whose change is still active
- **THEN** the refusal names the blocker and the next action

### Requirement: The generated-manifest check precedes the full test run

In the platform's full validation set, the cheap generated-manifest check SHALL run before the full test run.

#### Scenario: Full validation set runs

- **WHEN** the platform's full validation set runs
- **THEN** the cheap generated-manifest check runs before the full test run

### Requirement: A reusable-evidence refusal names the evidence path

The refusal of an evidence-producing `select_checks.py --execute` because the evidence already recorded at that path is reusable SHALL name the evidence path and state that archive and finish reuse the recorded evidence.

#### Scenario: Evidence-producing run with reusable evidence

- **WHEN** an evidence-producing run refuses because its recorded evidence is reusable
- **THEN** the refusal names the evidence path
- **AND** it states that archive and finish reuse it

### Requirement: Non-reusable evidence lets the selected-check run proceed

When existing evidence at the path of an evidence-producing `select_checks.py --execute` is not reusable, the run SHALL print the named reason and proceed.

#### Scenario: Existing evidence is not reusable

- **WHEN** existing evidence at the path is not reusable
- **THEN** the run prints the named reason
- **AND** it proceeds

### Requirement: Portable archive reuses selected-check evidence by the finish rule

Portable `archive` SHALL decide by the rule finish uses (`check_evidence_reuse`) before running the selected checks: reusable evidence SHALL be reused and the decision printed, and otherwise the selected checks SHALL run as before.

#### Scenario: Portable archive with reusable evidence

- **WHEN** portable `archive` finds reusable evidence
- **THEN** it reuses the evidence and prints the decision

#### Scenario: Portable archive without reusable evidence

- **WHEN** portable `archive` finds no reusable evidence
- **THEN** the selected checks run as before

### Requirement: A failure while deciding evidence reuse stops explicitly

A git or selection failure while deciding whether selected-check evidence is reusable SHALL stop explicitly.

#### Scenario: Git fails during the reuse decision

- **WHEN** a git or selection failure occurs while deciding
- **THEN** the command stops explicitly

### Requirement: The shared preflight registry lists the known cheap conditions

The ordered registry of cheap conditions in `lifecycle_preflight.py` SHALL consist of: shared-workspace permissions on the task paths, the task's board claim and scope together with scope overlap, the task's freshness against authoritative main under the existing behind-mergeable contract, the project's configured cheap gates (`[settings] preflight_commands`), and whether the task's committed selected-check evidence still proves its content.

#### Scenario: Preflight registry is evaluated

- **WHEN** the shared preflight runs
- **THEN** it evaluates shared-workspace permissions on the task paths, the board claim and scope with scope overlap, freshness under the behind-mergeable contract, the configured `[settings] preflight_commands`, and whether committed selected-check evidence still proves the content

### Requirement: Each preflight condition reuses its gate function

Each condition of the `lifecycle_preflight.py` registry SHALL call the function the corresponding gate uses, and SHALL report `passed`, `repaired` or `not-applicable` with the fact that makes it so, or refuse.

#### Scenario: Condition is evaluated

- **WHEN** a preflight condition is evaluated
- **THEN** it calls the function the corresponding gate uses
- **AND** it reports `passed`, `repaired` or `not-applicable` with the fact that makes it so, or refuses

### Requirement: Preflight prints every checked condition

A command that runs the `lifecycle_preflight.py` registry SHALL print every condition checked with its result.

#### Scenario: Preflight completes

- **WHEN** the preflight has evaluated its conditions
- **THEN** the command prints every condition checked with its result

### Requirement: A refused preflight condition stops before expensive work

When any `lifecycle_preflight.py` condition refuses, the command SHALL exit non-zero before the first expensive operation, reporting every refused condition together with the violated condition and the command that repairs it.

#### Scenario: Preflight condition refuses

- **WHEN** a preflight condition refuses
- **THEN** the command exits non-zero before the first expensive operation
- **AND** it reports every refused condition with the violated condition and the command that repairs it

### Requirement: An unevaluable preflight condition refuses

A `lifecycle_preflight.py` condition that cannot be evaluated SHALL refuse; no condition SHALL pass by default.

#### Scenario: Condition cannot be evaluated

- **WHEN** a preflight condition cannot be evaluated
- **THEN** it refuses and does not pass by default

### Requirement: Reconcile fails when gating evidence no longer proves the content

When a managed task's committed selected-check evidence is a publication gate (the change is archived, or the task is a coordinator-managed candidate) and no longer proves the task content, `reconcile` SHALL exit non-zero after the merge, naming the evidence path, its recorded base and the current base, and printing the exact refresh command `python3 scripts/select_checks.py --base origin/main --execute --evidence <path>` followed by committing the refreshed evidence.

#### Scenario: Gating evidence invalidated by the base move

- **GIVEN** an archived change or a coordinator-managed candidate
- **WHEN** `reconcile` merges authoritative main and the committed selected-check evidence no longer proves the task content
- **THEN** `reconcile` exits non-zero after the merge naming the evidence path, its recorded base and the current base
- **AND** it prints `python3 scripts/select_checks.py --base origin/main --execute --evidence <path>` followed by committing the refreshed evidence

### Requirement: Reconcile passes evidence that still proves the content

After `reconcile` merges authoritative main into a managed task, committed selected-check evidence that still proves the content SHALL pass unchanged.

#### Scenario: Evidence still proves the content

- **WHEN** `reconcile` evaluates committed evidence that still proves the task content
- **THEN** the evidence passes unchanged

### Requirement: Reconcile does not fail on quick task evidence

A quick task's machine-local evidence is not committed: `reconcile` SHALL report that finish reruns validation for the quick task's machine-local evidence and SHALL NOT fail.

#### Scenario: Quick task reconciled

- **WHEN** `reconcile` runs for a quick task
- **THEN** it reports that finish reruns validation for its machine-local evidence
- **AND** it does not fail

### Requirement: Reconcile fails when the content proof cannot be computed

During `reconcile`, inability to compute the current content proof SHALL fail explicitly.

#### Scenario: Content proof cannot be computed

- **WHEN** `reconcile` cannot compute the current content proof
- **THEN** it fails explicitly

### Requirement: Developer handoff enforces the routing gate

Every developer handoff of an active change, first or repeated, through `finish` or `execute_requirement.py advance`, SHALL run the same routing gate as archive before publication and SHALL fail naming the missing routing record or retained execution outcome and its command. An archived re-admission SHALL rely on the gate its first handoff passed.

#### Scenario: First handoff without a retained outcome

- **WHEN** a candidate is handed off without its retained execution outcome
- **THEN** the handoff fails before publication naming the record and its command

### Requirement: A merge-only reconcile keeps the handoff checkpoint

The developer handoff SHALL accept a friction checkpoint whose managed task-content proof is equivalent to the current one, so a reconcile that only merges main needs no new checkpoint. Changed task content SHALL still require a new checkpoint.

#### Scenario: Re-handoff after a merge-only reconcile

- **WHEN** a checkpoint was recorded before a reconcile that changed no task path
- **THEN** the re-handoff accepts it

#### Scenario: Task content changed after the checkpoint

- **WHEN** a task-owned file changed after the checkpoint
- **THEN** the handoff fails naming the checkpoint command

### Requirement: Finish of a merged PR reconciles before any developer handoff

When the exact PR of the task branch is merged, finish SHALL run the post-merge reconcile path before any managed-candidate developer handoff, and the board scope-claim condition SHALL NOT apply to it. An unreadable PR state SHALL stop finish explicitly.

#### Scenario: Merged PR at a pre-finalize head

- **GIVEN** a task worktree at a pre-finalize head whose exact PR is merged and whose board claim was released
- **WHEN** finish runs
- **THEN** it reconciles delivery without a scope claim and starts no developer handoff
