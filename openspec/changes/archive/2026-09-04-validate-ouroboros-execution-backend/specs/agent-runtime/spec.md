## ADDED Requirements

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
