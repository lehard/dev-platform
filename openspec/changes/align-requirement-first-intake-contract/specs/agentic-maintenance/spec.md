# agentic-maintenance Specification Delta

## MODIFIED Requirements

### Requirement: Process review does not create managed work

Process/friction issues SHALL remain evidence and advisory maintenance input. Neither triage nor periodic review SHALL create a Business Requirement, technical managed task, OpenSpec package, implementation PR, or Development Backlog lifecycle state. Later explicit human fixation MAY create a Business Requirement under the requirement-first intake contract; execution requires a subsequent or simultaneous execution instruction.

#### Scenario: Review finds a process issue ready for remediation

- **WHEN** triage or weekly review identifies a likely reusable fix
- **THEN** the workflow may explain the recommendation in bounded process output
- **AND** no Backlog task is created automatically
- **AND** a later generic fixation request creates or reuses a Business Requirement without technical authoring

### Requirement: Process review clusters symptoms before recommending work

The periodic review SHALL reason about likely root causes across the bounded evidence set and SHALL report a smaller set of candidate managed changes when multiple issues appear to be symptoms of one cause. Issue count SHALL NOT be treated as required-change count.

#### Scenario: Several issues share one likely root cause

- **WHEN** the review finds strong evidence that several process issues describe different symptoms of one underlying platform defect
- **THEN** it groups them into one bounded root-cause candidate
- **AND** cites the contributing issue numbers
- **AND** generic human fixation creates or reuses a Business Requirement; technical managed work starts only with execution or explicit direct technical intent
