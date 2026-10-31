# platform-health-review Specification

## Purpose
Define the automated, cloud-native "Platform Health Review" that runs Dev Platform's existing advisory review capabilities together on one combined trigger and durable reporting/notification surface, without requiring a running local computer or a standing server.

## Requirements

### Requirement: Process and Architecture Health Review run together on one combined trigger

Dev Platform SHALL run the combined scheduled and manually dispatched Platform Health Review in the private caller repository. The review SHALL read only the bounded public platform and private Backlog evidence needed by its existing process and architecture lenses. The public `lehard/dev-platform` repository SHALL NOT run a complete combined review that reads private Backlog data. The combined review remains advisory and does not create managed work or mutate source evidence.

#### Scenario: Scheduled combined run

- **WHEN** the private combined review is triggered on its schedule
- **THEN** its jobs, logs, artifacts, and full report remain in the private caller repository
- **AND** no private task information is emitted to a public `dev-platform` output surface

#### Scenario: Manually dispatched combined run

- **WHEN** a human manually triggers the combined review in the private caller repository
- **THEN** both reviews run in that private repository and remain advisory

#### Scenario: One review fails independently

- **WHEN** one review job fails or is unavailable
- **THEN** the other review still runs and its findings remain available for the private combined report

#### Scenario: Central pilot precedes downstream rollout

- **WHEN** the private combined trigger is validated for the Dev Platform pilot
- **THEN** managed consumer repositories do not receive it without separate approval

### Requirement: Platform Health Review publishes one combined durable report

Each run SHALL publish exactly one dated, combined, human-readable Issue in the private caller repository, replacing the prior same-prefix report. The report SHALL record the reviewed platform `main` SHA, review time, previous boundary, and whether private evidence was available. The public repository SHALL NOT publish a second full report or store private task information.

#### Scenario: Combined run produces one report

- **GIVEN** private evidence and both review jobs are available
- **WHEN** the private run completes
- **THEN** one complete combined report appears only as a private Backlog Issue

#### Scenario: Repeat run replaces the prior report

- **GIVEN** a prior same-prefix combined report exists in the private Backlog
- **WHEN** a new review run completes
- **THEN** the new private report replaces the prior report without accumulating duplicates

#### Scenario: Missing private access

- **GIVEN** GitHub App credentials, installation scope, or private Issues read access is absent
- **WHEN** the run executes
- **THEN** the private report explicitly says `degraded` and names the unavailable evidence category without exposing secrets
- **AND** it does not claim a complete audit or send private content to the public repository

#### Scenario: One review's section is unavailable

- **WHEN** one bounded review job fails
- **THEN** the private combined report marks that section unavailable and does not claim complete status

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

### Requirement: Private Backlog access uses a minimally scoped GitHub App token

The private workflow SHALL mint a short-lived GitHub App installation token for only the repositories and read permissions needed to inspect its bounded evidence. Report writing SHALL use a separate private-repository-scoped credential. Long-lived PATs and public-run access to private task data SHALL NOT be required.

#### Scenario: Token scope

- **WHEN** the private run prepares review credentials
- **THEN** its App read token is restricted to `dev-platform` and the private caller repository and only required read permissions
- **AND** report publishing is restricted to the private caller repository

#### Scenario: Credentials unavailable

- **WHEN** required App credentials are not configured
- **THEN** the run takes the explicit degraded path without running an agent against incomplete Backlog evidence

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

### Requirement: New-work recommendations use current context

Before recommending new work, each review SHALL inspect the relevant existing Backlog and recent merged changes against current platform evidence. A known, active, or likely resolved problem SHALL not be presented as a new finding needing new work. Incomplete access or inconclusive evidence SHALL be reported as uncertainty. The review SHALL remain advisory/read-only and SHALL NOT create Requirements, managed tasks, or fixes.

#### Scenario: Existing or recently fixed problem

- **WHEN** a finding matches existing Backlog work or a recent fix
- **THEN** the review labels its current status from the allowed Russian values and cites the supporting evidence
- **AND** it does not recommend duplicate new work

#### Scenario: Evidence is unavailable

- **WHEN** the review cannot verify relevant Backlog or recent-change context
- **THEN** it states the limitation and does not call the candidate new work

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
