## ADDED Requirements

### Requirement: Atomic-judgment pilots do not gain gating or write authority

Dev Platform SHALL NOT let a candidate decision-layer pilot, or any of its backends (including System One/Jev), gate, block, or auto-approve a managed-task action, gain write access to any repository or worktree, or become a required Dev Platform runtime dependency, solely from the pilot's own evaluation output.

#### Scenario: Pilot judgment attempts to influence a live action

- **GIVEN** an atomic-judgment pilot backend produces a verdict for a completed managed run
- **WHEN** that verdict is available
- **THEN** it SHALL NOT be used to gate, block, or auto-approve any live publication, merge, retry, or routing decision
- **AND** no pilot backend receives write access to any repository or worktree

#### Scenario: Confidence alone is insufficient

- **GIVEN** a judgment carries a high-confidence score from any backend
- **WHEN** a dangerous action would otherwise require human or deterministic authorization
- **THEN** the confidence score alone SHALL NOT substitute for that authorization

### Requirement: Judgment evaluation separates deterministic ground truth from model judgment

For each judgment in the taxonomy, the pilot SHALL classify it as deterministic-checkable (established directly, for example by tests, file existence, exit status, exact version, or changed paths) or model-judged (a genuinely ambiguous semantic property). A deterministic-checkable judgment SHALL NOT be scored using any model backend's output as its source of truth. Reference verdicts SHALL be recorded independently of the backend under evaluation, and an unlabelable case SHALL be recorded as `unknown/not-labelable` rather than a fabricated ground truth.

#### Scenario: Deterministic judgment reuses existing evidence

- **GIVEN** a judgment can be established directly from test results, file existence, exit status, an exact version, or changed paths
- **WHEN** the pilot benchmark scores that judgment
- **THEN** the deterministic/rule result is treated as ground truth
- **AND** no model backend's output for that judgment is treated as authoritative

#### Scenario: No ground truth is invented

- **GIVEN** a replay case has no reliable independent reference for a judgment
- **WHEN** the benchmark records that judgment's outcome
- **THEN** it is recorded as `unknown/not-labelable`
- **AND** no backend's own output is substituted as ground truth

### Requirement: Decision-layer pilots end in one explicit bounded decision with error classes reported separately

A completed atomic-judgment decision-layer pilot SHALL record exactly one current decision: `proceed-to-shadow`, `watch-only`, or `reject-for-now`. The report SHALL report false-allow/false-safe errors as a metric distinct from false-escalation errors and SHALL NOT average them into a single accuracy figure. The decision SHALL NOT itself enable live gating, change verification/publication/routing policy, or authorize downstream rollout.

#### Scenario: Pilot records its bounded decision

- **GIVEN** reference verdicts and comparison-arm results are available for the replay cases
- **WHEN** the pilot is completed
- **THEN** exactly one of `proceed-to-shadow`, `watch-only`, or `reject-for-now` is recorded with its evidence
- **AND** false-allow/false-safe error counts are reported separately from false-escalation error counts
- **AND** no live gating, verification/publication/routing change, or downstream rollout is performed by the pilot

#### Scenario: Dangerous false-allow blocks proceed-to-shadow

- **GIVEN** the pilot observes a false-allow/false-safe error on a labelable case
- **WHEN** the decision is recorded
- **THEN** the decision SHALL NOT be `proceed-to-shadow` unless that error class is explicitly evaluated and found acceptable
- **AND** the report identifies the concrete false-allow cases observed
