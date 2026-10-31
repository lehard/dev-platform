## MODIFIED Requirements

### Requirement: External runtime adoption is gated by bounded compatibility evidence

Dev Platform SHALL NOT promote an external agent runtime toward the default execution path solely from upstream capability claims, architecture similarity, or the success signal of the candidate runtime itself.

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

### Requirement: Compatibility pilots end in one explicit bounded decision

A completed external-runtime compatibility pilot SHALL record exactly one current decision: `adopt-next-step`, `watch-only`, or `reject-for-now`.

#### Scenario: Pilot records its bounded decision

- **GIVEN** the candidate runtime replay evidence and independent Dev Platform acceptance results are available
- **WHEN** the compatibility pilot is completed
- **THEN** exactly one of `adopt-next-step`, `watch-only`, or `reject-for-now` is recorded with the required evidence
- **AND** native execution remains the production default
- **AND** no downstream runtime switch or rollout is performed by the pilot

## ADDED Requirements

### Requirement: Compatibility pilots preserve Dev Platform lifecycle authority

A compatibility pilot SHALL preserve Dev Platform authority over managed task identity, the canonical OpenSpec contract, assigned workspace ownership, verification/acceptance, publication and final lifecycle completion.

#### Scenario: Compatibility pilot runs

- **WHEN** a compatibility pilot runs an external agent runtime
- **THEN** Dev Platform keeps authority over managed task identity, the canonical OpenSpec contract and assigned workspace ownership
- **AND** Dev Platform keeps authority over verification/acceptance, publication and final lifecycle completion

### Requirement: Candidate-runtime artifacts do not become a source of truth

Candidate-runtime specifications or session state MAY be generated as bounded execution artifacts, but SHALL NOT become an independently maintained source of truth.

#### Scenario: Candidate runtime generates specifications

- **WHEN** candidate-runtime specifications or session state are generated
- **THEN** they are bounded execution artifacts
- **AND** they do not become an independently maintained source of truth

### Requirement: Compatibility pilot decision evidence identifies the evaluated facts

The decision evidence SHALL identify the exact candidate version/commit, replay cases, Dev Platform acceptance outcomes, observed human intervention/coupling, available comparable efficiency evidence, and the concrete maintenance substitution opportunity or its absence.

#### Scenario: Pilot decision evidence is recorded

- **WHEN** a compatibility pilot decision is recorded
- **THEN** its evidence identifies the exact candidate version/commit, replay cases and Dev Platform acceptance outcomes
- **AND** it identifies observed human intervention/coupling, available comparable efficiency evidence, and the concrete maintenance substitution opportunity or its absence

### Requirement: A compatibility pilot decision does not itself change production

The decision SHALL NOT itself switch the production runtime, remove the native path, change downstream routing, or authorize unrelated candidate features.

#### Scenario: Pilot decision is recorded

- **WHEN** a compatibility pilot decision is recorded
- **THEN** the decision does not itself switch the production runtime, remove the native path or change downstream routing
- **AND** it does not authorize unrelated candidate features
