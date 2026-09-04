# agent-runtime Specification

## Purpose
TBD - created by archiving change add-deepseek-harness-runtime-adapter. Update Purpose after archive.
## Requirements
### Requirement: Dev Platform may expose optional external agent-runtime backends

The platform MAY provide external agent-runtime backends behind a platform-owned runtime adapter boundary. An optional backend SHALL NOT become the default execution path merely because its dependency is installed.

The runtime boundary SHALL remain subordinate to the existing managed task lifecycle: task identity, OpenSpec contract, assigned workspace/worktree ownership, routing policy, verification, publication and final completion remain Dev Platform responsibilities.

#### Scenario: Experimental backend is installed

- **GIVEN** an external runtime adapter is available
- **WHEN** an ordinary managed task starts without an explicit experimental runtime selection
- **THEN** the current supported native execution path remains authoritative
- **AND** the external backend is not selected automatically

### Requirement: DeepSeek Harness integration is pinned and isolated

The DeepSeek Harness adapter SHALL use an exact tested upstream version selected through implementation preflight and SHALL NOT rely on mutable `master`/`latest` as its production identity.

DSH/Cordis-specific types, session identities, plugin registries and internal lifecycle state SHALL remain encapsulated inside the adapter/profile layer and SHALL NOT become public types or authoritative state in task-intake, OpenSpec, routing-policy, verification, publication or rollout contracts.

#### Scenario: DSH upstream changes incompatibly

- **GIVEN** a newer DSH version changes the supported integration contract
- **WHEN** the platform evaluates that version
- **THEN** compatibility failures are contained to the adapter/version gate
- **AND** current native execution remains usable
- **AND** the new version is not promoted automatically

### Requirement: External runtime execution preserves one lifecycle owner

For an external runtime run, Dev Platform SHALL supply the authorized task workspace and SHALL remain the authority for task status and completion. The runtime MAY own its internal session/tool/subagent lifecycle for the bounded run but SHALL NOT create a competing Backlog/OpenSpec/publication lifecycle.

#### Scenario: DSH run reaches an internal terminal state

- **WHEN** a DSH run returns a successful runtime result
- **THEN** the result is only execution evidence
- **AND** Dev Platform still performs its normal verification/publication lifecycle before the managed task can complete

### Requirement: External runtime containment fails closed

A write-capable external runtime execution SHALL NOT be reported as safely contained unless the platform can prove the required writer/workspace boundary for the actual supported runtime mode. The adapter SHALL expose an actionable distinction between proven, partial/insufficient, and unavailable containment evidence as needed by the caller.

#### Scenario: DSH write containment is not provable

- **GIVEN** the experimental DSH backend is asked to run write-capable work
- **AND** the supported host/runtime cannot prove the required assigned-workspace boundary
- **WHEN** adapter preflight runs
- **THEN** the write-capable run is refused or retained on a safe existing path
- **AND** the platform does not claim a successful contained delegation

### Requirement: External runtime evidence uses the common execution provenance

The DSH adapter SHALL map bounded runtime identity/version, run identity where safe, timing, terminal result/cancellation/cleanup, usage evidence where authoritative, and required containment evidence into the platform's runtime-neutral execution provenance. It SHALL NOT require a parallel execution database or copy the full DSH session/transcript into Dev Platform by default.

Unavailable usage or runtime fields SHALL remain unknown rather than fabricated.

#### Scenario: DSH exposes token usage

- **GIVEN** the supported pinned DSH version returns compatible structured usage
- **WHEN** the adapter finalizes execution evidence
- **THEN** the compatible normalized fields are recorded with truthful source/status
- **AND** DSH-specific event objects are not required by upper lifecycle layers

### Requirement: DeepSeek Harness upgrades are explicit compatibility events

Changing the supported DSH version SHALL require an explicit exact-version update followed by adapter compatibility checks and a bounded safe smoke before the new version is included in a normal Dev Platform release. Automatic upstream discovery MAY notify or propose an update, but SHALL NOT promote it to production without those gates.

#### Scenario: New DSH release is available

- **WHEN** a newer upstream release is discovered
- **THEN** current pinned execution remains unchanged
- **AND** adoption requires a reviewable version bump plus compatibility/smoke evidence
- **AND** downstream runtime behavior changes only through the normal immutable Dev Platform release lifecycle

