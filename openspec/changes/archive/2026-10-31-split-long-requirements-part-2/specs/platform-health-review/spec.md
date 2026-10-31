## MODIFIED Requirements

### Requirement: Platform Health Review supports optional external notification

Dev Platform SHALL support notifying a human when a new Platform Health Review report is published, through GitHub (the report Issue itself, always present) and, optionally, Telegram and a generic outbound webhook.

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

### Requirement: Platform Health Review findings are classified in Russian

Each finding in the existing Platform Health Review outputs SHALL have exactly one primary category: «Подтверждённый дефект», «Риск надёжности», «Возможность упрощения», «Техническая гигиена» or «Наблюдение».

#### Scenario: Review reports a finding

- **WHEN** either review reports an evidence-backed finding
- **THEN** the finding has one Russian category, confidence and status
- **AND** structural evidence lenses or work-state groupings do not replace those fields

#### Scenario: Combined report contains findings

- **WHEN** either private source review reports classified findings
- **THEN** the combined report Issue shows a short bounded excerpt with category, confidence, and status for each included finding
- **AND** links to the full source report without a score or duplicate reporting store

### Requirement: Process Health Review includes the full Requirement-first path

The existing advisory Process Health Review SHALL inspect bounded relevant process evidence from Business Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery, including Requirement-level retrospective findings.

#### Scenario: Early or cross-child finding with clean technical children

- **GIVEN** a meaningful pre-materialization or cross-child process finding is recorded on the Requirement path
- **AND** every technical child completes cleanly
- **WHEN** the next bounded Process Health Review examines relevant evidence
- **THEN** the finding remains visible with its Requirement context and is considered in likely root-cause grouping
- **AND** clean child status does not suppress it

#### Scenario: Specialized review supplies process evidence

- **WHEN** architecture, routing, validation, or capability review identifies meaningful process friction
- **THEN** that evidence may enter the existing friction/process-issue mechanism
- **AND** Process Health Review does not create a second improvement lifecycle

## ADDED Requirements

### Requirement: Platform Health Review notification content is a summary and a link

Platform Health Review notification content SHALL be limited to a short summary and a link to the report Issue, and SHALL NOT duplicate the full report.

#### Scenario: Notification is composed

- **WHEN** a Platform Health Review notification is composed
- **THEN** its content is a short summary and a link to the report Issue
- **AND** it does not duplicate the full report

### Requirement: Platform Health Review notification secrets stay in repository secrets

Any Platform Health Review external notification channel secret SHALL be supplied only through GitHub Actions repository secrets and SHALL NOT be written into `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other portable or public project configuration file.

#### Scenario: External channel is configured

- **WHEN** a Platform Health Review external notification channel needs a secret
- **THEN** the secret is supplied only through GitHub Actions repository secrets
- **AND** it is not written into `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other portable or public project configuration file

### Requirement: Platform Health Review notification delivery runs outside the review job

Platform Health Review notification delivery SHALL run as a separate, deterministic, non-agentic step outside the sandboxed review job.

#### Scenario: Notification is delivered

- **WHEN** a Platform Health Review notification is delivered
- **THEN** delivery runs as a separate, deterministic, non-agentic step outside the sandboxed review job

### Requirement: Platform Health Review findings carry a Russian confidence and status

The confidence of each finding in the existing Platform Health Review outputs SHALL be «высокая», «средняя» or «низкая» and its status SHALL be «новый», «сохраняется», «уже в работе», «вероятно устранён» or «наблюдать».

#### Scenario: Finding is reported with confidence and status

- **WHEN** a Platform Health Review output reports a finding
- **THEN** its confidence is «высокая», «средняя» or «низкая»
- **AND** its status is «новый», «сохраняется», «уже в работе», «вероятно устранён» or «наблюдать»

### Requirement: The Platform Health Review report stays concise without a health score

The Platform Health Review report SHALL stay concise and SHALL NOT introduce a single health score.

#### Scenario: Report is produced

- **WHEN** a Platform Health Review report is produced
- **THEN** it stays concise
- **AND** it introduces no single health score

### Requirement: The combined Platform Health Review report Issue shows bounded excerpts

The existing combined Platform Health Review report Issue SHALL show a bounded excerpt of classified findings from each available private source report and link to the full source reports.

#### Scenario: Combined report Issue is published

- **WHEN** the combined Platform Health Review report Issue is published
- **THEN** it shows a bounded excerpt of classified findings from each available private source report
- **AND** it links to the full source reports

### Requirement: Missing Platform Health Review excerpts are shown as unavailable

Missing or malformed classified-finding excerpts in the existing combined Platform Health Review report Issue SHALL be shown as unavailable, rather than silently treated as no findings.

#### Scenario: Excerpt is missing or malformed

- **WHEN** a source report's excerpt for the combined Platform Health Review report Issue is missing or malformed
- **THEN** the excerpt is shown as unavailable
- **AND** it is not silently treated as no findings

### Requirement: Process Health Review groups symptoms by likely root cause

The existing advisory Process Health Review SHALL group related symptoms with managed task, PR/lifecycle and open process issue context by likely root cause.

#### Scenario: Related symptoms are found

- **WHEN** the Process Health Review finds related symptoms
- **THEN** it groups them with managed task, PR/lifecycle and open process issue context by likely root cause

### Requirement: Specialized review findings use the Process Health Review evidence mechanism

Specialized review findings SHALL use the same process evidence mechanism as the existing advisory Process Health Review and SHALL not create parallel improvement backlogs.

#### Scenario: Specialized review reports findings

- **WHEN** a specialized review produces findings
- **THEN** they use the same process evidence mechanism as the Process Health Review
- **AND** they create no parallel improvement backlog

### Requirement: Process Health Review stays read-only

The existing advisory Process Health Review SHALL remain read-only and SHALL not create accepted work until a human explicitly decides to fix it.

#### Scenario: Review identifies a problem

- **WHEN** the Process Health Review identifies a problem
- **THEN** it remains read-only
- **AND** no accepted work exists until a human explicitly decides to fix it
