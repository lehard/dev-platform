# platform-health-review Specification Delta

## ADDED Requirements

### Requirement: Platform Health Review findings are classified in Russian

Each finding in the existing Platform Health Review outputs SHALL have exactly one primary category: «Подтверждённый дефект», «Риск надёжности», «Возможность упрощения», «Техническая гигиена» or «Наблюдение». Its confidence SHALL be «высокая», «средняя» or «низкая» and its status SHALL be «новый», «сохраняется», «уже в работе», «вероятно устранён» or «наблюдать». The report SHALL stay concise and SHALL NOT introduce a single health score.

The existing combined report Issue SHALL show a bounded excerpt of classified findings from each available private source report and link to the full source reports. Missing or malformed excerpts SHALL be shown as unavailable, rather than silently treated as no findings.

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
