# engineering-capabilities Specification

## Purpose
TBD - created by archiving change add-optional-engineering-capability-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Optional engineering capabilities use one provider-neutral lifecycle

Dev Platform SHALL support reusable optional engineering capabilities through a canonical provider-neutral contract that is separate from core workflow-profile composition. A capability SHALL declare its identity, owner, applicability/trigger, invocation intent, visibility intent, kind, provenance, safety boundary, dependencies, materialization policy, and update/removal policy without embedding provider-local implementation details into the canonical identity.

#### Scenario: Project opts into an optional capability
- **WHEN** a managed project explicitly enables a supported optional engineering capability
- **THEN** the platform materializes the capability through the supported project/provider surfaces
- **AND** the capability retains one canonical identity and provenance record
- **AND** existing workflow-profile semantics remain unchanged

#### Scenario: Project does not opt in
- **WHEN** a managed project has not enabled an optional capability
- **THEN** render/update does not add that capability's agent context, generated provider surface, or tool runtime solely because the platform supports it

### Requirement: Capability invocation intent maps to provider-native controls

Dev Platform SHALL represent invocation intent provider-neutrally and SHALL prefer native Claude/Codex discovery and explicit-invocation controls over a parallel semantic router.

#### Scenario: Auto and explicit capability is materialized
- **WHEN** a capability declares `auto+explicit`
- **THEN** supported providers expose its name/description for implicit semantic discovery
- **AND** expose explicit invocation where supported

#### Scenario: Explicit-only capability is materialized
- **WHEN** a capability declares `explicit-only`
- **THEN** supported providers disable implicit model invocation through native controls
- **AND** retain explicit human invocation where supported

#### Scenario: Provider cannot represent an invocation mode
- **WHEN** a provider cannot faithfully represent the configured invocation intent
- **THEN** the capability support matrix reports the limitation
- **AND** the platform does not emulate parity with an undocumented competing router

### Requirement: Capability lifecycle operations are discoverable without memorizing internal tools

Dev Platform SHALL expose an agent-facing management/authoring path whose trigger metadata covers generic create, add, update, remove, list, and audit intents for skills/capabilities.

#### Scenario: User asks to add a new skill
- **WHEN** the user requests creation or adoption of a skill/capability without naming the management tool
- **THEN** the agent can discover the management/authoring path from its trigger metadata
- **AND** follows the canonical capability lifecycle

### Requirement: Capability authoring makes an automatic eval decision

Creating or materially changing a reusable capability SHALL perform structural validation and SHALL produce an explicit eval decision using #79 when available. Live eval SHALL be selective rather than universally mandatory.

#### Scenario: New or materially changed behavior is authored
- **WHEN** capability trigger, description, instructions, tool behavior, or safety-relevant behavior changes materially
- **THEN** the management path evaluates whether a live #79 run is appropriate
- **AND** records `run`, `skip-with-reason`, or `blocked/unavailable` rather than silently relying on human memory

#### Scenario: Metadata-only change is authored
- **WHEN** a change is demonstrably non-behavioral
- **THEN** structural validation still runs
- **AND** live eval may be skipped with an explicit reason

### Requirement: Capability catalog is derived from canonical descriptors

Dev Platform SHALL provide a human-readable list/show surface generated from canonical capability descriptors and project opt-in state. It SHALL NOT require a separately maintained catalog to stay synchronized.

#### Scenario: User requests all available capabilities
- **WHEN** a user or agent requests the capability catalog
- **THEN** the result includes each capability's purpose, kind, invocation mode, provider support, project enablement, provenance, dependencies/safety, and available eval evidence
- **AND** provider-native skill menus remain runtime projections rather than canonical state

### Requirement: External capability content is reproducible and reviewable

Any optional capability that incorporates external source content SHALL record an exact reviewed source revision or version, source path, applicable license, and content hash. Its effective instructions or tooling SHALL NOT silently change because a mutable upstream branch changes.

#### Scenario: Upstream changes after capability installation
- **GIVEN** a capability was materialized from pinned external content
- **WHEN** the upstream default branch later changes
- **THEN** the managed project's effective capability remains unchanged until an explicit reviewed capability update is applied

### Requirement: Provider-local capability surfaces do not become competing sources

When Codex, Claude, or another supported agent surface requires different local files or adapters, Dev Platform SHALL derive them from one canonical capability source or explicitly mark provider-specific support. Manually divergent provider copies SHALL NOT be treated as equivalent canonical state.

#### Scenario: Generated provider surface drifts
- **WHEN** one generated provider-local capability surface no longer matches its canonical source/provenance
- **THEN** platform validation reports the drift
- **AND** the divergent copy does not silently become authoritative

### Requirement: Tool-backed capabilities preserve application and safety boundaries

A tool-backed optional engineering capability SHALL remain development tooling unless a separate product/runtime change explicitly requires otherwise. Enabling it SHALL NOT by itself add production application dependencies, grant production access, authorize credentials, or widen write/origin permissions.

#### Scenario: Tool capability is enabled for local engineering work
- **WHEN** a managed project enables a tool-backed capability
- **THEN** its runtime/dependencies are isolated from the application production contract where supported
- **AND** existing production, credential, origin, and write-safety rules remain authoritative

### Requirement: Capability lifecycle is self-contained and reviewable

Fresh render, reviewed upgrade, capability update, and capability removal SHALL be deterministic and idempotent through Project Factory/Copier-compatible mechanisms. Normal downstream use SHALL NOT require mutable runtime access to the central Dev Platform repository.