### Requirement: Initial DSH adapter scope remains deliberately narrow

The first adapter change SHALL NOT make DSH Agent Teams authoritative, migrate project skills/AGENTS into DSH, replace platform-owned planning/verification/publication, remove the native runtime, or make DSH the default. Such changes require separate evidence-based managed decisions.

#### Scenario: Adapter smoke succeeds

- **WHEN** the experimental adapter passes its contract and smoke checks
- **THEN** the result establishes integration capability only
- **AND** it does not by itself authorize a production runtime switch

### Requirement: External runtime adoption is gated by bounded compatibility evidence

Dev Platform SHALL NOT promote an external agent runtime toward the default execution path solely from upstream capability claims, architecture similarity, or the success signal of the candidate runtime itself.

A compatibility pilot SHALL preserve Dev Platform authority over managed task identity, the canonical OpenSpec contract, assigned workspace ownership, verification/acceptance, publication and final lifecycle completion. Candidate-runtime specifications or session state MAY be generated as bounded execution artifacts, but SHALL NOT become an independently maintained source of truth.

#### Scenario: Candidate runtime is evaluated on historical work

- **GIVEN** a completed managed change has a reconstructable pre-change base and accepted task/OpenSpec contract
- **WHEN** an external runtime is evaluated through the platform runtime boundary
- **THEN** the candidate receives the same canonical requirements without manual requirement changes between comparison arms
- **AND** execution occurs only in an isolated pilot workspace
- **AND** the produced result is judged by Dev Platform verification/acceptance rather than candidate self-evaluation alone

#### Scenario: Historical native evidence is already sufficient

- **GIVEN** durable native execution and verification evidence exists for a replay case
- **AND** the evidence is sufficient and semantically comparable for a required decision field
- **WHEN** the pilot builds its comparison
- **THEN** the existing evidence MAY be reused
- **AND** the platform SHALL NOT require a duplicate native model run merely for experimental ceremony
- **AND** any unavailable or incompatible metric remains unknown instead of being inferred

### Requirement: External runtime promotion requires concrete maintenance leverage

A successful compatibility run SHALL NOT by itself authorize further adoption. A next adoption step requires evidence that the candidate is at least acceptably reliable and correct under Dev Platform acceptance, does not introduce a competing canonical task/spec lifecycle or broad runtime-specific coupling, and can eliminate or avoid a meaningful Dev Platform maintenance responsibility.

#### Scenario: Ouroboros replay succeeds without substitution value

- **GIVEN** Ouroboros completes the representative replay cases correctly
- **BUT** integration still requires comparable custom maintenance or no substantial Dev Platform responsibility can be retired
- **WHEN** the pilot decision is recorded
- **THEN** the result is `watch-only` rather than automatic adoption
- **AND** native execution remains the production default

#### Scenario: Candidate requires broad lifecycle coupling

- **GIVEN** supporting the candidate requires its concepts to become authoritative in task-intake, OpenSpec, verification, publication or rollout
- **WHEN** compatibility is evaluated
- **THEN** that coupling is recorded as negative evidence
- **AND** the pilot SHALL stop or return `reject-for-now` rather than silently expanding the candidate's ownership

### Requirement: Compatibility pilots end in one explicit bounded decision

A completed external-runtime compatibility pilot SHALL record exactly one current decision: `adopt-next-step`, `watch-only`, or `reject-for-now`. The decision evidence SHALL identify the exact candidate version/commit, replay cases, Dev Platform acceptance outcomes, observed human intervention/coupling, available comparable efficiency evidence, and the concrete maintenance substitution opportunity or its absence.

The decision SHALL NOT itself switch the production runtime, remove the native path, change downstream routing, or authorize unrelated candidate features.

#### Scenario: Pilot records its bounded decision

- **GIVEN** the candidate runtime replay evidence and independent Dev Platform acceptance results are available
- **WHEN** the compatibility pilot is completed
- **THEN** exactly one of `adopt-next-step`, `watch-only`, or `reject-for-now` is recorded with the required evidence
- **AND** native execution remains the production default
- **AND** no downstream runtime switch or rollout is performed by the pilot

