## ADDED Requirements

### Requirement: Requirement retrospective reads durable coordinator evidence

The Business Requirement retrospective SHALL include durable coordinator evidence recorded on the candidate pull requests of the Requirement and its linked children, in addition to the machine-local friction log, and SHALL treat it as it treats local events: it is listed by the review-path with its pull request, head, stage and worker, it may be linked or classified by the checkpoint, and mandatory lifecycle-failure and workaround signals among it SHALL be explained. When the durable source cannot be read or contains a malformed trusted record, the evidence source `coordinator-evidence` SHALL be reported as not fully readable and the checkpoint SHALL refuse it unless the gap is explicitly accepted; an unreadable source SHALL NOT be reported as an empty one. Developer task retrospectives SHALL NOT depend on GitHub for this evidence.

#### Scenario: Evidence recorded on a discarded runner

- **WHEN** the retrospective runs on a checkout whose local log contains no coordinator events
- **THEN** the review-path lists the durable events attributed to the Requirement with their pull request, head, stage and worker

#### Scenario: Mandatory durable signal

- **WHEN** a durable coordinator event is a high-severity lifecycle failure or carries a workaround or override trigger
- **THEN** the checkpoint requires it to be linked or classified like a local event

#### Scenario: Durable source unreadable

- **WHEN** GitHub or a trusted evidence record cannot be read
- **THEN** the review-path reports `coordinator-evidence` as unreadable
- **AND** the checkpoint refuses until the source is repaired or the gap is explicitly accepted
