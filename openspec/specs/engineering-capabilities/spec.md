# engineering-capabilities Specification

## Purpose
Define the lifecycle and ownership boundaries for optional engineering capabilities supplied by the platform.

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

### Requirement: A capability is an atomic deliverable unit

Dev Platform SHALL review and deliver each capability as one atomic unit: its canonical descriptor, instructions or provider skill, optional tool/runtime adapter, dependencies, eval contract, and provider materialization. Components from different reviewed revisions SHALL NOT be mixed. Until capabilities have an independent release lifecycle, an immutable Dev Platform release plus verifiable content hashes SHALL establish the unit's revision consistency.

#### Scenario: Capability is installed from a platform release
- **WHEN** a project enables a capability from a released Dev Platform revision
- **THEN** every component of that capability comes from the same reviewed atomic unit
- **AND** validation can verify the unit's content hashes where hashes are declared

#### Scenario: Capability release mechanism evolves
- **WHEN** a future independent capability release lifecycle is introduced
- **THEN** it may replace the versioning mechanism
- **AND** it preserves the same atomic capability boundary

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

### Requirement: Generated CI materializes derived capability surfaces before platform validation

Every generated project's CI SHALL materialize its selected capabilities' derived provider surfaces before running platform validation, since those surfaces are deliberately gitignored and therefore absent on any fresh checkout.

#### Scenario: A fresh checkout has capabilities enabled

- **GIVEN** a project's `dev-platform/capabilities.toml` has one or more capabilities enabled
- **AND** the checkout is fresh, so the gitignored derived provider surfaces for those capabilities do not yet exist
- **WHEN** generated CI runs
- **THEN** it runs `capability_manager.py sync` before `platform_doctor.py`
- **AND** platform validation's capability audit passes

#### Scenario: Materialized surfaces are never committed

- **WHEN** generated CI materializes selected capability surfaces
- **THEN** those files remain matched by the project's own gitignore patterns
- **AND** no generated CI step stages or commits them

### Requirement: Repository goal scans create a finite, revision-bound investigation queue

Dev Platform SHALL offer an opt-in `repository-goal-scan` capability for explicit broad engineering goals whose answer depends on systematically investigating a repository rather than editing a known local area. Each run SHALL be bound to an immutable commit revision and SHALL produce a finite deterministic candidate/shard manifest before reasoning workers claim scan completion.

#### Scenario: Human explicitly requests a broad repository scan
- **WHEN** a human explicitly asks to scan a repository for a broad engineering goal
- **THEN** the capability records the goal, exact resolved commit SHA, selector profile, exclusions, and scan limitations
- **AND** deterministic selection runs against the committed repository tree rather than a moving branch name
- **AND** the resulting candidate queue and shard inventory are finite and inspectable.

#### Scenario: Ordinary local work is requested
- **WHEN** the task is an already-scoped implementation, bug fix, focused review, test run, or other local engineering action
- **THEN** `repository-goal-scan` is not implicitly introduced
- **AND** the normal task lifecycle proceeds without whole-repository scan ceremony.

### Requirement: Selection is deterministic and does not execute arbitrary planner code

The v1 scan planner SHALL express selection through a bounded inspectable selector profile that the deterministic adapter can execute over the committed tree. The supported selector surface SHALL include conservative path/inventory selection and bounded textual matching sufficient to produce candidate signals without evaluating arbitrary shell commands, downloaded code, or model-authored executable programs.

#### Scenario: Planner defines selector rules
- **WHEN** the reasoning planner identifies code relevant to the goal
- **THEN** it expresses that plan using the supported selector/profile schema
- **AND** the deterministic adapter runs the selectors across the declared committed-tree scope
- **AND** every emitted signal records which selector matched, where it matched, and bounded provenance needed by a map worker.

#### Scenario: Desired semantic selector is unsupported
- **WHEN** the goal would ideally use a semantic selector outside the supported v1 selector surface
- **THEN** the planner either chooses a conservative supported selector with wider recall or records the limitation
- **AND** the capability does not silently execute arbitrary code or claim stronger selector recall than it can justify.

### Requirement: Every selected candidate is accounted for exactly once

The sharding and map-result contract SHALL make selected-scope coverage mechanically checkable. Every emitted candidate SHALL belong to exactly one batch, and every completed batch result SHALL explicitly account for every candidate assigned to it as a finding or no-finding verdict. Omitted, duplicate, extra, pending, or failed candidates/batches SHALL be detectable.

#### Scenario: Deterministic sharding completes
- **WHEN** selector execution emits candidate signals
- **THEN** the adapter assigns every candidate to exactly one bounded batch
- **AND** detects duplicate or omitted candidate assignment before Map work starts.

