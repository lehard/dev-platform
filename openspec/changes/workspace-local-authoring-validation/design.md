## Context

`template/scripts/managed_task.py:exact_target_context` uses `tempfile.mkdtemp` without a location and ignores worktree removal and recursive deletion errors. The local post-checkout hook inherits the integration policy and rejects checkouts outside reviewed roots. Existing platform worktree storage is already inside the reviewed integration checkout.

## Decisions

Resolve the integration root using existing platform Git helpers and use its configured worktree storage as the single placement strategy. Create missing configured storage directories only within the bounded integration path and verify their shared permissions. Reject missing/invalid required configuration, symlink escapes, foreign ownership and admission failures before destructive operations. Do not select system temporary storage on failure. Preserve the exact fetched SHA and detached checkout.

Use a unique helper-owned validation directory within that storage, avoiding task branches and board claims. Keep cooperative directory permissions through existing shared-workspace primitives; do not repair foreign source trees. Verify the root's local policy normally and let its Git hooks admit the temporary checkout.

Require the integration `.dev-platform.toml` and an explicit bounded relative `paths.worktrees`; existing generic configuration defaults must not hide missing configuration. Record a helper receipt before checkout containing the integration, exact SHA, owner uid, process pid and parent inode. Extend `worktree_cleanup.py` with `cleanup-validation --directory <helper-directory>`; recovery rejects a live owner process, active worktree cwd, changed receipt/inode/HEAD, branches, locked registrations and foreign ownership. Normal cleanup uses the same identity checks with the creating process explicitly authorized. Recovery after SIGKILL is operator-triggered, never a background sweep.

Cleanup must inspect exact helper directory and Git registration identity, remove only this helper's detached worktree, then remove the empty helper directory. A failed post-checkout hook can register a worktree even when add returns nonzero: inspect and safely remove that exact registration, never prune unrelated entries. Cleanup errors remain explicit and preserve the original validation failure as context. Normal exceptions and KeyboardInterrupt run cleanup; a hard interruption exposes a narrowly bounded, idempotent recovery through the existing cleanup mechanism rather than creating another lifecycle. Document the supported recovery and its actual limits.

## Risks and Mitigations

- Directory placement participates in local admission and group inheritance: use existing reviewed storage, owner checks and permission primitives; test attached policy without bypass.
- Failed Git checkout can leave registered state: exercise hook failures with real Git and inspect registration before deletion.
- Cleanup could affect sibling work: require helper ownership, exact path and detached SHA identity; preserve foreign or changed state with actionable failure.
- Template updates affect multiple projects: keep central wrapper and template runtime identical through their existing adapter and normal Copier delivery.

## Verification

Regression tests cover an external system TMPDIR, exact revision despite stale local checkout, supported reviewed placement, hook failure, body exception, KeyboardInterrupt, cleanup failure, idempotent recovery, and rejection of symlink/foreign identity. Existing exact-state tests remain passing. Perform semantic contract review and required platform checks before publication.
