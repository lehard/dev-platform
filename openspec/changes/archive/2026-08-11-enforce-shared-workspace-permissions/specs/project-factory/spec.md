## ADDED Requirements

### Requirement: Managed projects preserve a shared-workspace permission contract

The Project Factory SHALL render a portable shared-workspace permission
primitive into every workflow profile. On POSIX filesystems, platform-owned
shared directories SHALL preserve group write plus setgid inheritance and
platform-owned shared files/locks SHALL preserve group read/write, including
after atomic replacement. The intended group SHALL be derived from the reviewed
checkout or a machine-local override and SHALL NOT be hardcoded to a particular
user, gid or deployment group.

#### Scenario: Fresh managed project is used by a second group member

- **GIVEN** a fresh rendered project whose integration root is owned by a shared
  POSIX group
- **WHEN** one group member creates platform state, Git metadata and a task
  worktree through supported entry points
- **THEN** another member of that group can read and update the shared lifecycle
  state and perform normal Git object/ref/worktree operations
- **AND** no world-write permission is required

#### Scenario: Atomic shared state is replaced

- **WHEN** a platform writer atomically replaces board, friction, cleanup or
  publication state
- **THEN** the replacement file is group-readable and group-writable before it
  becomes visible at the final path
- **AND** repeated writes by alternating group members remain valid

#### Scenario: Platform cannot represent POSIX group modes

- **WHEN** the project filesystem does not support the POSIX permission contract
- **THEN** the platform reports that enforcement is unavailable using a defined
  non-mutating compatibility path
- **AND** it does not attempt unsafe permission emulation

### Requirement: Existing projects receive bounded permission migration

Copier update SHALL add the shared-workspace primitive and lifecycle wiring to
existing managed projects without overwriting project-owned content or widening
permissions outside the registered project and Git common directory.

#### Scenario: Existing project already has local permission tooling

- **GIVEN** an existing managed project has a project-owned permission audit or
  wrappers such as the proven `Jara_Fin` pattern
- **WHEN** the platform update is applied
- **THEN** platform-owned writers adopt the shared primitive
- **AND** project-owned tooling/content is preserved
- **AND** automation does not create two competing repair loops for the same
  platform-owned paths

#### Scenario: Existing checkout contains unrepairable foreign-owned paths

- **WHEN** migration finds a required shared path that the current user cannot
  safely repair
- **THEN** it reports the exact bounded path, current ownership/mode and owner
  action required
- **AND** it does not use sudo, traverse outside the registered roots or continue
  into a remote-mutating lifecycle step
