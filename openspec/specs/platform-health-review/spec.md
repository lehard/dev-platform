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

### Requirement: Platform Health Review supports optional external notification

Dev Platform SHALL support notifying a human when a new Platform Health Review report is published, through GitHub (the report Issue itself, always present) and, optionally, Telegram and a generic outbound webhook. Notification content SHALL be limited to a short summary and a link to the report Issue, and SHALL NOT duplicate the full report. Any external channel secret SHALL be supplied only through GitHub Actions repository secrets and SHALL NOT be written into `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other portable or public project configuration file. Notification delivery SHALL run as a separate, deterministic, non-agentic step outside the sandboxed review job.

#### Scenario: Configured channel receives a notification

- **GIVEN** a Telegram or webhook secret is configured for the repository
- **WHEN** a Platform Health Review report is published
- **THEN** exactly one short notification containing a summary and the report Issue link is sent to that channel
- **AND** the notification does not contain the full report body

#### Scenario: Unconfigured channel is skipped

- **GIVEN** no secret is configured for a given optional channel
- **WHEN** a Platform Health Review report is published
- **THEN** that channel is silently skipped
- **AND** GitHub remains fully sufficient as the base channel with no error raised

#### Scenario: One channel's delivery fails

- **GIVEN** more than one optional channel is configured
- **WHEN** delivery to one channel fails
- **THEN** delivery to the other configured channel still proceeds independently
- **AND** the already-published report Issue is unaffected

#### Scenario: Secret never enters portable configuration

- **WHEN** a channel is enabled for a repository
- **THEN** its non-secret enablement setting may live in ordinary project-owned configuration
- **AND** its secret value is never present in `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other tracked portable/public project file
