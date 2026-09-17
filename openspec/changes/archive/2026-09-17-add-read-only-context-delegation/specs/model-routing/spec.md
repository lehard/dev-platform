## ADDED Requirements

### Requirement: Bulk repository context may be delegated to a cheaper read-only worker

The platform MAY delegate question-directed bulk repository reads from an already selected managed-task executor to a provider-local read-only context worker. This auxiliary operation SHALL remain distinct from the managed task start tier: using a routine-profile context worker SHALL NOT by itself classify or rewrite the managed task as R1.

The context worker SHALL resolve through replaceable provider-local routing configuration rather than durable concrete model IDs in task artifacts. Cross-provider context delegation SHALL NOT be required.

#### Scenario: Strong session needs a narrow answer from broad source context

- **GIVEN** an R2 or R3 execution needs to inspect a bounded set of large repository files for a specific question
- **AND** a supported cheaper provider-local read-only worker is available
- **WHEN** context delegation is selected
- **THEN** the worker receives the question and bounded repository scope
- **AND** returns compact structured evidence to the parent
- **AND** the managed task keeps its existing R2/R3 execution identity

#### Scenario: Exact source detail is needed

- **GIVEN** editing, debugging, architecture reasoning or exact verification requires source detail
- **WHEN** the parent needs a targeted file/range
- **THEN** a direct targeted read remains available
- **AND** context delegation does not force an unnecessary summarization hop

### Requirement: Context delegation is read-only and fails open truthfully

A supported context worker path SHALL NOT grant repository write capability. If the runtime cannot provide the supported read-only delegation, the worker fails, or its result is materially low confidence, the platform SHALL expose a bounded direct-read fallback and SHALL NOT claim successful delegation.

Read-only context delegation SHALL NOT require write-containment ceremony solely for consistency with write-capable executors.

#### Scenario: Context worker cannot run

- **GIVEN** the selected runtime lacks the required read-only worker surface or the delegated operation fails
- **WHEN** the parent still needs repository evidence
- **THEN** the platform records the real unsupported/failed outcome
- **AND** direct reading remains available
- **AND** no successful child execution is fabricated

### Requirement: Context-delegation evidence is bounded and semantically truthful

The platform SHALL retain enough local observation evidence to evaluate context delegation without creating a separate transcript or telemetry service. At minimum, supported observations SHALL distinguish source payload volume, returned payload volume, attributable direct re-read volume when observable, elapsed time, outcome, and provider/model provenance when truthfully known.

Deterministic line or byte counts MAY be used as payload-reduction evidence but SHALL NOT be labelled as measured token or request usage. Canonical token/request fields SHALL be populated only from exact supported runtime evidence; unavailable values remain unknown.

#### Scenario: Runtime does not expose exact token usage

- **GIVEN** a context delegation completed and source/result byte volumes are known
- **BUT** the runtime does not expose an exact supported token field
- **WHEN** the observation is recorded
- **THEN** byte/line payload evidence is retained separately
- **AND** token usage remains unknown rather than estimated as canonical usage

### Requirement: Initial context delegation remains soft before calibration

The first production context-delegation capability SHALL remain advisory and SHALL NOT hard-block ordinary repository Read operations. Hard interception or redirection of eligible reads requires a later evidence-gated change.

#### Scenario: Soft dogfood phase is active

- **GIVEN** context delegation is available during the initial dogfood phase
- **WHEN** the parent chooses a direct repository read
- **THEN** the platform does not block the read solely because a context worker exists
- **AND** later calibration may evaluate whether stronger enforcement is justified
