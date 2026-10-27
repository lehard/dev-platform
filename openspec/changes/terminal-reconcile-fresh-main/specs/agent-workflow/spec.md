## MODIFIED Requirements

### Requirement: Requirement terminal state requires target delivery proof

Requirement terminal reconciliation SHALL require a supported target lifecycle and the existing exact linked-child, archived verification and merged delivery evidence. A manually closed Issue, Project Done field, or empty child set SHALL NOT substitute for that proof. The archived verification evidence SHALL be read from the tree of a freshly fetched remote main commit, not from the integration checkout, so reconciliation neither depends on nor performs a fast-forward of the local integration main; a failed fetch SHALL stop reconciliation.

#### Scenario: Target lacks a terminal path

- **GIVEN** a Requirement Issue appears complete or its work was delivered outside managed execution
- **WHEN** terminal reconciliation cannot prove the target's supported managed lifecycle and exact delivered children
- **THEN** it refuses parent Done and Issue closure
- **AND** reports the missing terminal proof

#### Scenario: Integration main was not fast-forwarded

- **GIVEN** a child's archived change with its verification receipt is merged on remote main
- **AND** the local integration main has not been fast-forwarded to it
- **WHEN** terminal reconciliation runs in the integration checkout
- **THEN** it proves that child's delivery from the fetched remote main commit
- **AND** it leaves the local integration main and working tree unchanged

#### Scenario: Remote main lacks the archive

- **WHEN** the fetched remote main commit has no archived change with a verification receipt for a child, even though the local checkout has one
- **THEN** terminal reconciliation refuses, naming that child
