# model-routing Specification Delta

## ADDED Requirements

### Requirement: Snapshot semantic extraction prefers routine read-only workers

Snapshot construction SHALL use deterministic preprocessing first and routine/read-only workers for bounded semantic extraction before stronger-model escalation, unless conflict, low confidence, or materially complex interpretation requires escalation.

#### Scenario: Bounded extraction is routine
- **WHEN** selected evidence can be summarized into a projection without a novel design decision
- **THEN** the platform may delegate that extraction through the existing routine read-only context-worker path
- **AND** the worker has no repository write authority

#### Scenario: Extraction is ambiguous or conflicting
- **WHEN** the routine worker reports materially low confidence or conflicting evidence that source-of-truth rules cannot resolve mechanically
- **THEN** the result is marked for stronger review/escalation
- **AND** the routine worker does not invent a new architecture decision

### Requirement: Snapshot worker evidence reuses routing provenance where practical

The platform SHALL avoid a parallel telemetry system solely for snapshot workers.

#### Scenario: Worker execution is measurable
- **WHEN** existing routing/context-worker provenance exposes timing or supported usage evidence
- **THEN** snapshot reporting may reference/reuse that evidence
- **AND** unavailable token fields remain unknown rather than guessed
