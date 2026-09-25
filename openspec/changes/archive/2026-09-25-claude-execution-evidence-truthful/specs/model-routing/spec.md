# model-routing Specification Delta

## MODIFIED Requirements

### Requirement: Model routing preserves truthful bounded execution provenance

For each routed non-trivial managed task, the platform SHALL preserve bounded execution provenance sufficient to distinguish the supervisor from any delegated executor that actually ran. The provenance SHALL reuse the existing routing/execution record rather than create a parallel tracing state machine.

For each participant where the information is applicable and available, provenance SHOULD represent the runtime/provider, participant role, execution profile, model identity, reasoning effort, bounded execution identifier and parent/child relationship. Model and reasoning-effort fields SHALL carry enough source/status information to distinguish platform-selected/configured values from runtime-confirmed values and unknown values.

Free-form model self-identification SHALL NOT be the authoritative source for model or effort provenance. A route that was merely prepared SHALL NOT be represented as an executed child. Fallback and escalation SHALL preserve the actual execution path rather than the preferred path that failed to run.

The concrete runtime adapters SHALL be verified against the supported Codex and Claude Code surfaces at implementation preflight. If a runtime does not reliably expose a desired field, the platform SHALL degrade truthfully by recording that field as unknown or only as selected/configured; it SHALL NOT scrape unstable UI text or infer effective execution state from an unsupported assumption solely to make the record complete.

#### Scenario: Routed Codex executor actually runs

- **GIVEN** Codex routing selects a routine or standard executor
- **WHEN** the platform-owned Codex launch actually runs the selected executor
- **THEN** the routing record preserves the actual executed child participant and the platform-selected model/profile
- **AND** reasoning effort is marked selected/configured or runtime-confirmed only according to evidence available from the supported current Codex runtime
- **AND** any unavailable effective effort remains unknown rather than inferred

#### Scenario: Native Claude subagent actually runs

- **GIVEN** Claude routing selects a routine or standard child and emits a native Agent hand-off
- **AND** the supported Claude runtime exposes no platform-verifiable launch receipt
- **WHEN** the supervisor records the returned agent identifier
- **THEN** the routing record preserves it only as a self-reported claim with its selected model/profile and unknown effort
- **AND** the record does not mark the child as launched or as an executed participant

#### Scenario: Preferred delegated executor is unavailable

- **GIVEN** routing selected a lower-cost executor
- **BUT** the current runtime cannot safely launch or confirm that child
- **WHEN** work is retained by or falls back to the parent
- **THEN** provenance reports the actual parent/fallback execution
- **AND** does not create an executed child participant for the unavailable route

#### Scenario: Routed work escalates

- **GIVEN** a delegated executor actually performed bounded work and then triggered escalation
- **WHEN** the stronger parent resumes the task
- **THEN** provenance may contain both real participants and the escalation relationship
- **AND** later friction can be attributed to the appropriate participant or to the overall run when the locus is ambiguous


## ADDED Requirements

### Requirement: Self-reported delegated execution is not hard launch proof

The platform SHALL NOT treat a value it cannot independently verify, such as a supervisor-supplied Claude agent identifier, as proof that a delegated executor launched. Such execution SHALL be recorded as an explicit claimed/unverified outcome whose launch state is unknown. The terminal routing gate SHALL accept a claimed routine/standard Claude outcome only on the evidence the platform can verify (exact managed identity and a clean containment postcheck) and SHALL NOT present it as a confirmed launch. Efficiency and calibration reports SHALL NOT count a self-reported execution, current or legacy, as a launched or verified execution. Execution paths whose launch the platform observes directly, such as the platform-owned Codex subprocess, and the explicit retained outcome SHALL keep their existing evidence semantics.

#### Scenario: Arbitrary agent identifier is recorded

- **GIVEN** a routine or standard Claude route
- **WHEN** a caller records execution with an arbitrary non-empty agent identifier
- **THEN** the record's outcome is claimed with self-reported launch evidence and unknown launch state
- **AND** no executed participant is attached
- **AND** reports classify it as claimed, not launched

#### Scenario: Legacy self-reported launch record reaches the gate

- **GIVEN** an older Claude routing record marks `launched: true` from a supplied agent identifier without the claimed outcome
- **WHEN** the terminal routing gate runs
- **THEN** it refuses the record as unverifiable launch evidence
- **AND** directs the supervisor to re-record the claimed execution

#### Scenario: Platform-observed Codex launch

- **GIVEN** the platform-owned Codex launcher observed a real subprocess run
- **WHEN** the routing gate and reports read that record
- **THEN** its launch evidence and outcome semantics are unchanged

