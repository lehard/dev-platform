# harness-evaluation Specification

## Purpose
TBD - created by archiving change add-harness-replay-lab. Update Purpose after archive.
## Requirements
### Requirement: Harness replay cases are bound to exact historical task identity

Dev Platform SHALL support a small frozen replay suite for platform harness/process evaluation. Each replay case SHALL identify an exact pre-change repository revision, the canonical accepted task/OpenSpec contract applicable to that revision, and independent authoritative verification/reference evidence sufficient to judge the required outcome. A case SHALL NOT rely only on prose reconstructed after the original work completed.

#### Scenario: Historical case is materialized for replay

- **GIVEN** a completed managed task has a reconstructable pre-change revision and accepted canonical contract
- **WHEN** it is added as a replay case
- **THEN** the case records exact source revision and stable case identity/digest
- **AND** preserves independent verification/reference evidence
- **AND** candidate-generated output is not used as its own ground truth

#### Scenario: Frozen case drifts

- **GIVEN** a replay case has been frozen
- **WHEN** its source contract, revision identity or acceptance evidence changes without an explicit case update
- **THEN** replay validation reports case drift
- **AND** the changed case is not silently treated as the original held-out case

### Requirement: Harness optimization evaluation gates capability before efficiency

A candidate harness/process optimization SHALL be judged first against explicit capability/fidelity acceptance criteria and authoritative verification/reference outcomes. Positive efficiency comparison SHALL be performed only for candidates that satisfy the capability gate within the declared tolerance.

#### Scenario: Candidate saves resources but breaks required behavior

- **GIVEN** a candidate uses fewer resources on a replay case
- **BUT** it fails required verification or materially violates the reference acceptance outcome
- **WHEN** evaluation is produced
- **THEN** the candidate fails the capability gate
- **AND** its resource reduction is not reported as a successful optimization

#### Scenario: Candidate preserves required capability

- **GIVEN** a candidate satisfies the declared capability/fidelity gate
- **WHEN** efficiency comparison runs
- **THEN** the report may compare deterministic payload evidence and authoritative runtime token/cache/request, wall-time, cost, retry/escalation or intervention evidence where available and semantically comparable
- **AND** unavailable/incompatible fields remain unknown

### Requirement: Harness replay reuses comparable evidence and avoids ceremonial reruns

Historical native execution/verification evidence MAY be reused when it is durable and semantically comparable to the field being evaluated. The platform SHALL NOT require a duplicate native baseline run solely to make every case symmetrical.

#### Scenario: Durable native baseline already exists

- **GIVEN** a replay case has trustworthy historical native verification and compatible efficiency evidence
- **WHEN** a candidate comparison is prepared
- **THEN** the existing evidence may serve as the native baseline
- **AND** no duplicate native run is required only for ceremony

### Requirement: Harness complexity removal uses the same capability gate

The replay lab SHALL support candidate evaluations that reduce instruction surfaces, load tool or capability definitions on demand, relax explicit explorer/subagent guidance, or change prompt/tool boundaries for cache behavior. Resource savings claims from outside Dev Platform SHALL NOT substitute for local capability/fidelity evidence.

#### Scenario: A shorter harness surface is proposed

- **GIVEN** a candidate removes or defers harness instructions or definitions
- **WHEN** the replay lab evaluates it
- **THEN** the candidate is subject to the same declared capability tolerance and independent verification outcomes
- **AND** efficiency evidence is considered only after that gate passes

### Requirement: Harness replay is isolated and advisory

Replay execution SHALL occur only in isolated disposable workspaces bound to the exact case revision. Replay results SHALL be advisory evidence and SHALL NOT automatically alter production routing, context policy, runtime defaults, releases or Development Backlog state.

#### Scenario: Replay candidate finishes successfully

- **WHEN** a candidate completes all replay gates
- **THEN** the result is recorded as bounded evaluation evidence
- **AND** no production policy, runtime default, release or backlog task is changed by the replay itself

#### Scenario: Replay attempts to mutate historical or integration state

- **WHEN** a replay execution attempts to write outside its isolated disposable workspace
- **THEN** the run fails closed or is rejected as invalid evidence
- **AND** integration/main and historical source truth remain unchanged
