## MODIFIED Requirements

### Requirement: Deliberate learning promotion

Platform friction SHALL keep raw evidence machine-local by default, while high-signal sanitized friction candidates SHALL be routed automatically to the appropriate GitHub process-issue backlog during supported lifecycle processing instead of depending on remembered routine manual promotion. Routing SHALL sanitize credential-like content and arbitrary raw evidence, deduplicate repeated occurrences with a stable non-secret fingerprint, and preserve a durable local fallback when GitHub routing is unavailable.

Process/friction issues SHALL remain evidence/inbox state. They SHALL NOT automatically create Development Backlog tasks, materialize OpenSpec changes, dispatch executors or start remediation. Converting process evidence into managed work requires separate explicit human fixation intent through the managed-task authoring contract.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem through a high-signal supported friction event
- **THEN** only sanitized structured evidence is sent to the central platform inbox through the routing contract
- **AND** raw evidence remains machine-local by default

#### Scenario: Platform-level friction is captured

- **WHEN** an agent or supported deterministic lifecycle hook records a high-signal event with `scope=platform`
- **THEN** the platform stores the raw structured event locally
- **AND** automatically attempts to create or update a sanitized fingerprinted issue in the configured platform repository
- **AND** does not require the human operator to remember a separate `promote` command

#### Scenario: Project-level friction is captured

- **WHEN** a high-signal event has `scope=project`
- **THEN** the platform automatically attempts to create or update the sanitized fingerprinted issue in the normalized current project repository
- **AND** does not route that project-specific issue to the central platform inbox solely because the platform provides the tooling

#### Scenario: Similar friction repeats

- **GIVEN** an open process issue already contains the stable sanitized fingerprint for the event class
- **WHEN** the same friction class recurs
- **THEN** routing updates that issue with a bounded sanitized occurrence rather than creating a duplicate issue
- **AND** execution model/runtime MAY be recorded as occurrence provenance without splitting the same process problem into model-specific duplicate issues

#### Scenario: Raw evidence contains sensitive context

- **WHEN** a recorded friction event contains arbitrary raw evidence, credential-like text or machine-local details
- **THEN** those raw fields remain machine-local by default
- **AND** the GitHub representation contains only bounded sanitized structured fields allowed by the routing contract

#### Scenario: GitHub routing is unavailable

- **WHEN** authentication, network or GitHub API availability prevents issue routing
- **THEN** the local event remains pending for a later supported lifecycle retry
- **AND** no raw credential-bearing evidence is printed or uploaded
- **AND** an otherwise safe task is not reclassified as failed solely because process telemetry could not be routed

#### Scenario: Process evidence looks ready for remediation

- **WHEN** a process issue or cloud review recommends a reusable fix
- **THEN** the recommendation remains advisory process evidence
- **AND** no Development Backlog issue or OpenSpec change is created until the human explicitly requests fixation through the managed-task authoring path

## ADDED Requirements

### Requirement: Meaningful friction capture is a completion invariant

For a non-trivial platform-owned task, terminal completion SHALL include a bounded post-task process retrospective so meaningful user corrections, repeated failures, safety near-misses, workarounds, false task premises, avoidable CI/lifecycle failures, excessive retries or other high-signal unresolved process problems cannot be omitted merely because the agent forgot to record them. The retrospective SHALL run before the final friction checkpoint and SHALL reuse the ordinary platform lifecycle rather than require a separate agent-specific hook or background state machine.

The retrospective SHALL distinguish problems already fixed during the task, problems already represented by existing friction/process evidence, and new meaningful unresolved/unrecorded findings. One retrospective MAY legitimately produce `0..N` new friction events. `none` SHALL mean that this bounded retrospective ran and found no new meaningful unresolved/unrecorded findings; a bare checkpoint call without a current retrospective result is insufficient.

The retrospective/checkpoint result SHALL be bound to current task execution state sufficiently to prevent a stale result from silently completing changed work. Supported machine-detectable lifecycle/process failures SHOULD continue recording friction directly without relying on model judgment.

