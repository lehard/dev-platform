## ADDED Requirements

### Requirement: Routed Codex execution has single-writer ownership per assigned worktree

The model-routing lifecycle SHALL prevent more than one active write-capable Codex executor from owning the same assigned worktree at the same time. Launch ownership SHALL remain held until the prior writer is known to have exited or has been terminated and reaped.

#### Scenario: Second writer is requested while the first is active

- **GIVEN** a write-capable Codex executor currently owns an assigned worktree
- **WHEN** another routed Codex launch targets the same worktree
- **THEN** the second launch is refused before it can write
- **AND** the existing writer remains the only active writer for that worktree

#### Scenario: Prior launch state is ambiguous

- **WHEN** the platform cannot safely prove that the previous writer has exited
- **THEN** it does not release single-writer ownership
- **AND** a new write-capable launch fails closed with an actionable diagnostic

### Requirement: Abnormal delegated return leaves truthful execution state

If a routed Codex launch returns abnormally after starting a writer, routing provenance SHALL NOT represent the handoff as cleanly complete until the writer lifecycle is resolved.

#### Scenario: Parent path fails after child launch

- **WHEN** a routed launch encounters timeout, cancellation, stream failure or another abnormal return after the child started
- **THEN** execution provenance records the real failed/abnormal outcome
- **AND** the worktree is not made eligible for a new writer while the previous writer remains live or ambiguous
