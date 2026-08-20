## ADDED Requirements

### Requirement: Managed rollout preserves project-owned ignore extensions

A fresh managed platform render SHALL seed the platform `.gitignore` baseline. On every later Copier update, the complete existing downstream `.gitignore` SHALL be treated as project-owned and preserved byte-for-byte, regardless of harness mode. The platform SHALL NOT treat any part of an existing downstream `.gitignore` as replaceable template content.

#### Scenario: Project adds local runtime ignore rules

- **GIVEN** a managed repository has project-owned ignore entries in addition to the platform baseline
- **WHEN** a later platform release is applied through the supported Copier rollout path
- **THEN** the project-owned ignore behavior remains effective
- **AND** the initial-render baseline remains intact alongside those project rules

### Requirement: Rollout fails closed when managed rendering removes ignore coverage

Before publishing a managed rollout, the platform SHALL detect when managed rendering causes previously ignored representative local-secret or runtime artifact classes to become visible to Git and SHALL stop the rollout with an actionable diagnostic.

#### Scenario: Copier render drops a credential/runtime ignore rule

- **GIVEN** a representative synthetic secret/runtime path is ignored before the managed render
- **AND** the render removes the rule responsible for that coverage
- **WHEN** rollout validation evaluates the rendered result
- **THEN** rollout publication is blocked
- **AND** the diagnostic identifies lost ignore coverage without reading, deleting, staging or committing the local artifact

#### Scenario: Project extensions survive a normal update

- **GIVEN** project-owned ignore rules cover representative environment, database, dependency and build artifacts
- **WHEN** the managed Copier update preserves those rules
- **THEN** validation passes this guard
- **AND** those artifacts remain ignored after the update
