## ADDED Requirements

### Requirement: Project configuration records main protection and PR merge policy

Generated project configuration SHALL explicitly record whether the integration branch is expected to be protected and how ordinary task PRs are completed.

#### Scenario: Standard project is generated for protected delivery

- **WHEN** a standard or multi-agent platform-owned project is generated with normal safe defaults
- **THEN** configuration records `protected_main=true`, `publish_mode=pr`, and `pr_merge_mode=auto`

#### Scenario: Intentionally simple unprotected project uses direct publication

- **WHEN** a project deliberately uses direct publication
- **THEN** configuration records `protected_main=false`
- **AND** doctor can distinguish that choice from an accidental protected-main mismatch

### Requirement: Invalid protected-main publication combinations are rejected during configuration

The project factory SHALL reject or clearly fail validation for combinations that cannot satisfy the protected-main lifecycle.

#### Scenario: Protected light project requests direct publication

- **GIVEN** the light profile has no mandatory feature branch
- **WHEN** protected main is enabled with direct publication
- **THEN** generation/doctor rejects the combination
- **AND** instructs the project to use a feature-capable profile or a reviewed project-owned harness