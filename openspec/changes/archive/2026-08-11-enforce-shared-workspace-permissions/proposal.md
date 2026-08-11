## Why

The platform describes `.claude/`, worktrees and the Git common directory as
shared local coordination infrastructure, but its writers currently inherit
per-user defaults. On a checkout shared by local users in one Unix group, that
silently creates `0600` state files, `0644` Git metadata and non-group-writable
directories. The next authorized user can read neither lifecycle state nor
write the object database, so safe start/finish/recovery stops after remote
state may already have changed.

`Jara_Fin` provides working prior art: set `umask 0002`, dynamically resolve the
checkout group, enable `core.sharedRepository=group`, keep shared directories
setgid, chmod atomic temporary state to `0664` before replacement, and run a
bounded check/fix audit after file-producing operations. The reusable platform
should own this invariant instead of requiring each downstream project to
rediscover it.

## What Changes

- Define a portable shared-workspace permission contract for every managed
  project, with POSIX enforcement and an explicit safe no-op/diagnostic path on
  filesystems that cannot represent the contract.
- Add a platform-owned check/fix helper that resolves the intended group from
  the checkout (with a machine-local override), validates both project paths
  and the Git common directory, repairs only bounded registered roots, and
  reports exact unrepairable paths.
- Make all platform atomic writers, locks and lifecycle subprocess entry points
  preserve group read/write and setgid inheritance instead of recreating
  owner-only files.
- Configure Git shared-repository behavior and validate/repair existing Git
  metadata needed for objects, refs, worktrees, fetch and merge reconciliation.
- Wire permission preflight/repair into bootstrap, doctor, managed start/finish,
  cleanup and central dogfood without changing product-owned credentials or
  traversing outside the registered checkout.
- Render the helper, guidance and configuration through Copier for all workflow
  profiles and safely upgrade existing projects.
- Add mode/ownership, atomic-replacement, Git-metadata, idempotence, failure and
  downstream render/update tests based on the proven `Jara_Fin` pattern.

## Impact

- Affected specs: `project-factory`, `platform-lifecycle`.
- Affected platform areas: `_platform_common.py`, platform state writers,
  bootstrap/doctor/start/finish/cleanup, Git lifecycle, Copier template and
  downstream upgrade tests.
- Delivery boundary: this task verifies, archives and publishes the source
  implementation. Immutable release publication and downstream Copier rollout
  need the source PR to be merged, so they are fixed as a separate post-merge
  managed change.
- Existing active change dependency: compose with the final archived form of
  `adopt-gh-aw-process-automation`; do not fork its friction-routing behavior.
- Security boundary: group access is granted only to the checkout's reviewed
  shared group and bounded managed paths. The helper must not widen permissions
  on credential stores, home directories or paths outside the registered
  project/Git common directory.
