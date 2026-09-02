## ADDED Requirements

### Requirement: External launcher interruption preserves single-writer ownership

Dev Platform SHALL route a supported external interruption of a live delegated executor through bounded process-group cleanup before releasing writer ownership.

#### Scenario: Launcher is interrupted while descendants are live

- **WHEN** the launcher receives a supported termination or interruption signal while its delegated process group is live
- **THEN** the full group is terminated and reaped through the existing cleanup boundary
- **AND** writer ownership is released only after group absence is proven

#### Scenario: Group absence cannot be proven

- **WHEN** bounded cleanup cannot prove that the delegated process group is absent
- **THEN** ownership is retained as ambiguous
- **AND** another write-capable executor is refused for that worktree

### Requirement: Abnormal executor handoff is classified and bounded

Dev Platform SHALL persist an abnormal route outcome that distinguishes external interruption, timeout and other launcher failure without discarding retained task work.

#### Scenario: Interrupted executor left a partial diff

- **WHEN** cleanup succeeds after an interrupted executor changed files within its assigned worktree
- **THEN** the receipt reports the interruption class and bounded retained-work state
- **AND** no automatic retry or quality claim is made
