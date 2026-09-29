## MODIFIED Requirements

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

## ADDED Requirements

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
