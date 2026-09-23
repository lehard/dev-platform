# architecture-health Specification

## Purpose
Define how the platform evaluates and records architecture health without conflating it with product delivery.

## Requirements

### Requirement: Dev Platform can produce read-only architecture health evidence

Dev Platform SHALL support an advisory architecture review bound to an exact repository revision that reports bounded evidence about module/interface boundaries, locality, coupling, seams and related structural risks without modifying repository or managed-task state.

#### Scenario: Architecture review runs
- **WHEN** an architecture health review is requested for a repository revision
- **THEN** the result identifies the exact revision and evidence-bearing code locations
- **AND** separates observations from uncertainty and proposed improvements
- **AND** performs no repository or backlog mutation

### Requirement: Architecture findings require explicit human promotion

Architecture health findings SHALL remain advisory until a human explicitly accepts a candidate as managed work through the normal task-intake lifecycle.

#### Scenario: Review finds a refactor candidate
- **WHEN** the report identifies a potentially valuable architectural improvement
- **THEN** it does not create a managed task or change code automatically
- **AND** any later accepted work is authored separately through the ordinary managed lifecycle

### Requirement: Alternative design analysis is selective

Dev Platform SHALL permit bounded comparison of materially different design/interface alternatives for high-consequence architecture decisions without requiring that ceremony for ordinary changes.

#### Scenario: Significant interface decision is reviewed
- **WHEN** an explicitly configured architecture trigger requests alternative-design analysis
- **THEN** at least two materially distinct designs can be compared against stated criteria
- **AND** the comparison remains evidence for the existing OpenSpec design decision rather than a competing specification source

### Requirement: Architecture Health Review can run as a bounded cloud/scheduled job

Dev Platform SHALL support running Architecture Health Review as an optional GitHub Agentic Workflows job, triggerable by a configured schedule and by manual dispatch, independent of any running local developer computer. The job SHALL remain read-only over repository/issue content, SHALL declare a bounded runtime and per-run AI-credit budget, and SHALL be enabled and validated only in `lehard/dev-platform` until a separate, explicitly approved change extends it to managed downstream repositories.

#### Scenario: Scheduled cloud run

- **GIVEN** the repository has a valid configured architecture-health-review agentic workflow and Actions secret
- **WHEN** the configured schedule triggers the workflow
- **THEN** GitHub Actions runs the review in the cloud
- **AND** no local daemon, cron, or interactive session is required

#### Scenario: Manually dispatched cloud run

- **WHEN** a human triggers the workflow's manual dispatch
- **THEN** the same read-only, bounded-safe-output review runs on demand
- **AND** it performs no repository or backlog mutation beyond its declared safe outputs

#### Scenario: Guardrail is reached

- **WHEN** a run reaches its configured runtime or AI-credit bound
- **THEN** execution is stopped or constrained by the `gh-aw` guardrail
- **AND** the repository does not silently permit unbounded inference spend

#### Scenario: Central pilot precedes downstream rollout

- **WHEN** the cloud execution surface is validated in `lehard/dev-platform`
- **THEN** managed consumer repositories do not receive the workflow until a separate follow-up change is approved
