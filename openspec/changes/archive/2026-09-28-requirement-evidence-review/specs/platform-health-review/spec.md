# platform-health-review Specification Delta

## ADDED Requirements

### Requirement: Process Health Review includes the full Requirement-first path

The existing advisory Process Health Review SHALL inspect bounded relevant process evidence from Business Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery, including Requirement-level retrospective findings. It SHALL group related symptoms with managed task, PR/lifecycle and open process issue context by likely root cause. Specialized review findings SHALL use the same process evidence mechanism and SHALL not create parallel improvement backlogs. The review SHALL remain read-only and SHALL not create accepted work until a human explicitly decides to fix it.

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
