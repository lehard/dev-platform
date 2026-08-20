## ADDED Requirements

### Requirement: Guarded recopy permits only its deterministic task-intake migration

When managed rollout adds or normalizes the platform-owned marked task-intake reference in a project-owned root `AGENTS.md`, guarded Copier recopy SHALL accept that exact deterministic migration while continuing to reject any other change to protected project-owned paths.

#### Scenario: Cuby-like project receives the missing migration reference

- **GIVEN** a project-owned root `AGENTS.md` without the marked task-intake reference
- **WHEN** managed rollout performs guarded Copier recopy and its deterministic migration
- **THEN** rollout does not report project-owned drift solely for that marked insertion
- **AND** the project-owned rules remain otherwise unchanged

#### Scenario: Protected rules change outside the migration

- **GIVEN** a protected project-owned path changes beyond the deterministic migration
- **WHEN** guarded recopy comparison runs
- **THEN** rollout fails closed
- **AND** reports the affected protected path

### Requirement: Task-intake migration is idempotent

Managed rollout SHALL leave exactly one canonical marked task-intake reference after repeated successful runs and SHALL NOT duplicate or rewrite project-owned rule content.

#### Scenario: Project is rolled out twice

- **GIVEN** a project already has the canonical marked reference
- **WHEN** managed rollout is repeated
- **THEN** the reference remains singular
- **AND** guarded protected-path comparison still detects unrelated drift
