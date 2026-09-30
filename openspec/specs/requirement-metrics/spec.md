# requirement-metrics Specification

## Purpose
Give a read-only, source-traceable end-to-end view of how a Business Requirement was delivered, including the cost of mandatory independent review, composed from existing lifecycle evidence without a second state store or a composite score.

## Requirements

### Requirement: A Requirement has a read-only end-to-end metrics report

Dev Platform SHALL provide a repository-owned read-only command that reports one Business Requirement's end-to-end execution from existing sources: the Requirement and its linked children, pre-authoring evidence, managed provenance, routing/execution records, verification and automated-check evidence, independent review evidence, PR/publication and CI state, the local friction log and supported runtime-local session signals. The command SHALL NOT write files, caches, logs, remote comments, labels, Project fields or git refs.

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

For each child, the report SHALL reconstruct independent review rounds from the published history of the change's review evidence and show per round the reviewer launches, per-perspective reviewer provider/model with its source, wall time, findings by severity and dispositions. Each rerun SHALL be classified as a substantive candidate change, an unavailable reviewer, or another process rerun, and the report SHALL show full-validation and CI cycles that followed the first review round. Round counts reconstructed from published history SHALL be partial.

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

Where a runtime keeps reliable local session records, the report MAY include session-quality counters attributed to the Requirement by exact child branch or exact reference: prompt turns, interruptions, tool rejections, tool errors, re-prompts after an interruption or rejection, session and active time, and runtime-local usage. The report SHALL output only counts, durations, identifiers and attribution method, never prompts, responses, transcript text or tool payloads. An unsupported runtime or unrecognized format SHALL be unknown. Signals from different runtimes SHALL NOT be combined as if comparable.

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
