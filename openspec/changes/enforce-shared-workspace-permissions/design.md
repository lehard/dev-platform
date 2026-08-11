## Context

PR #145 exposed several manifestations of one missing invariant in the central
repository: non-group-writable Git object directories, `FETCH_HEAD`, repository
root entries and owner-only `.claude` state. Manual repair allowed progress, but
`agent_friction.py` and the board writer immediately recreated `0600` files via
atomic replacement. This proves that a one-time `chmod` is not a durable fix.

The same class of failure was previously solved in `Jara_Fin`. Its current
implementation combines:

1. repository guidance and runtime entry points using `umask 0002`;
2. `check_group_write.sh --check/--fix`, with group resolution from the checkout
   or an environment override;
3. group-write plus setgid repair and `core.sharedRepository=group`;
4. shared-path helpers in board, friction, cleanup and merge tooling;
5. atomic writers that set the temporary file to `0664` before `os.replace`;
6. post-operation audits; and
7. regression tests.

The platform should adopt the architecture, not copy Jara-specific names,
absolute paths, exclusions or the hardcoded local group.

## Decisions

### 1. Shared group is derived, not project-configured identity

The default shared group is the group owner of the registered integration root.
A machine-local environment override may select another reviewed group for
special deployments. No username, numeric gid or machine-local path is committed
into the template.

The doctor reports the resolved root/group and whether POSIX mode enforcement is
available. Unsupported filesystems/platforms receive a clear diagnostic and do
not run unsafe emulation.

### 2. A common primitive owns mode-preserving writes

Platform scripts use one shared helper for directories, files, locks and atomic
replacement:

- shared directories are group `rwx` and setgid;
- ordinary shared state/lock files are at least group `rw`;
- atomic temporary files receive the final shared mode before `os.replace`;
- an existing more-restrictive non-group mode may be preserved for non-shared
  sensitive paths, which are outside this primitive's allowlist; and
- chmod/chgrp failures name the exact path and owning group instead of being
  swallowed.

The primitive is applied to all platform-owned machine-local state, including
agent board, friction state/log/locks, publication/cleanup coordination and
worktree metadata. The active friction-routing change remains authoritative for
data semantics; this change only replaces its filesystem write mechanics.

### 3. Git metadata is part of the collaboration contract

Bootstrap/fix configures `core.sharedRepository=group` in the repository and
checks the Git common directory used by all worktrees. The bounded repair covers
metadata required for normal object creation, refs/log updates, worktree admin,
fetch and merge reconciliation. It never changes another repository or a path
outside the resolved Git common directory.

Git environment overrides such as `GIT_OBJECT_DIRECTORY` are not the normal
solution and are not exported across lifecycle validation commands. Existing
alternate object stores are reported for deliberate reconciliation rather than
silently removed.

### 4. Prevention and repair compose

`umask 0002` is set inside platform-owned file-producing entry points and child
processes that intentionally create managed artifacts. This prevents ordinary
drift but is insufficient for APIs such as `mkstemp`, which deliberately create
`0600`; those writers explicitly apply the final mode.

A rendered permission helper exposes read-only `check` and bounded `fix` modes.
Bootstrap performs safe initialization, doctor performs read-only validation,
and lifecycle mutations perform a targeted preflight/fix for the paths they own.
Post-operation validation catches tools that ignored the expected umask.

### 5. Repair is bounded and fail-closed

The helper resolves and realpath-validates the integration root and Git common
directory before mutation. It refuses `/`, a home directory, unresolved
variables, symlink escapes and unregistered worktrees. It does not recursively
open permissions on credential files, virtual environments, dependency caches
or arbitrary external paths.

When a path is owned by another user and the current process cannot repair it,
the lifecycle stops before the next remote mutation and prints a minimal exact
`chmod`/`chgrp` command for the owner. No `sudo`, stash, reset or destructive
cleanup is attempted automatically.

### 6. Existing projects receive a reviewable Copier upgrade

All workflow profiles render the helper and shared-writer behavior. Copier
smart-update preserves project-owned content and adds only platform-owned files,
guidance/config defaults and bounded lifecycle integration. Migration detects
existing Jara-style local helpers and avoids creating two competing automated
repair loops; projects may keep domain-specific wrappers while delegating the
platform invariant to the rendered primitive.

### 7. Verification includes real mode transitions

Tests exercise `0644 -> 0664`, `0755 -> 2775`, atomic replacement, idempotent
already-correct paths, dynamic group resolution, simulated foreign ownership,
unrepairable-path diagnostics, Git common-directory/worktree metadata and
render/update behavior. A POSIX acceptance smoke alternates effective ownership
where the runner supports it; otherwise mode and mocked ownership tests remain
mandatory and the skipped capability is explicit.

## Alternatives considered

- **One-time recursive chmod only:** rejected because atomic writers and Git
  recreate restrictive files.
- **Hardcode `staff`:** rejected because deployed/shared groups differ and the
  platform is cross-project.
- **Rely only on `umask 0002`:** rejected because secure temporary-file APIs use
  `0600` intentionally.
- **Export a central alternate object directory:** rejected because it leaks
  repository-specific Git state into tests and unrelated subprocesses.
- **Give every file world-write:** rejected as unnecessary and unsafe; the
  contract is limited to the reviewed shared group.
