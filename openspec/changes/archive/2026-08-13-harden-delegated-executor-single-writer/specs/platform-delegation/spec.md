## ADDED Requirements

### Requirement: Abnormal delegated execution reaps the launched writer before ownership is released

The platform delegation path SHALL perform bounded termination and reaping for a launched write-capable child and its relevant descendants when execution ends abnormally. Existing containment checks SHALL still run and SHALL not be replaced by process cleanup.

#### Scenario: Delegated child times out or is cancelled

- **GIVEN** the write-capable delegated child was launched in its assigned worktree
- **WHEN** the observed delegation times out, is cancelled, or otherwise returns abnormally
- **THEN** the platform terminates and reaps the launched writer process tree before releasing writer ownership
- **AND** containment evidence is still collected
- **AND** the abnormal execution remains a failure rather than being converted to success

#### Scenario: Cleanup succeeds

- **WHEN** the launched writer and relevant descendants are proven absent after abnormal cleanup
- **THEN** the assigned worktree may become eligible for a later routed writer
- **AND** repeated cleanup is safe
