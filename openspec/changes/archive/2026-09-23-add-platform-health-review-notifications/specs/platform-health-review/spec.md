# platform-health-review Specification Delta

## ADDED Requirements

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
