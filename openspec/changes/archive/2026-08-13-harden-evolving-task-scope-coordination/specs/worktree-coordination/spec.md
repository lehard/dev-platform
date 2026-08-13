## ADDED Requirements

### Requirement: Known same-file overlap can be acknowledged without falsifying scope

File-level hard overlap SHALL remain a default admission blocker. The platform MAY allow a task to proceed through an explicit bounded acknowledgment when an operator has verified that the concrete same-file overlap is intentionally safe. The acknowledgment SHALL record the current/conflicting task identities, exact conflicting repository-relative paths and a bounded reason, and SHALL NOT require the task to omit those paths from its truthful declared scope.

#### Scenario: Same file is intentionally shared

- **GIVEN** task A is active and claims file `x`
- **AND** task B also truthfully needs file `x`
- **WHEN** task B starts without an overlap acknowledgment
- **THEN** task B receives the normal hard-overlap `WAIT`
- **WHEN** an operator explicitly acknowledges the current A/B overlap on file `x` with a reason
- **THEN** task B may proceed without removing `x` from its declared scope
- **AND** the acknowledgment is retained as bounded coordination evidence

#### Scenario: Acknowledged overlap does not cover new files

- **GIVEN** an acknowledgment covers file `x`
- **WHEN** task B later overlaps task A on previously unacknowledged file `y`
- **THEN** the acknowledgment for `x` does not authorize `y`
- **AND** the new hard overlap requires a new coordination decision

### Requirement: Factual scope is rechecked before costly validation and publication

The platform SHALL compare the task's current factual changed-file scope with active task claims before costly protected validation and again at the publication boundary. A newly observed hard file overlap that is still active and not explicitly acknowledged SHALL block progression instead of remaining a warning-only diagnostic.

#### Scenario: Task scope expands after admission

- **GIVEN** tasks A and B were admitted without a hard overlap
- **WHEN** task B's factual diff later begins changing a concrete file actively claimed by task A
- **THEN** the pre-validation or pre-publication coordination gate stops task B before further costly/delivery work
- **AND** reports the active conflicting task and bounded repository-relative paths
- **AND** requires the overlap to clear or be explicitly acknowledged

#### Scenario: Conflicting task has completed

- **GIVEN** a previous hard overlap existed
- **WHEN** the sibling task is no longer active under the normal board lifecycle
- **THEN** its stale claim does not block the current task
- **AND** resume may proceed after the ordinary recheck

#### Scenario: Only soft scope overlap exists

- **WHEN** two active tasks share only a broad directory, subsystem or other non-file-specific scope
- **THEN** the platform emits a warning
- **AND** does not create a hard coordination blocker solely from that soft overlap
