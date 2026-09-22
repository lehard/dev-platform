# platform-health-review Specification Delta

## ADDED Requirements

### Requirement: Platform Health Review publishes one combined durable report

Each Platform Health Review run SHALL publish exactly one dated, human-readable GitHub Issue report combining Process Health Review and Architecture Health Review findings, recording `reviewed_at`, the exact current `main` SHA, and the previous-review boundary. The report SHALL replace the prior same-prefix report rather than accumulating duplicates, and SHALL remain strictly advisory: it SHALL NOT mutate any source backlog issue beyond what each individual review's existing rules already allow, and SHALL NOT create a managed task, publish a `managed-openspec:v1` package, or materialize OpenSpec.

#### Scenario: Combined run produces one report

- **WHEN** a Platform Health Review run completes
- **THEN** exactly one dated report Issue is created or updated containing both a process section and an architecture section
- **AND** the report records `reviewed_at`, the exact current `main` SHA, and the previous-review boundary

#### Scenario: Repeat run replaces the prior report

- **GIVEN** a prior combined report Issue exists
- **WHEN** a new Platform Health Review run completes
- **THEN** the new report replaces the prior one under the same fixed title prefix
- **AND** no duplicate report Issue accumulates

#### Scenario: One review's section is unavailable

- **GIVEN** one of the two reviews failed or did not run for this trigger event
- **WHEN** the combined report is produced
- **THEN** the report explicitly states that section did not run
- **AND** the available section's findings are still reported