#### Scenario: Several unresolved semantic frictions occurred

- **WHEN** a non-trivial platform-owned task reaches completion with two or more distinct high-signal semantic conditions that remain unresolved and unrecorded
- **THEN** the retrospective records or links all corresponding new friction events before completion is reported
- **AND** the completion result is not forced to choose only one event

#### Scenario: No meaningful friction occurred

- **WHEN** the bounded retrospective completes with zero new meaningful unresolved/unrecorded findings
- **THEN** the current completion checkpoint may resolve to `friction: none`
- **AND** no friction issue is created merely for the clean result

#### Scenario: Retrospective is omitted

- **WHEN** a non-trivial platform-owned task reaches the completion boundary without a current retrospective result
- **THEN** the lifecycle refuses terminal completion with an actionable instruction to perform the bounded review
- **AND** it does not invent a friction event on the agent's behalf

#### Scenario: Stale retrospective is reused

- **GIVEN** a valid retrospective/checkpoint existed for an earlier task execution state
- **WHEN** relevant task state changes before terminal completion
- **THEN** the old result does not satisfy the completion invariant
- **AND** a current retrospective is required

#### Scenario: Deterministic lifecycle failure occurs

- **WHEN** a supported lifecycle component detects an allow-listed machine-classifiable process failure or safety near-miss
- **THEN** it records the structured local friction event directly with bounded available context
- **AND** does not depend on a later natural-language reminder to preserve the observation

#### Scenario: Routing fails after checkpoint resolution

- **WHEN** a valid positive friction checkpoint has recorded its local event but GitHub routing is temporarily unavailable
- **THEN** completion may continue if all deterministic delivery requirements are otherwise satisfied
- **AND** the event remains pending for later routing retry

### Requirement: Friction evidence carries truthful bounded execution provenance

For a non-trivial platform-owned task, the platform SHALL maintain bounded execution provenance sufficient to relate completion/friction evidence to the execution run and, when knowable, the relevant supervisor or delegated executor. Provenance SHALL prefer structured runtime metadata or platform-owned routing/launch evidence over free-form model self-identification.

The provenance contract SHALL distinguish selected/configured model or reasoning-effort values from runtime-confirmed values. If the supported current runtime cannot establish a value truthfully, the value SHALL remain explicitly unknown rather than be inferred from a prompt, global default, model statement or unsupported assumption.

Execution provenance SHALL remain bounded metadata, not a transcript or general tracing system. Public friction routing SHALL include only sanitized provenance needed for useful comparison; raw execution evidence and unnecessary machine-local identifiers SHALL remain local by default.

#### Scenario: Friction is observed during a delegated execution

- **GIVEN** a supervisor actually delegates work to a recorded child executor
- **AND** a meaningful friction finding is attributable to that child
- **WHEN** the finding is recorded
- **THEN** it references the current execution/run and the child participant using available truthful runtime/routing evidence
- **AND** the parent model is not presented as the sole executor of that finding

#### Scenario: Route was prepared but child did not run

- **GIVEN** a lower-cost route was selected or prepared
- **BUT** delegation did not actually execute and the parent/fallback performed the work
- **WHEN** completion provenance is recorded
- **THEN** no executed child participant is fabricated
- **AND** the actual fallback/parent route is represented truthfully

#### Scenario: Effective reasoning effort cannot be confirmed

- **GIVEN** the platform selected or configured a reasoning-effort value
- **BUT** the current runtime does not reliably expose the effective value applied to the actual execution
- **WHEN** provenance is persisted
- **THEN** the selected/configured effort MAY be retained with that source/status
- **AND** runtime-confirmed/effective effort remains unknown

#### Scenario: Participant attribution is ambiguous

- **WHEN** a meaningful friction finding cannot be reliably attributed to a specific supervisor or child participant
- **THEN** the finding remains attached to the task execution/run with participant attribution unknown
- **AND** the platform does not guess which model caused it
