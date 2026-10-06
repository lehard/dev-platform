## ADDED Requirements

### Requirement: Exact-target validation uses reviewed workspace storage

Managed authoring and handoff materialization SHALL validate against their exact prepared revision in an isolated helper-owned detached Git worktree under the integration checkout's existing configured platform worktree storage. This operation SHALL retain ordinary workspace admission, shared-workspace permissions and containment checks and SHALL NOT depend on manually changing TMPDIR, disable policy, or substitute another location after failure. Missing or invalid required storage configuration, unsafe containment or ownership, and admission failures SHALL fail explicitly before managed Issue creation.

#### Scenario: Attached local policy with external system temporary directory

- **GIVEN** an integration checkout admitted under reviewed workspace roots and TMPDIR outside those roots
- **WHEN** managed authoring or materialize-handoff validates a package
- **THEN** its isolated detached worktree is allocated in existing platform storage inside those roots without changing TMPDIR
- **AND** validation observes the exact prepared SHA with ordinary admission and permission checks
- **AND** integration source content and branch identity remain unchanged

#### Scenario: Invalid validation storage

- **WHEN** validation storage configuration is missing or invalid, or its path escapes containment through a symlink or has foreign ownership
- **THEN** validation fails explicitly naming the unsafe storage
- **AND** no alternate directory, policy bypass or managed Issue is used

### Requirement: Validation worktree cleanup is explicit and identity bounded

Exact-target validation SHALL clean only its own verified temporary worktree and directory on success, failure and catchable interruption. A failed checkout hook that leaves a Git registration SHALL receive the same bounded cleanup. Failed cleanup SHALL be reported explicitly with retained identity evidence for safe recovery; it SHALL NOT be swallowed or replaced by unchecked recursive deletion. Recovery after interruption SHALL be idempotent and use existing lifecycle cleanup mechanisms without taking over foreign or ambiguous worktrees.

#### Scenario: Validation succeeds or raises

- **WHEN** validation completes, raises an exception or receives KeyboardInterrupt
- **THEN** the exact helper-owned Git registration and temporary directory are removed
- **AND** validation errors remain visible and unrelated worktrees are untouched

#### Scenario: Checkout hook rejects the temporary checkout

- **WHEN** Git worktree add returns nonzero after creating a registration
- **THEN** cleanup verifies and removes only the helper's exact registration and temporary directory
- **AND** the original checkout failure is reported

#### Scenario: Cleanup cannot be completed

- **WHEN** cleanup fails or the helper is stopped before cleanup can run
- **THEN** available identity evidence supports explicit bounded recovery via the existing cleanup mechanism
- **AND** repeated recovery of already removed helper state is safe
- **AND** foreign, changed or ambiguous worktree state is preserved with an explicit diagnostic
