## ADDED Requirements

### Requirement: Validation feedback is observable and failure-diagnostic

The platform SHALL emit machine-readable duration and outcome evidence for each validation command. Successful routine output SHALL be concise, while a failed command SHALL preserve actionable diagnostics including the command identity, exit outcome, and bounded relevant output or a durable artifact reference.

#### Scenario: Successful local validation

- **WHEN** a local validation command succeeds
- **THEN** the lifecycle records its selected check identity, duration and successful outcome
- **AND** routine output remains concise enough for an agent to identify progress and elapsed time

#### Scenario: Validation command fails

- **WHEN** a validation command fails
- **THEN** the lifecycle reports the command identity and non-success outcome
- **AND** exposes a bounded useful diagnostic tail or artifact location without suppressing the failure

### Requirement: Local affected validation never replaces protected PR authority

The platform SHALL distinguish a conservative `local affected` feedback policy from a `protected full` merge-authority policy. A protected-main PR SHALL require the complete authoritative platform validation set even when a local affected subset has succeeded.

#### Scenario: Proven local affected change

- **WHEN** every changed path is mapped by a maintained and tested selector rule
- **THEN** local feedback may execute the mapped affected checks
- **AND** the resulting success is not accepted as the protected PR required validation result

#### Scenario: Protected-main PR is evaluated

- **WHEN** a protected-main PR contains any platform change
- **THEN** CI executes the complete authoritative validation set required by the protected publication contract
- **AND** merge authority does not depend on a prior local affected run

### Requirement: Validation selection fails closed

The validation selector SHALL choose the full authoritative set whenever a changed path is unknown, ambiguously classified, or affects selector/configuration, workflow, OpenSpec, lifecycle, or other explicitly high-impact control-plane code.

#### Scenario: Changed path has no proven selector mapping

- **WHEN** local affected validation receives a path without an explicit safe mapping
- **THEN** it selects the full validation set
- **AND** reports that the fallback was safety-driven

#### Scenario: Control-plane path changes

- **WHEN** a change touches validation selection/configuration, CI workflow, OpenSpec, or lifecycle control-plane code
- **THEN** local affected validation selects the full validation set

### Requirement: Parallel validation preserves resource isolation and aggregate authority

The platform SHALL run validation partitions concurrently only when each partition's mutable resources are isolated per worker or explicitly serialized. When CI uses partitions, it SHALL publish a stable aggregate required check that fails if any mandatory partition fails.

#### Scenario: Candidate partition shares mutable state

- **WHEN** the resource audit identifies a shared mutable database, artifact path, lock, port, external state, or process-global setting
- **THEN** the candidate is serialized or given proven per-worker isolation before concurrent execution is enabled

#### Scenario: Partitioned required validation fails

- **WHEN** any mandatory validation partition fails
- **THEN** the stable aggregate required check reports failure
- **AND** protected-main merge remains blocked
