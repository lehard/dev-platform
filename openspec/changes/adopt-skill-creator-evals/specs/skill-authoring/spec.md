## ADDED Requirements

### Requirement: Capability authoring automatically decides whether to evaluate

Dev Platform SHALL expose a bounded eval-decision surface that the canonical capability-management workflow invokes automatically when a reusable skill/capability is created, adopted, or materially changed. Users SHALL NOT need to remember or name a separate eval tool for normal capability lifecycle work.

#### Scenario: New reusable capability is authored
- **WHEN** the canonical management workflow creates or adopts a reusable capability
- **THEN** structural validation runs
- **AND** the workflow records an eval decision of `run`, `skip-with-reason`, or `blocked/unavailable`
- **AND** a `run` decision invokes the supported #79 eval path

#### Scenario: Material behavior or trigger changes
- **WHEN** a capability's description/trigger, instructions, tool behavior, or safety-relevant behavior changes materially
- **THEN** the management workflow re-evaluates whether live trigger/behavior testing is appropriate
- **AND** does not silently rely on the user to request it

#### Scenario: Change is demonstrably non-behavioral
- **WHEN** a capability change affects metadata only and cannot reasonably affect discovery or behavior
- **THEN** structural validation still runs
- **AND** live eval may be skipped only with an explicit reason

### Requirement: Skill and capability evals use provider-neutral evidence

Dev Platform SHALL support evaluation of a pinned candidate skill/capability using provider-neutral case and result records derived from the canonical capability identity/provenance contract. Canonical eval state SHALL NOT depend on Claude-specific or Codex-specific tool/event names.

#### Scenario: Candidate triggering is evaluated
- **WHEN** a supported runtime executes positive or negative trigger cases for a candidate capability
- **THEN** results record the candidate identity/hash, expectation, number of runs, trigger outcome/status, and bounded runtime provenance
- **AND** provider-local mechanics remain behind the adapter boundary

#### Scenario: Provider cannot expose truthful trigger evidence
- **WHEN** a configured provider/runtime cannot prove whether the candidate triggered
- **THEN** the result is recorded as `unsupported` or `unknown` according to the defined contract
- **AND** parity is not fabricated from another provider's behavior

### Requirement: Runtime failure is distinct from negative triggering

Evaluation SHALL distinguish a successful run in which a capability did not trigger from timeout, runtime failure, unsupported execution, and unavailable/blocked execution. Reports SHALL expose sample size and status distribution for nondeterministic live evaluations.

#### Scenario: Eval process times out
- **WHEN** a trigger-eval run exceeds its supported timeout
- **THEN** that run is recorded as `timeout`
- **AND** it is not counted as evidence that the candidate correctly did not trigger

### Requirement: Capability value can be compared to a baseline

The evaluation layer SHALL support bounded comparison of candidate-enabled behavior against baseline/no-capability behavior when an objective verifier or explicitly accepted bounded scoring contract exists.

#### Scenario: Capability improves a verifiable task
- **WHEN** the same representative task is evaluated with and without the candidate capability
- **THEN** the report identifies the compared candidate/baseline conditions and objective outcome evidence
- **AND** a positive trigger rate alone is not treated as proof of task-quality improvement

### Requirement: Explicit eval remains available

A user or agent SHALL be able to request evaluation/comparison of an existing capability directly, independent of an adoption/update operation.

#### Scenario: Existing capability is explicitly audited
- **WHEN** the user asks to test or compare an existing capability
- **THEN** the eval path runs or returns a truthful blocker without requiring a lifecycle mutation

### Requirement: Eval execution preserves existing containment and lifecycle ownership

Provider adapters SHALL use supported Dev Platform execution/containment boundaries and SHALL NOT introduce a second task orchestrator, bypass single-writer protections, or mutate durable platform/project state as an automatic consequence of an eval.

#### Scenario: Upstream reference uses an incompatible nested runtime
- **WHEN** an upstream eval implementation requires execution that conflicts with current platform containment or delegation rules
- **THEN** the platform adapts or rejects that runtime path
- **AND** does not weaken containment merely to match the upstream implementation

### Requirement: Eval evidence is bounded and optional at runtime

Eval fixtures/results SHALL avoid secrets, private full transcripts, and chain-of-thought. Missing optional eval runtime or credentials SHALL be reported truthfully without breaking ordinary managed-task or capability use.

#### Scenario: Eval runtime is unavailable
- **WHEN** a requested or automatically selected live eval cannot run because optional runtime/credentials are unavailable
- **THEN** the eval decision/result reports `blocked/unavailable` with an actionable reason
- **AND** ordinary platform lifecycle remains operational according to the calling workflow's policy

### Requirement: Evals do not autonomously promote capabilities

A passing eval SHALL remain supporting review evidence and SHALL NOT automatically rewrite, publish, roll out, or create managed work for a capability.

#### Scenario: Candidate passes all configured evals
- **WHEN** an eval report is successful
- **THEN** any durable capability change still requires the normal reviewed managed lifecycle
