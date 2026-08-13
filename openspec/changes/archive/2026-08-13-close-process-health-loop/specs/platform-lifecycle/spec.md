## ADDED Requirements

### Requirement: Managed work carries explicit process-evidence linkage

When a human explicitly fixes accepted process evidence into a managed task, the platform SHALL support an explicit bounded list of source process issues and SHALL preserve that relation in a deterministic task representation readable by the managed lifecycle. Linked source issues SHALL remain evidence records, SHALL stay open while remediation is incomplete, and MAY receive the minimal `process:managed` lifecycle label and one bounded backlink.

#### Scenario: Several symptoms become one managed change

- **GIVEN** several open process issues have been judged symptoms of one root cause
- **WHEN** the human explicitly creates one managed task with those evidence references
- **THEN** the managed task stores each exact source issue reference in its canonical linkage
- **AND** each eligible open evidence issue remains open and is marked as managed without duplicate backlinks
- **AND** no additional managed task is created solely because there are several source issues

#### Scenario: Evidence reference is not eligible

- **WHEN** authoring receives an inaccessible, malformed or non-process issue as explicit evidence
- **THEN** linkage fails with an actionable diagnostic
- **AND** the platform does not silently treat that issue as valid process provenance

### Requirement: Terminal managed success resolves only its linked process evidence

After the existing managed lifecycle establishes terminal delivery success, the platform SHALL reconcile the task's explicit process evidence and close each linked still-open issue with a bounded resolution record. Non-terminal, failed, blocked or cancelled work SHALL NOT be represented as having resolved its evidence.

#### Scenario: Linked managed task completes

- **GIVEN** a managed task has explicit linked process evidence
- **AND** the exact task has reached terminal delivery success under the existing lifecycle
- **WHEN** completion reconciles process evidence
- **THEN** each linked still-open process issue is closed with reason `completed`
- **AND** a bounded resolution note identifies the Development Backlog task and implementation provenance
- **AND** repeating completion produces no duplicate resolution mutation

#### Scenario: Managed task is not terminally successful

- **WHEN** the managed task is blocked, failed, abandoned or otherwise not at terminal success
- **THEN** linked process evidence remains open
- **AND** it is not classified as resolved solely because managed work exists

#### Scenario: Same friction recurs after resolution

- **GIVEN** the prior fingerprinted process issue was closed after a successful fix
- **WHEN** the same friction class is observed again
- **THEN** the router creates a new open process issue under the existing open-issue dedupe rule
- **AND** the recurrence is visible as new regression evidence rather than rewriting the historical resolved record
