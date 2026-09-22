# platform-health-review Specification

## Purpose
Define the automated, cloud-native "Platform Health Review" that runs Dev Platform's existing advisory review capabilities together on one combined trigger and durable reporting/notification surface, without requiring a running local computer or a standing server.

## Requirements

### Requirement: Process and Architecture Health Review run together on one combined trigger

Dev Platform SHALL provide a `platform-health-review` capability that triggers Process Health Review and Architecture Health Review together, on one configured schedule and one manual dispatch, independent of any running local developer computer. Each review SHALL keep its own existing engine, read-only tools, safe-outputs declaration, and cost/runtime guardrails unchanged; this capability only aligns their trigger. This capability SHALL be enabled and validated only in `lehard/dev-platform` until a separate, explicitly approved change extends it to managed downstream repositories.

#### Scenario: Scheduled combined run

- **WHEN** the configured schedule triggers the combined Platform Health Review
- **THEN** both Process Health Review and Architecture Health Review run for that trigger event
- **AND** each produces its own existing bounded advisory output unchanged

#### Scenario: Manually dispatched combined run

- **WHEN** a human triggers the combined Platform Health Review's manual dispatch
- **THEN** both reviews run on demand for that event
- **AND** neither review performs repository or backlog mutation beyond its own declared safe outputs

#### Scenario: One review fails independently

- **GIVEN** a combined trigger event has started both reviews
- **WHEN** one review fails or is unavailable
- **THEN** the other review's run and its own safe output are not blocked by that failure

#### Scenario: Central pilot precedes downstream rollout

- **WHEN** the combined trigger is validated in `lehard/dev-platform`
- **THEN** managed consumer repositories do not receive the combined trigger until a separate follow-up change is approved
