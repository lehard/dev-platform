## ADDED Requirements

### Requirement: Repository goal scans create a finite, revision-bound investigation queue

Dev Platform SHALL offer an opt-in `repository-goal-scan` capability for explicit broad engineering goals whose answer depends on systematically investigating a repository rather than editing a known local area. Each run SHALL be bound to an immutable commit revision and SHALL produce a finite deterministic candidate/shard manifest before reasoning workers claim scan completion.

#### Scenario: Human explicitly requests a broad repository scan
- **WHEN** a human explicitly asks to scan a repository for a broad engineering goal
- **THEN** the capability records the goal, exact resolved commit SHA, selector profile, exclusions, and scan limitations
- **AND** deterministic selection runs against the committed repository tree rather than a moving branch name
- **AND** the resulting candidate queue and shard inventory are finite and inspectable.

#### Scenario: Ordinary local work is requested
- **WHEN** the task is an already-scoped implementation, bug fix, focused review, test run, or other local engineering action
- **THEN** `repository-goal-scan` is not implicitly introduced
- **AND** the normal task lifecycle proceeds without whole-repository scan ceremony.

### Requirement: Selection is deterministic and does not execute arbitrary planner code

The v1 scan planner SHALL express selection through a bounded inspectable selector profile that the deterministic adapter can execute over the committed tree. The supported selector surface SHALL include conservative path/inventory selection and bounded textual matching sufficient to produce candidate signals without evaluating arbitrary shell commands, downloaded code, or model-authored executable programs.

#### Scenario: Planner defines selector rules
- **WHEN** the reasoning planner identifies code relevant to the goal
- **THEN** it expresses that plan using the supported selector/profile schema
- **AND** the deterministic adapter runs the selectors across the declared committed-tree scope
- **AND** every emitted signal records which selector matched, where it matched, and bounded provenance needed by a map worker.

#### Scenario: Desired semantic selector is unsupported
- **WHEN** the goal would ideally use a semantic selector outside the supported v1 selector surface
- **THEN** the planner either chooses a conservative supported selector with wider recall or records the limitation
- **AND** the capability does not silently execute arbitrary code or claim stronger selector recall than it can justify.

### Requirement: Every selected candidate is accounted for exactly once

The sharding and map-result contract SHALL make selected-scope coverage mechanically checkable. Every emitted candidate SHALL belong to exactly one batch, and every completed batch result SHALL explicitly account for every candidate assigned to it as a finding or no-finding verdict. Omitted, duplicate, extra, pending, or failed candidates/batches SHALL be detectable.

#### Scenario: Deterministic sharding completes
- **WHEN** selector execution emits candidate signals
- **THEN** the adapter assigns every candidate to exactly one bounded batch
- **AND** detects duplicate or omitted candidate assignment before Map work starts.

#### Scenario: Worker reports a batch result
- **WHEN** a map worker finishes a batch
- **THEN** its structured result identifies the exact batch and every assigned candidate
- **AND** each candidate receives an explicit verdict
- **AND** extra, missing, or duplicate candidate identifiers make that result invalid rather than silently reducing coverage.

#### Scenario: Batch cannot be processed
- **WHEN** a batch fails or remains pending
- **THEN** the run records that state explicitly
- **AND** finalization does not represent the scan as complete.

### Requirement: Coverage claims separate queue exhaustion from selector recall

A repository goal scan SHALL distinguish mechanically proven coverage of the selected candidate queue from uncertainty in the selectors that created that queue. The platform SHALL NOT equate "all selected batches processed" with proof that every relevant defect/opportunity in the repository was selected.

#### Scenario: All selected batches were successfully processed
- **WHEN** every selected batch has a valid result and every selected candidate is accounted for
- **THEN** the coverage receipt may report 100% selected-scope processing
- **AND** separately reports selector/profile limitations, exclusions, and selection confidence
- **AND** does not make an unqualified whole-codebase completeness claim.

#### Scenario: Selector profile has known blind spots
- **WHEN** the planner or adapter identifies unsupported semantic analysis, explicit exclusions, or another selection limitation
- **THEN** that limitation remains visible in the final report even if selected-scope processing is 100%.

### Requirement: Reasoning fan-out stays provider-neutral and does not create a second task system

The capability SHALL define Plan, Map, and Reduce responsibilities without introducing a platform-owned provider-specific agent scheduler, second backlog, branch/worktree lifecycle, or execution authority. A supported executor MAY use its native bounded parallel/delegation facilities, and an executor without them MAY process batches sequentially while preserving the same manifest/result contract.

#### Scenario: Executor supports bounded parallel workers
- **WHEN** native runtime delegation can safely process independent read-only batches
- **THEN** the executor may fan out Map investigation across batches
- **AND** the deterministic manifest/result contract remains provider-neutral.

#### Scenario: Executor does not support parallel workers
- **WHEN** safe native parallelism is unavailable
- **THEN** batches may be processed sequentially
- **AND** the capability retains the same coverage/accounting semantics instead of fabricating parallel execution.

### Requirement: Scan findings remain advisory until explicitly promoted

Repository goal scans SHALL produce evidence-backed findings and a reduced prioritized report without automatically modifying source code, creating Issues, authoring managed tasks, opening pull requests, or changing lifecycle status. Scan state and intermediate evidence SHALL be machine-local/ignored by default.

#### Scenario: Scan produces findings
- **WHEN** Map/Reduce identifies one or more candidate improvements
- **THEN** each finding preserves bounded source evidence and provenance to its scan candidates/batches
- **AND** the reduced report may deduplicate and prioritize findings
- **BUT** no repository or backlog mutation is authorized solely by the finding.

#### Scenario: Human accepts a finding
- **WHEN** a human explicitly chooses one or more scan findings for implementation
- **THEN** that accepted work enters the ordinary quick-task or managed-task/OpenSpec lifecycle according to its scope
- **AND** the scan remains evidence/provenance rather than a competing implementation task list.
