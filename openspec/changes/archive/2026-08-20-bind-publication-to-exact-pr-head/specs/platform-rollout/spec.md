## ADDED Requirements

### Requirement: Managed project-owned publication harnesses conform to shared exact-head merge safety

A managed repository with `harness_mode=project` SHALL retain ownership of its repository-specific task/worktree/integration harness, but that ownership SHALL NOT weaken the platform-owned merge-safety invariant. Managed rollout SHALL treat exact-head publication safety as a conformance requirement for project-owned publication code.

A bounded compatibility migration MAY change only the recognized publication identity/confirmation surface when applicability is proven by a deterministic, reviewed compatibility predicate. Unknown or drifted project-owned harness content SHALL fail closed with an actionable diagnostic and SHALL be preserved rather than overwritten.

Advancing `.copier-answers.yml` or `.dev-platform.toml` platform version metadata alone SHALL NOT count as successful safety adoption for a project-owned harness whose publication surface is known to require conformance.

#### Scenario: Jara-like project harness has a recognized vulnerable publication shape

- **GIVEN** a managed project-owned harness matches the reviewed Jara-like compatibility fixture
- **WHEN** rollout applies the safety release
- **THEN** only the vulnerable publication identity/confirmation surface is migrated to stable PR identity plus exact expected head
- **AND** project-owned board, worktree, and serialized integration behavior remains intact
- **AND** the migration is idempotent

#### Scenario: Planner-like project harness has a recognized vulnerable publication shape

- **GIVEN** a managed project-owned harness matches the reviewed Planner-like compatibility fixture
- **WHEN** rollout applies the safety release
- **THEN** its publication path gains stable PR identity and exact-head confirmation
- **AND** its standalone integration-clone semantics remain intact
- **AND** the migration is idempotent

#### Scenario: Project-owned publication harness has unexpected drift

- **GIVEN** a managed `harness_mode=project` repository does not match a reviewed compatibility predicate
- **WHEN** rollout cannot prove the bounded safety migration is applicable
- **THEN** rollout fails closed before publishing a downstream update that claims safety conformance
- **AND** the project-owned harness bytes remain unchanged
- **AND** the diagnostic identifies the publication-safety compatibility blocker without guessing a rewrite

#### Scenario: Platform-owned harness receives the same safety release

- **GIVEN** a managed repository uses `harness_mode=platform`
- **WHEN** rollout applies the safety release
- **THEN** normal Copier-managed lifecycle files receive the exact-head publication implementation
- **AND** no project-harness compatibility rewrite is attempted

#### Scenario: Candidate or excluded repository is known to the registry

- **GIVEN** a repository is not in `managed` state
- **WHEN** ordinary managed rollout runs for the safety release
- **THEN** the repository is not mutated
- **AND** it receives the corrected contract only through a later deliberate adoption path