#### Scenario: Worker reports a batch result
- **WHEN** a map worker finishes a batch
- **THEN** its structured result identifies the exact batch and every assigned candidate
- **AND** each candidate receives an explicit verdict
- **AND** extra, missing, or duplicate candidate identifiers make that result invalid rather than silently reducing coverage.

#### Scenario: Batch cannot be processed
- **WHEN** a batch fails or remains pending
- **THEN** the run records that state explicitly
- **AND** finalization does not represent the scan as complete.

### Requirement: Coverage claims separate queue exhaustion from selector recall

A repository goal scan SHALL distinguish mechanically proven coverage of the selected candidate queue from uncertainty in the selectors that created that queue. The platform SHALL NOT equate "all selected batches processed" with proof that every relevant defect/opportunity in the repository was selected.

#### Scenario: All selected batches were successfully processed
- **WHEN** every selected batch has a valid result and every selected candidate is accounted for
- **THEN** the coverage receipt may report 100% selected-scope processing
- **AND** separately reports selector/profile limitations, exclusions, and selection confidence
- **AND** does not make an unqualified whole-codebase completeness claim.

#### Scenario: Selector profile has known blind spots
- **WHEN** the planner or adapter identifies unsupported semantic analysis, explicit exclusions, or another selection limitation
- **THEN** that limitation remains visible in the final report even if selected-scope processing is 100%.

### Requirement: Reasoning fan-out stays provider-neutral and does not create a second task system

The capability SHALL define Plan, Map, and Reduce responsibilities without introducing a platform-owned provider-specific agent scheduler, second backlog, branch/worktree lifecycle, or execution authority. A supported executor MAY use its native bounded parallel/delegation facilities, and an executor without them MAY process batches sequentially while preserving the same manifest/result contract.

#### Scenario: Executor supports bounded parallel workers
- **WHEN** native runtime delegation can safely process independent read-only batches
- **THEN** the executor may fan out Map investigation across batches
- **AND** the deterministic manifest/result contract remains provider-neutral.

#### Scenario: Executor does not support parallel workers
- **WHEN** safe native parallelism is unavailable
- **THEN** batches may be processed sequentially
- **AND** the capability retains the same coverage/accounting semantics instead of fabricating parallel execution.

### Requirement: Scan findings remain advisory until explicitly promoted

Repository goal scans SHALL produce evidence-backed findings and a reduced prioritized report without automatically modifying source code, creating Issues, authoring managed tasks, opening pull requests, or changing lifecycle status. Scan state and intermediate evidence SHALL be machine-local/ignored by default.

#### Scenario: Scan produces findings
- **WHEN** Map/Reduce identifies one or more candidate improvements
- **THEN** each finding preserves bounded source evidence and provenance to its scan candidates/batches
- **AND** the reduced report may deduplicate and prioritize findings
- **BUT** no repository or backlog mutation is authorized solely by the finding.

#### Scenario: Human accepts a finding
- **WHEN** a human explicitly chooses one or more scan findings for implementation
- **THEN** that accepted work enters the ordinary quick-task or managed-task/OpenSpec lifecycle according to its scope
- **AND** the scan remains evidence/provenance rather than a competing implementation task list.

### Requirement: Shipped capability eval fixtures are consistent and continuously evaluated

Every eval fixture shipped in `dev-platform/evals/` and `template/dev-platform/evals/` SHALL bind by `content_sha256` to the current canonical descriptor of its capability and SHALL evaluate successfully against it. The source and template fixture sets SHALL be identical. A repository-owned regression check SHALL evaluate every shipped fixture against its descriptor so that a stale binding or a source/template divergence fails platform validation with an explicit error naming the fixture.

#### Scenario: Fixture binds to a changed descriptor
- **WHEN** a capability's instructions or descriptor hash changes and its shipped fixture still carries the previous `content_sha256`
- **THEN** the regression check fails and names the fixture and the hash mismatch
- **AND** the direct `capability_manager.py evaluate` path reports the same mismatch instead of running the fixture

#### Scenario: Shipped fixtures are current
- **WHEN** the regression check runs on a consistent source tree
- **THEN** every fixture in both `dev-platform/evals/` and `template/dev-platform/evals/` evaluates against its descriptor with the fixture runtime
- **AND** the add-intents fixture evaluates successfully

#### Scenario: Source and template fixtures diverge
- **WHEN** a fixture file differs in content, or exists in only one of the two trees
- **THEN** the regression check fails naming the fixture
- **AND** no fixture is skipped or silently repaired
