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

For a platform-owned task configured for automatic PR delivery, an agent SHALL NOT report the task as fully delivered while its exact task PR is still open/pending or while GitHub has merged it but safe local reconciliation remains incomplete. Completion/doctor status SHALL derive that condition from current Git/GitHub state and identify the supported next operation without requiring the human user to remember a Git hand-off.

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

Before non-trivial completion, the post-task retrospective SHALL consider bounded meaningful non-success evidence already produced by the current managed lifecycle. A `none` checkpoint SHALL NOT be accepted while a high-signal start, archive, publication, verification or comparable lifecycle failure remains without an explicit disposition as resolved-in-task, already represented by durable friction evidence, or newly recorded.

#### Scenario: Lifecycle failure exists but retrospective claims none

- **GIVEN** the current task produced a meaningful lifecycle failure
- **AND** no disposition or existing friction linkage accounts for it
- **WHEN** the executor attempts `checkpoint --result none`
- **THEN** completion rejects the checkpoint with an actionable retrospective instruction.

#### Scenario: Clean task has no meaningful friction

- **GIVEN** the retrospective reviews the current task and finds no meaningful unresolved/unrepresented lifecycle friction
- **WHEN** it records `none`
- **THEN** the checkpoint remains valid without additional ceremony.

### Requirement: Material verification can incorporate independent review perspectives

For material managed changes, Dev Platform SHALL support distinct contract-fidelity and engineering-quality review evidence bound to the exact candidate under verification when the configured runtime supports independent review.

#### Scenario: Independent reviews are available
- **WHEN** a material change reaches semantic verification
- **THEN** spec-fidelity and engineering-quality findings can be produced from independent review contexts
- **AND** the findings identify the candidate they reviewed
- **AND** they are consumed by the existing verification lifecycle
- **AND** the verification receipt cites the accepted review evidence

#### Scenario: Independent runtime is unavailable
- **WHEN** configured independent review cannot be executed
- **THEN** the limitation is reported truthfully
- **AND** Dev Platform does not fabricate independent-review evidence

#### Scenario: Candidate changes after review preparation
- **GIVEN** independent review evidence was prepared for a candidate/base identity
- **WHEN** the candidate or base diff changes
- **THEN** the existing evidence is not accepted for the new candidate
- **AND** a fresh independent review request is required

### Requirement: Material review findings require explicit disposition

A material independent-review finding SHALL be resolved, explicitly rejected with rationale, or retained as a blocker before terminal semantic verification can claim PASS.

#### Scenario: Material finding remains unresolved
- **WHEN** semantic verification evaluates a material reviewer finding with no accepted disposition
- **THEN** `OpenSpec-Verify: PASS` is not recorded solely because deterministic tests passed

#### Scenario: Independent review is configured but unavailable
- **GIVEN** independent review is required for the material managed change
- **AND** either required perspective is unavailable
- **WHEN** archive readiness is evaluated
- **THEN** archive is blocked with the recorded limitation
- **AND** the lifecycle does not claim independent evidence was obtained