#### Scenario: Existing managed project changes capability selection
- **WHEN** a reviewed platform update enables, updates, or removes an optional capability
- **THEN** the resulting downstream diff is reviewable
- **AND** project-owned rules are preserved
- **AND** repeated application converges without duplicated or stale provider surfaces

### Requirement: OpenSpec-generated agent integrations remain external

Optional engineering capability support SHALL NOT vendor or claim ownership of OpenSpec-generated Claude/Codex skills that the existing OpenSpec integration contract treats as external.

#### Scenario: Project refreshes OpenSpec integrations
- **WHEN** local readiness refreshes OpenSpec-generated agent integrations
- **THEN** optional-capability state remains distinct
- **AND** the platform does not reinterpret generated OpenSpec skills as platform-owned capability source

### Requirement: Material uncertainty can use an isolated prototype

Dev Platform SHALL offer an optional `bounded-prototype` capability that runs a disposable experiment when an observable experiment can materially reduce unresolved product, UI or technical uncertainty that available evidence cannot settle. The capability SHALL declare the question, the options or hypotheses, and time/iteration/cost bounds before the experiment starts, and SHALL run only in a temporary throwaway workspace or an explicitly project-declared prototype area.

#### Scenario: Experiment is justified
- **WHEN** evidence cannot resolve a material product, UI or technical choice and a bounded experiment can distinguish the options
- **THEN** the capability records the question, options and declared bounds, runs in an isolated area, and returns the observation plus an evidence reference

#### Scenario: Task is clear
- **WHEN** the accepted behavior and approach are already sufficiently clear, or the change is mechanical or a bounded fix with an established approach
- **THEN** no prototype ceremony is added and work proceeds normally

#### Scenario: Bounds are exhausted
- **WHEN** the declared time, iteration or cost bounds are reached or the evidence gathered is insufficient to decide
- **THEN** the capability stops and records the remaining uncertainty and the safest bounded interpretation rather than continuing the experiment

### Requirement: Prototype work does not touch production state

A `bounded-prototype` experiment SHALL NOT modify production source, dependencies, credentials, or managed task state, and SHALL be refused when it would require unapproved credentials, production writes, sensitive data, or wider permissions.

#### Scenario: Experiment stays isolated
- **WHEN** an experiment runs
- **THEN** production source, dependency manifests, credentials and task/lifecycle state are unchanged, and only temporary or explicitly declared prototype-area paths are written

#### Scenario: Authority is prohibited
- **WHEN** the experiment would need unapproved credentials, writes to production systems, sensitive data, or permissions beyond the current scope
- **THEN** it is refused and the boundary is reported instead of being worked around

### Requirement: Prototype output cannot bypass the production lifecycle

Prototype code SHALL be disposable by default and SHALL NOT be promoted automatically into production source. A useful experimental result SHALL be carried forward only as a decision plus bounded evidence, with production implementation entering the ordinary managed OpenSpec lifecycle.

#### Scenario: Prototype informs production work
- **WHEN** an experiment yields a useful decision
- **THEN** production implementation starts through ordinary managed intake, is written against the contract rather than copied from the prototype, and no prototype code is promoted automatically

### Requirement: Prototype evidence is bounded and cleanable

The `bounded-prototype` capability SHALL retain only a bounded decision record — question, options or hypotheses, declared bounds, observation, decision or remaining uncertainty, and an evidence reference or path — with no transcript, secrets, or sensitive payloads. Temporary state SHALL be cleaned by default when the experiment concludes; retention SHALL be explicit and policy-compatible and SHALL NOT make retained artifacts production source.

#### Scenario: Experiment concludes
- **WHEN** a bounded prototype run ends with a decision or exhausted bounds
- **THEN** the bounded decision record and its evidence reference are captured and the temporary workspace or prototype area is cleaned by default

#### Scenario: Retention is requested
- **WHEN** keeping prototype artifacts beyond the run is asked for
- **THEN** retention happens only when explicitly allowed and policy-compatible, and the retained artifacts are still not promoted into production source

### Requirement: Stack-specific web guidance is opt-in and bounded

Dev Platform SHALL expose React/Next guidance only to compatible opted-in projects and SHALL use progressive disclosure.

#### Scenario: Compatible project opts in
- **WHEN** a compatible React/Next project enables it
- **THEN** it receives a compact index and loads only relevant pinned rule groups

#### Scenario: Project is incompatible
- **WHEN** a backend-only, non-React or unsupported project is evaluated
- **THEN** the guidance is not applied and no application dependency changes

### Requirement: UI quality review is independent and advisory

Dev Platform SHALL offer read-only evidence-backed review of accessibility and user-visible web quality without creating tasks or replacing acceptance.

#### Scenario: Defect exists
- **WHEN** evidence supports an accessibility, keyboard/focus, form or responsive defect
- **THEN** location, severity, evidence, uncertainty and recommendation are reported

#### Scenario: Surface is healthy
- **WHEN** evidence supports no finding
- **THEN** no cosmetic work is manufactured

### Requirement: Guidance is reproducible and subordinate

Rules SHALL be pinned and updated only through reviewed capability lifecycle, and SHALL NOT override project design rules, redesign automatically or become a merge gate by themselves.

#### Scenario: Upstream publishes a new revision
- **WHEN** an upstream rule source changes after the capability was pinned
- **THEN** the pinned revision, license and content hash stay in effect
- **AND** the new revision is adopted only through a reviewed capability update, never a runtime read of a mutable URL

#### Scenario: Guidance conflicts with a project rule
- **WHEN** capability guidance disagrees with a project design system or repository rule
- **THEN** the project rule and its acceptance tests take precedence
- **AND** the guidance does not trigger an unsolicited redesign or block merge on its own

