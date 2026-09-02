## ADDED Requirements

### Requirement: An exact open PR may continue from a proven local descendant

Dev Platform SHALL permit continuation of an existing exact open task PR when the remote PR head is proven to be an ancestor of the local task head.

#### Scenario: Local CI fix descends from exact PR head

- **WHEN** the local task head descends from the unchanged remote head of the exact open PR
- **THEN** lifecycle fast-forwards that same remote task branch
- **AND** revalidates PR identity before reconciling current authoritative main

#### Scenario: Remote identity or history changed

- **WHEN** the remote branch, PR head, base, repository owner or ancestry proof differs from the expected identity
- **THEN** lifecycle refuses mutation without force, rebase or guessed recovery

### Requirement: Exact merged PR recovery is terminal

Dev Platform SHALL route a proven exact merged PR only through terminal local-main and managed-status reconciliation.

#### Scenario: Finish resumes after squash merge

- **WHEN** GitHub proves the exact validated task head is already merged
- **THEN** lifecycle synchronizes authoritative local main and terminal task state
- **AND** does not create, update or publish another task head or pull request
