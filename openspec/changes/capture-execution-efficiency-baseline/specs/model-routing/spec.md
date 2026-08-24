## ADDED Requirements

### Requirement: Managed execution provenance captures comparable efficiency evidence

For non-trivial managed execution, the platform SHALL preserve bounded runtime-efficiency evidence in the existing routing/execution provenance path rather than creating a parallel observability state machine.

The platform SHALL record execution timing from its own execution boundary. Runtime/provider-supplied usage fields such as input/prompt tokens, cache-read tokens, fresh/computed input tokens, output tokens, total tokens, and model-request/turn counts MAY be recorded when the supported runtime exposes authoritative values. Optional measurements SHALL preserve enough source/status information to distinguish measured/confirmed values from unavailable or unknown values.

Missing efficiency evidence SHALL NOT be represented as zero and SHALL NOT make an otherwise valid task execution fail solely because a provider does not expose a usage metric.

#### Scenario: Runtime exposes authoritative usage

- **GIVEN** a managed executor returns supported structured usage evidence
- **WHEN** the platform records the execution outcome
- **THEN** the compatible normalized efficiency fields are preserved with truthful source/status
- **AND** platform-measured elapsed time is preserved alongside them
- **AND** no prompt, chain-of-thought or full transcript is required

#### Scenario: Runtime does not expose token usage

- **GIVEN** a managed executor completes but the supported runtime exposes no reliable token breakdown
- **WHEN** execution provenance is finalized
- **THEN** elapsed time and the available lifecycle outcome are still recorded
- **AND** unsupported usage fields remain unknown/absent rather than guessed or set to zero
- **AND** completion is not rejected solely because usage metadata is unavailable

### Requirement: Efficiency evidence reuses existing execution outcomes

Efficiency measurement SHALL reuse the existing provider/model/profile provenance and the existing verification, retry/escalation/fallback, human-intervention, containment, abnormal-termination and recovery evidence where those facts already exist. It SHALL NOT introduce a competing task/execution status machine.

#### Scenario: Execution escalates

- **GIVEN** an R2 execution performs bounded work and then escalates
- **WHEN** efficiency evidence is aggregated
- **THEN** the actual elapsed/usage evidence for the performed path remains attributable to the real execution
- **AND** the existing escalation/final-outcome provenance remains authoritative

### Requirement: Efficiency evidence remains runtime-neutral and historically compatible

The canonical efficiency schema SHALL NOT depend on DeepSeek Harness, Cordis, or another optional runtime implementation. Historical execution records that predate efficiency fields SHALL remain readable and SHALL be treated as missing evidence rather than invalid or zero-valued observations.

#### Scenario: Historical record is analyzed

- **GIVEN** a prior execution record has no efficiency fields
- **WHEN** a baseline report reads it
- **THEN** the record may still contribute compatible outcome facts
- **AND** unavailable efficiency measurements are classified as missing
- **AND** no fabricated values are introduced

### Requirement: Baseline reporting exposes sample adequacy

The platform SHALL provide a bounded report over existing execution evidence that exposes observation counts and useful aggregate efficiency measures only for populated compatible fields. The report SHALL explicitly identify insufficient evidence for small or sparse samples.

The first decision-quality baseline SHOULD use roughly 15–30 verified managed executions with enough task-family/runtime coverage to make comparison useful; the count is an evidence guideline rather than a ceremonial threshold.

#### Scenario: Baseline sample is too small

- **GIVEN** only a small or sparsely populated execution sample exists
- **WHEN** the baseline report is generated
- **THEN** it reports the available observations and missing-field coverage
- **AND** it labels the evidence insufficient rather than claiming a reliable improvement or regression

### Requirement: Baseline collection does not self-optimize execution

This change SHALL collect and report evidence only. It SHALL NOT automatically switch runtimes, change routing tiers, enable R1, enforce token/time kill budgets, or self-modify routing policy based on the collected sample.

#### Scenario: High-cost execution is observed

- **WHEN** the report observes an unusually expensive or long execution
- **THEN** the observation is retained for analysis
- **AND** no new automatic routing or cancellation policy is inferred by this change alone