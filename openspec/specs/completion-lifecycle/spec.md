# Completion Lifecycle Specification

## Purpose

The completion lifecycle SHALL make semantic OpenSpec verification and archive part of the agent-owned definition of done for non-trivial work, so completed changes cannot silently remain active or depend on the human user remembering cleanup steps.

## Requirements

### Requirement: Completed OpenSpec changes cannot remain active at publication

For non-trivial OpenSpec work, the platform SHALL treat a change with a completed task checklist as not publishable until the change is archived.

#### Scenario: Completed active change blocks finish

- **GIVEN** an active OpenSpec change with one or more task checkboxes
- **AND** every task checkbox is complete
- **WHEN** the agent runs the platform completion or publication flow
- **THEN** the flow fails with an instruction to verify and archive the change

#### Scenario: In-progress active change is allowed

- **GIVEN** an active OpenSpec change with at least one incomplete task
- **WHEN** lifecycle hygiene is checked
- **THEN** the change is not treated as stale solely because it is active

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

For a platform-owned task configured for automatic PR delivery, an agent SHALL NOT report the task as fully delivered while its exact task PR is still open/pending or while GitHub has merged it but safe local reconciliation remains incomplete. Completion/doctor status SHALL derive that condition from current Git/GitHub state and identify the supported next operation without requiring the human user to remember a Git hand-off. For a managed task, read-only status SHALL distinguish confirmed exact PR merge from full terminal completion. Full completion SHALL be reported only when mandatory post-merge local, Project, linked process-evidence, and required cleanup obligations are fulfilled or have an explicitly supported terminal disposition. Status SHALL derive this from existing authoritative lifecycle and obligation evidence without a second terminal state ledger. A failed or unknown post-merge obligation SHALL be reported as pending or blocking without changing the confirmed merge fact to failure.

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

Before non-trivial completion, the post-task retrospective SHALL consider bounded meaningful non-success evidence already produced by the current managed lifecycle, together with recorded manual workaround, non-default override, known-recurrence and observed-drift evidence attributed to the task. A `none` checkpoint SHALL NOT be accepted while any such mandatory signal remains without an explicit disposition as resolved-in-task, expected-behavior, already represented by durable friction evidence, or newly recorded. A new occurrence of an already open problem SHALL be preserved as recorded evidence and SHALL NOT be dismissed by disposition.

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

Dev Platform SHALL evaluate all safely observable read-only and cheap completion gates, including the existing private Backlog reference guard over the current public candidate, before starting expensive validation. The same guard SHALL still run at publication time to cover changes after preflight.

#### Scenario: One or more blockers are already observable

- **WHEN** cleanliness, OpenSpec/provenance, terminal state, freshness, scope, checkpoint, privacy or integration preflight reports a blocker
- **THEN** expensive validation does not start
- **AND** independently observable blockers are returned in one bounded actionable report

#### Scenario: Preflight is clear

- **WHEN** every current cheap completion gate passes
- **THEN** the canonical required checks run with unchanged verification semantics
- **AND** publication still performs required race-sensitive rechecks

#### Scenario: Private reference in candidate evidence

- **GIVEN** a candidate verification artifact contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the candidate-file surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Private reference in new commit message

- **GIVEN** a new candidate commit message contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the commit-message surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Clean candidate passes preflight

- **WHEN** no supported public candidate surface contains a direct private reference
- **THEN** completion proceeds to the existing required validation without another privacy mechanism
- **AND** publication still applies the fail-closed current-candidate guard

### Requirement: Synchronous completion exposes bounded progress

The existing synchronous completion command SHALL expose its current lifecycle stage and test-group progress without requiring background polling processes.

#### Scenario: Completion runs for an extended period

- **WHEN** validation or protected publication remains in progress
- **THEN** the caller receives bounded stage progress and terminal output
- **AND** no new daemon, job queue or workflow engine is required

### Requirement: Completion evidence freshness follows proven task-content identity

Managed completion evidence SHALL NOT become stale solely because HEAD changed through a platform-owned lifecycle transition when the platform can mechanically prove that the validated task-owned content is unchanged. Evidence SHALL retain its original commit provenance, and reuse SHALL require a deterministic auditable content-equivalence proof.

If task-owned content changed or equivalence cannot be proven, the relevant evidence SHALL be treated as stale and the required validation or retrospective SHALL run again.

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

Every platform gate that decides whether a change's tasks are complete (lifecycle readiness and archive, completed-change hygiene, managed delivery provenance and shared Requirement integration) SHALL count tasks.md checklist items using the same task-line semantics as upstream OpenSpec apply progress: an item with a `-`, `*`, `+`, `N.` or `N)` list marker followed by a checkbox is a task, and a task is complete only when its checkbox content is `x` or `X`. Any other checkbox content SHALL count as incomplete.

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

A required independent review SHALL be accepted only when the platform observed the reviewer launch, launched it as a new non-resumable process whose runtime-enforced tool or sandbox surface grants no repository write capability, and a before/after content check of the task worktree and integration checkout shows no mutation. The reviewer provider SHALL default to the current task route's provider; cross-provider review SHALL happen only by explicit configuration. The canonical review contract SHALL NOT name a concrete model or provider API.

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

When independent review is required, the lifecycle SHALL run a missing or stale review automatically during archive preflight before expensive validation, SHALL re-validate current review evidence before publication, and SHALL expose the derived review state and next command through task status and Requirement advance from file-backed evidence without a separate state store. Review SHALL be required only for changes with managed provenance in a repository that enables it; quick tasks without managed provenance SHALL NOT receive review ceremony.

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

Before launching any independent review perspective, the platform SHALL prove that the selected reviewer runtime is usable on the current host and account with the exact selected model, using one bounded probe launched through the same read-only adapter. When readiness cannot be proven, the platform SHALL record the review as unavailable with a concrete actionable limitation and SHALL NOT launch the perspectives. The platform SHALL expose the same readiness check as a standalone command. It SHALL NOT substitute another model or provider.

#### Scenario: Reviewer CLI is not logged in or cannot be executed
- **GIVEN** a required independent review
- **AND** the resolved reviewer binary is missing or its probe exits unsuccessfully
- **WHEN** the review runs
- **THEN** both perspectives are recorded as unavailable with a limitation naming the runtime's bounded error and the next step
- **AND** no review perspective is launched
- **AND** archive stops before expensive validation

#### Scenario: Selected model is not available to the current account
- **GIVEN** the probe with the exact selected model is rejected by the runtime
- **WHEN** readiness is evaluated
- **THEN** the limitation identifies the provider and model and directs the operator to change the binding or the account
- **AND** no other model or provider is tried

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
