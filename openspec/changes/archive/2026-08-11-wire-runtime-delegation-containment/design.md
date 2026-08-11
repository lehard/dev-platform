# Design: supported delegated-write runtime guard

## Safety model

The platform cannot honestly promise one universal filesystem jail across every agent runtime. It can, however, make one supported delegation path deterministic and explicit:

`validate assigned worktree -> establish enforcement tier -> content-aware pre-snapshot -> launch in assigned worktree -> always post-snapshot -> classify -> record friction -> return success/failure`

Only this guarded path is described as platform-contained. Agent-native write delegation that bypasses it may still be useful, but it is outside the platform containment guarantee and agent guidance must not blur that distinction.

## Content-aware integration snapshot

The existing `HEAD + set(status_code, path)` snapshot is insufficient for a dirty path whose status code remains unchanged while content changes. Replace/extend it with a deterministic fingerprint that can distinguish at least:

- integration `HEAD` commit;
- index state for tracked dirty paths (blob/object identity or equivalent deterministic index fingerprint);
- worktree contents for tracked dirty paths, including executable/symlink-relevant state where Git distinguishes it;
- every untracked file enumerated by the snapshot, including content fingerprint and path;
- path appearance/disappearance/rename state sufficiently to report the affected path(s).

The implementation should avoid hashing the entire repository. It may use Git object/diff identities plus content hashes only for paths reported dirty/untracked. Snapshotting is read-only and must fail closed if a needed path cannot be inspected consistently.

A path present before and after is `pre_existing_unchanged` only when its relevant fingerprint is equal, not merely when porcelain status text matches.

## Supported delegation entrypoint

Add a dependency-light platform helper/entrypoint for write-capable delegation. Exact module/CLI naming may be adjusted during implementation if the OpenSpec design is updated first, but its contract is:

1. Resolve integration root and `assigned_worktree` via registered Git worktrees; reject relative/unregistered/integration-root assignments.
2. Determine runtime/enforcement tier before launch.
3. If the tier is detection-only and integration is dirty, fail before starting the writer.
4. Capture the content-aware integration pre-snapshot.
5. Launch/wrap with `cwd=assigned_worktree` and the runtime-specific enforcement configuration.
6. Run the post-snapshot and comparison on every exit path, including child failure/cancellation.
7. If integration changed, report exact paths, record local friction after classification, and return containment failure even if the child otherwise succeeded.
8. Never auto-stash/reset/clean/delete integration changes.

The entrypoint must not require GitHub authentication for local containment or friction recording.

## Runtime enforcement tiers

### Codex: hard writable-root containment when platform-controlled

When the platform controls the Codex child launch and the installed runtime exposes the supported workspace-write sandbox, configure the writable root to the resolved `assigned_worktree` and avoid additional writable repository roots. The adapter must validate/establish that policy before describing the run as hard-contained.

If the expected sandbox capability is unavailable, invocation must either:

- fail before launch when hard containment was requested/required; or
- explicitly downgrade to the detection-only tier, which is allowed only with a clean integration checkout and must be reported as detection-only.

No silent downgrade may retain a `hard` label.

### Claude Code: hook-assisted prevention plus truthful shell boundary

Where the platform controls the Claude child/session configuration, provide a session/local `PreToolUse` guard for structured filesystem write tools whose target path can be resolved reliably (`Write`, `Edit`, `NotebookEdit`, and equivalent supported tools). The guard resolves the target and denies anything outside `assigned_worktree`.

Arbitrary shell commands are not declared hard-contained merely because a hook inspected command text. Unless the child is additionally placed in a real OS filesystem sandbox, Claude shell-capable delegation is a detection-only tier for the purposes of the platform contract. Therefore it requires a clean integration checkout before launch and always receives the post-check.

The design does not vendor OpenSpec-generated skills or assume hooks are inherited by opaque tool-native subagents. The supported entrypoint is responsible for the configuration it launches.

## Integration state changed concurrently

A moved integration `HEAD` or new dirty state during delegation is treated as a containment/integration-safety event even if another process may have caused it. Attribution cannot be proven from snapshots alone. The platform must stop and report rather than guessing or repairing. Serialization of normal post-merge integration (covered by `harden-pr-reconciliation-concurrency`) reduces legitimate concurrent mutations, but containment remains conservative.

## Existing dirty integration behavior

- **Hard-contained runtime:** pre-existing dirty integration is permitted because the OS/pre-write boundary is proven to prevent the delegated writer from touching it; the content-aware post-check still verifies no unexpected mutation occurred.
- **Detection-only runtime:** pre-existing dirty integration blocks launch. This intentionally trades convenience for protection of uncommitted state that cannot be safely restored if the writer overwrites it.

## Project/tool integration

Generated workflow documentation and platform agent rules should explain the supported guarded path. Do not modify/project-own OpenSpec-generated Claude/Codex skill directories. Any local runtime settings created solely for a guarded child should be machine-local or generated/ephemeral rather than silently taking ownership of a project's tracked agent configuration.

## Upgrade and rollback

This adds/changes managed platform scripts and guidance, so fresh renders and existing Copier-managed consumers must be tested. Rollback removes the supported runtime guard and content-aware snapshot protection; no persisted project data format migration is required, but rollback reopens the containment gap.

## Validation

Automated coverage must include:

- an already-dirty tracked file whose contents change but porcelain status remains identical -> violation;
- unchanged dirty tracked/index/untracked state -> not a violation;
- untracked file content mutation, create/delete, symlink-relevant state where supported;
- snapshot failure -> fail closed;
- detection-only runtime + dirty integration -> child never launched;
- fake/runtime-adapter Codex hard tier proves only assigned worktree is writable and refuses silent downgrade;
- Claude structured write hook denies an out-of-root target and allows an in-root target; shell-capable mode remains labeled detection-only unless a real OS sandbox is used;
- child failure still executes post-check and can surface a containment violation;
- local friction recording works without GitHub auth;
- Project Factory render/upgrade smoke plus a real guarded delegation acceptance in at least one managed platform-owned consumer.