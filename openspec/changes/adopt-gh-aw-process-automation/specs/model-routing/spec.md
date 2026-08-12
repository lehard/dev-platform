## ADDED Requirements

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
- **WHEN** the supervisor actually invokes that Agent and records the returned execution identifier
- **THEN** the routing record preserves the executed Claude child participant, its selected model/profile/effort and returned bounded agent identifier
- **AND** selected values are not mislabeled as runtime-confirmed unless the supported runtime also confirms them

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

### Requirement: Execution provenance remains replaceable across runtime/model changes

Execution provenance SHALL describe a specific task execution rather than become a durable model requirement of the backlog Issue or canonical product specification. Concrete model IDs, reasoning-effort vocabulary and runtime-specific identifiers remain replaceable execution metadata governed by the current supported platform/runtime policy.

Historical provenance MAY preserve the model/runtime values that actually or reportedly applied to that execution, but a later change to the supported model lineup SHALL NOT require editing old Development Backlog Issues or accepted OpenSpec requirements solely to rename current executor models.

#### Scenario: Model policy changes after an execution

- **GIVEN** a completed or recorded task execution used an older supported model mapping
- **WHEN** the platform later changes its current model-routing policy
- **THEN** historical execution provenance retains the truthful historical values/source status
- **AND** future executions use the new current policy without rewriting the managed task contract
