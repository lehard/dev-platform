## ADDED Requirements

### Requirement: Opt-in local source permission policy
The platform SHALL support an operator-local policy for allowed application source paths, separate from platform-owned shared state. Repair SHALL change only current-user owned paths within reviewed roots and shared-group membership, SHALL avoid secrets, generated dependencies, symlinks and foreign active worktrees, and SHALL diagnose exact unrepairable paths. Opted-in lifecycle admission SHALL check allowed source paths before mutation.

#### Scenario: Restrictive or atomic source write
- **GIVEN** a registered checkout with an explicit source policy
- **WHEN** its owner creates or atomically replaces an allowed source file with restrictive group permissions
- **THEN** an owner audit restores group read/write and directory group traversal/write plus setgid
- **AND** a foreign-owner audit reports the path without changing it

#### Scenario: Foreign active task
- **WHEN** the policy runs inside another user's active worktree
- **THEN** it refuses to repair or launch task commands there

### Requirement: Preserve hook composition
Local attachment SHALL preserve existing hook arguments, stdin and failure status, including platform hooks refreshed by doctor. Attachment SHALL be idempotent and removable without deleting foreign hooks.

#### Scenario: Doctor refresh and failing hook
- **GIVEN** an attached checkout whose original pre-commit hook is refreshed
- **WHEN** the refreshed hook rejects a commit
- **THEN** the composed hook invokes that refreshed hook and returns failure

### Requirement: Automatically attach registered local projects
A reviewed external registry SHALL drive identity-scoped discovery, versioned runtime installation and updates across local projects. Automatic per-user sync SHALL operate only in reviewed workspace roots, SHALL preserve existing configuration, and SHALL report unavailable projects or foreign-owner drift. A cooperative launcher SHALL set umask 0002 and audit allowed source paths before and after commands. Mac-specific paths and users SHALL stay in operator-local configuration.

#### Scenario: New registered project
- **GIVEN** a reviewed workspace root and project repository inventory
- **WHEN** a matching integration checkout appears and sync runs
- **THEN** it receives the current local policy and composed hooks automatically
- **AND** an unrelated checkout remains unchanged

#### Scenario: Both user identities
- **WHEN** either permitted group member runs the installed automation
- **THEN** their own allowed newly created files and worktree metadata are repaired
- **AND** the other user's active worktree remains untouched
