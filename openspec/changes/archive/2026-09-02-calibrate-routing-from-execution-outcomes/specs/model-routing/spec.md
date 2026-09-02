## ADDED Requirements

### Requirement: Routing calibration reuses the existing execution baseline evidence path

The platform SHALL support bounded read-only calibration of the current R2/R3 routing rubric from existing managed-task routing/execution records and verification evidence. Calibration SHALL reuse the current routing-record/baseline scanning path and SHALL NOT introduce a parallel execution database, tracing backend, transcript store or calibration state machine.

Routing-calibration eligibility SHALL be based on the routing facts needed for the decision, independently from whether optional efficiency fields such as token usage or a cross-runtime request counter are comparable.

#### Scenario: Verified execution lacks comparable efficiency usage

- **GIVEN** a managed execution has truthful authored routing data, actual route/outcome and verification evidence
- **AND** token/request usage is unavailable or not cross-runtime comparable
- **WHEN** routing calibration evaluates the execution
- **THEN** the execution may still contribute routing-outcome evidence
- **AND** unavailable efficiency metadata remains unknown rather than excluding an otherwise usable routing outcome

### Requirement: Calibration distinguishes authored route from actual execution outcome

For each usable execution, calibration SHALL preserve authored start tier and rubric/task-family context where present, actual execution/fallback/escalation path, verification outcome, and provider/model source status where provable. Missing fields SHALL remain missing or unknown.

#### Scenario: Authored R2 completes without frontier escalation

- **GIVEN** an authored `R2` execution completes required verification without `R3` escalation
- **WHEN** calibration aggregates outcomes
- **THEN** it contributes positive evidence for the current R2 path in its recorded context
- **AND** it is counted separately from direct R3 executions and escalated executions

#### Scenario: R2 escalates and then succeeds

- **GIVEN** an authored `R2` execution has a real R2 attempt
- **AND** the path later escalates to `R3` and completes successfully
- **WHEN** calibration aggregates outcomes
- **THEN** the initial R2 path and final success remain distinguishable
- **AND** an escalation reason is reported only when the existing provenance proves it

#### Scenario: Legacy or partial record

- **GIVEN** a historical routing record lacks an authored tier, model confirmation, escalation reason or another optional field
- **WHEN** calibration reads it
- **THEN** supported facts may still contribute to compatible counts
- **AND** missing values are not converted to defaults or guesses

### Requirement: Calibration avoids unsupported counterfactual claims

Calibration SHALL NOT infer that `R3` was necessary merely because a direct R3 execution succeeded. It SHALL NOT label a direct R3 execution as over-routing without additional counterfactual evidence. Counterfactual replay is not required for the first calibration version.

#### Scenario: Direct frontier execution succeeds

- **GIVEN** a task was authored and executed directly as `R3`
- **WHEN** calibration analyzes the result
- **THEN** it is recorded as successful direct R3 execution
- **AND** the report does not claim that R2 would have failed or succeeded

### Requirement: Calibration exposes routing-specific sample adequacy and tradeoffs

The calibration report SHALL always expose observation counts and coverage and SHALL include at least:

- authored tier distribution and frontier exposure;
- verified R2 success without R3 escalation;
- R2-to-R3 escalation rate/path and known reason distribution;
- success after escalation;
- fallback/abnormal/unknown outcome counts;
- verification, first-pass and human-intervention signals only where current evidence supports them truthfully.

Breakdowns by task family, rubric version and provider/model generation SHALL include their own sample counts and SHALL NOT be presented as confident tuning evidence when the corresponding sample is insufficient.

#### Scenario: Global sample is usable but one family is small

- **GIVEN** the overall routing sample is adequate for a bounded global review
- **AND** one task family has too few usable executions
- **WHEN** the report renders breakdowns
- **THEN** the global report may be usable
- **AND** the small family is explicitly marked insufficient for family-specific policy advice

#### Scenario: Current real sample is insufficient

- **GIVEN** the current verified routing sample lacks adequate coverage
- **WHEN** the first calibration report is produced
- **THEN** the report returns `insufficient evidence / no policy change`
- **AND** implementation of the reporting capability is not considered blocked merely because more executions must accumulate

### Requirement: Calibration remains advisory

Calibration MAY produce a human-readable candidate decision to keep or change rubric rules, hard triggers, effort/assurance defaults or model mapping. Any actual policy change SHALL require a separate explicit reviewed managed change.

Calibration SHALL NOT automatically modify routing policy, enable R1, create Development Backlog tasks, dispatch remediation, or introduce a learned router.

#### Scenario: Report recommends a rubric change

- **GIVEN** the calibration report has adequate evidence to suggest a concrete rubric or hard-trigger adjustment
- **WHEN** the report is produced
- **THEN** it states the candidate change as human-readable advice only
- **AND** it does not edit routing policy files, `.dev-platform.toml`, the rubric or model mapping
- **AND** it does not create a Development Backlog task, dispatch remediation or enable a learned router

#### Scenario: Evidence supports keeping the current policy

- **GIVEN** the calibration report finds no change is warranted or the sample is insufficient
- **WHEN** the report is produced
- **THEN** it records `no change` or `insufficient evidence / no policy change` as advisory output
- **AND** any later policy change still requires a separate explicit reviewed managed change
