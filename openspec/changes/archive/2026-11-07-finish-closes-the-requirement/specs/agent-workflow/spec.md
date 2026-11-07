## ADDED Requirements

### Requirement: The finish of the last child closes the Requirement

After GitHub reports the exact PR of a managed child `MERGED`, `finish` SHALL close the parent Requirement through terminal reconciliation when every linked child is terminal and the Requirement retrospective is current. `finish` SHALL NOT write the retrospective. A closure that does not happen SHALL be named, SHALL NOT undo the merge and SHALL NOT be reported as success, and its retry SHALL be idempotent.

#### Scenario: Last child closes the Requirement

- **GIVEN** every other linked child is terminal and the Requirement retrospective is current
- **WHEN** `finish` confirms the merge of the last child
- **THEN** terminal reconciliation closes the Requirement in that run
- **AND** `finish` prints the Requirement, the number of children and the retrospective result

#### Scenario: Other children are open

- **GIVEN** another linked child is not terminal
- **WHEN** `finish` confirms the merge of a child
- **THEN** the Requirement stays open
- **AND** `finish` succeeds for its child and names each open child with its status

#### Scenario: Closure is prevented

- **GIVEN** the retrospective is missing or stale, an operator acceptance item is open, a child status cannot be read, or GitHub refuses a closure step
- **WHEN** `finish` reaches closure after the merge
- **THEN** the Requirement stays open and the merge stands
- **AND** `finish` exits non-zero naming the cause, the command that fixes it and the retry command

#### Scenario: Closure is retried

- **GIVEN** an earlier `finish` stopped at closure after the merge
- **WHEN** the cause is resolved and `finish` runs again
- **THEN** it does not publish again and closes the Requirement

#### Scenario: The Issue is already closed

- **GIVEN** the parent Issue is already closed
- **WHEN** `finish` reaches closure
- **THEN** it reports only that the Issue is already closed
- **AND** it claims neither proof of delivery nor closure by this run

#### Scenario: A gap is known before publication

- **GIVEN** closure would be prevented after the merge of a managed child
- **WHEN** `finish` is about to publish
- **THEN** it prints what is missing and the command
- **AND** publication and merge are not stopped

#### Scenario: Status shows an open parent

- **GIVEN** a delivered child whose parent Requirement is open
- **WHEN** read-only status runs
- **THEN** it reports a `requirement` obligation that is pending with what is missing, or a warning while other children are open
