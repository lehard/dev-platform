# architecture-health Specification Delta

## ADDED Requirements

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
