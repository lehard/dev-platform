# requirement-metrics Specification

## Purpose
Give a read-only, source-traceable end-to-end view of how a Business Requirement was delivered, including the cost of mandatory independent review, composed from existing lifecycle evidence without a second state store or a composite score.

## Requirements

### Requirement: A Requirement has a read-only end-to-end metrics report

Dev Platform SHALL provide a repository-owned read-only command that reports one Business Requirement's end-to-end execution from existing sources: the Requirement and its linked children, pre-authoring evidence, managed provenance, routing/execution records, verification and automated-check evidence, independent review evidence, PR/publication and CI state, the local friction log and supported runtime-local session signals.

#### Scenario: Completed Requirement is reported without manual input
- **GIVEN** a completed Requirement with at least one delivered child
- **WHEN** an agent runs the report command for it
- **THEN** the report shows cycle time and observed stage timestamps, children, per-child start tier and task family, supervisor/executor provenance, escalations, verification and full-validation cycles, PR/publication cycles, CI runs and CI wall time, friction occurrences and recorded human stops
- **AND** no value requires manual input from the agent

#### Scenario: A remote source is unavailable
- **GIVEN** GitHub cannot be reached or the command runs offline
- **WHEN** the report is produced
- **THEN** only the sections that depend on the unavailable source are unknown, with a reason
- **AND** local sections are still reported

### Requirement: Report values are traceable and never fabricate missing evidence

Every reported value SHALL carry a status (`measured`, `derived`, `partial` or `unknown`) and references to the existing sources it came from. Missing, unreadable, incompatible or historical-without-field evidence SHALL be unknown, and a lower bound or incomplete coverage SHALL be partial. The report SHALL NOT substitute zero or an estimate for unknown evidence, and SHALL NOT select an unrelated record when the exact one is missing.

#### Scenario: A historical record lacks a field
- **WHEN** a routing record or review report predates a field the report reads
- **THEN** that value is unknown with a reason
- **AND** totals that include it are partial or unknown, never zero

#### Scenario: A child's routing record does not match its identity
- **GIVEN** the routing record for a child's change names a different source Issue
- **WHEN** the report is produced
- **THEN** that child's routing section is unknown rather than filled from the mismatched record

### Requirement: The report exposes the cost of mandatory independent review

For each child, the report SHALL reconstruct independent review rounds from the published history of the change's review evidence and show per round the reviewer launches, per-perspective reviewer provider/model with its source, wall time, findings by severity and dispositions.

#### Scenario: A review is rerun after a candidate fix
- **GIVEN** two review rounds whose task-owned content digests differ
- **WHEN** the report is produced
- **THEN** the second round is classified as a substantive candidate change

#### Scenario: A review is rerun without a candidate change
- **GIVEN** two review rounds with the same task-owned content digest
- **WHEN** the earlier round had an unavailable perspective
- **THEN** the rerun is classified as reviewer-unavailable
- **AND** otherwise it is classified as a process rerun

### Requirement: Runtime session signals are counters only and runtime-specific

Where a runtime keeps reliable local session records, the report MAY include session-quality counters attributed to the Requirement by exact child branch or exact reference: prompt turns, interruptions, tool rejections, tool errors, re-prompts after an interruption or rejection, session and active time, and runtime-local usage. The report SHALL output only counts, durations, identifiers and attribution method, never prompts, responses, transcript text or tool payloads.

#### Scenario: Codex session signals are requested
- **WHEN** the report covers work executed through a runtime without a supported session adapter
- **THEN** its session signals are unknown with reason unsupported-runtime

#### Scenario: Session text never leaves the adapter
- **WHEN** the Claude Code adapter reads attributed transcript entries
- **THEN** the report contains only counters, durations, session ids and the attribution method

### Requirement: Requirements can be compared without a composite score

The command SHALL aggregate several Requirements side by side with their headline end-to-end totals. It SHALL group comparable subsets by child count, task family and start tier, and SHALL key runtime/provider-specific usage and session metrics by runtime/provider without summing across keys. Summary statistics SHALL appear only for an adequate sample. The aggregate SHALL NOT produce a productivity index or score and SHALL NOT change routing, decomposition, budgets or lifecycle gates.

#### Scenario: Small sample
- **GIVEN** fewer than five Requirements in a comparison group
- **WHEN** the aggregate is produced
- **THEN** the group shows its rows and count with insufficient adequacy instead of medians

#### Scenario: Faster stage but longer path
- **WHEN** one Requirement has a shorter review stage but a longer total cycle or more CI cycles than another
- **THEN** both totals are shown side by side, and no single score hides the trade-off

### Requirement: The Requirement metrics command writes nothing

The repository-owned read-only command that reports one Business Requirement's end-to-end execution SHALL NOT write files, caches, logs, remote comments, labels, Project fields or git refs.

#### Scenario: Metrics command runs

- **WHEN** the Requirement end-to-end metrics command runs
- **THEN** it writes no files, caches, logs, remote comments, labels, Project fields or git refs

### Requirement: Requirement metrics review reruns are classified

In the Requirement end-to-end metrics report, each independent review rerun SHALL be classified as a substantive candidate change, an unavailable reviewer, or another process rerun.

#### Scenario: Independent review is rerun

- **WHEN** the Requirement end-to-end metrics report shows an independent review rerun
- **THEN** the rerun is classified as a substantive candidate change, an unavailable reviewer, or another process rerun

### Requirement: Requirement metrics show cycles after the first review round

The Requirement end-to-end metrics report SHALL show full-validation and CI cycles that followed the first review round.

#### Scenario: Cycles followed the first review round

- **WHEN** full-validation or CI cycles followed the first review round
- **THEN** the Requirement end-to-end metrics report shows them

### Requirement: Requirement metrics reconstructed round counts are partial

In the Requirement end-to-end metrics report, review round counts reconstructed from published history SHALL be partial.

#### Scenario: Round counts come from published history

- **WHEN** the Requirement end-to-end metrics report reconstructs review round counts from published history
- **THEN** those counts are partial

### Requirement: Unsupported runtime session signals are unknown

In the Requirement end-to-end metrics report, an unsupported runtime or unrecognized session record format SHALL be unknown.

#### Scenario: Runtime or format is not supported

- **WHEN** the Requirement end-to-end metrics report meets an unsupported runtime or an unrecognized session record format
- **THEN** its session signals are reported as unknown

### Requirement: Session signals from different runtimes are not combined

In the Requirement end-to-end metrics report, session signals from different runtimes SHALL NOT be combined as if comparable.

#### Scenario: Signals come from several runtimes

- **WHEN** the Requirement end-to-end metrics report has session signals from different runtimes
- **THEN** it does not combine them as if comparable
