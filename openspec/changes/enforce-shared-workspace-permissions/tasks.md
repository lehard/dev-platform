## 1. Reconcile prior art and active platform work

- [x] 1.1 Audit the current `Jara_Fin` permission helpers, atomic writers,
  wrappers and tests; record which behavior is reusable and which is
  project-specific.
- [x] 1.2 Reconcile implementation with the archived result of
  `adopt-gh-aw-process-automation` so friction routing has one filesystem writer
  contract rather than parallel implementations.
- [x] 1.3 Inventory every platform-owned mutable repository, Git-common-dir and
  machine-local path across `light`, `standard` and `multi-agent` profiles.

## 2. Add the shared permission primitive

- [x] 2.1 Implement safe shared-group resolution, POSIX capability detection and
  realpath-bounded registered-root validation.
- [x] 2.2 Implement reusable shared directory/file/lock and atomic-write helpers
  that preserve group write and setgid inheritance.
- [x] 2.3 Add a rendered read-only `check` plus bounded `fix` command with exact
  actionable diagnostics for paths the current user cannot repair.
- [x] 2.4 Configure and validate Git `core.sharedRepository=group` plus the
  required Git common-directory metadata without exporting repository-specific
  object-store environment variables.

## 3. Integrate lifecycle prevention and recovery

- [x] 3.1 Apply the primitive to board, friction, cleanup, publication and other
  platform-owned machine-local state/lock writers.
- [x] 3.2 Set `umask 0002` within platform-owned file-producing entry points and
  explicitly chmod secure temporary files before atomic replacement.
- [x] 3.3 Integrate permission initialization/check/fix with bootstrap, doctor,
  readiness, managed start/finish and central dogfood ordering.
- [x] 3.4 Fail before remote mutation on divergent unrepairable permission state;
  keep already-merged recovery idempotent and actionable.

## 4. Render and migrate every managed project

- [x] 4.1 Render the helper, configuration and agent guidance for all workflow
  profiles with no hardcoded user, gid or local path.
- [x] 4.2 Preserve project-owned files during Copier smart update and define
  coexistence/migration for projects with an existing Jara-style permission
  audit.
- [x] 4.3 Update durable platform adoption/operation documentation with the
  shared-group contract, repair path and unsupported-filesystem behavior.

## 5. Verify and deliver

- [x] 5.1 Add unit tests for group resolution, mode repair, setgid, atomic
  replacement, idempotence, foreign ownership, symlink/boundary rejection and
  sanitized exact diagnostics.
- [x] 5.2 Add Git lifecycle tests covering objects, refs, logs, worktree admin,
  `FETCH_HEAD`, fetch and local-main reconciliation across shared users.
- [x] 5.3 Add template render and Copier upgrade smokes for all profiles,
  including an existing customized project and an existing local permission
  helper.
- [x] 5.4 Run central dogfood acceptance from two local identities when the test
  environment supports it; otherwise record the capability gap and equivalent
  mode/ownership evidence.
- [x] 5.5 Run the full platform validation matrix, semantic OpenSpec verification
  and lifecycle archive.
- [ ] 5.6 Publish an immutable platform release and roll it out through reviewed
  Copier PRs to every managed inventory entry.
