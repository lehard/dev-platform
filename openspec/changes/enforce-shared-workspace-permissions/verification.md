## Preliminary verification evidence

- `python3 -m compileall -q template/scripts scripts` passed.
- `python3 -m unittest discover -s tests -q` passed.
- `openspec validate enforce-shared-workspace-permissions --strict --no-interactive` passed.
- `python3 scripts/managed_projects.py validate` passed.
- `python3 template/scripts/openspec_lifecycle.py check` passed before task boxes were updated.

The runner cannot perform a two-effective-identity POSIX smoke. Unit coverage
therefore verifies setgid/group modes, secure atomic replacement, Git shared
repository configuration, bounded worktree traversal, symlink rejection,
foreign-owner diagnostics and the unsupported-platform no-op path.

The source checkout itself currently has a real permission blocker: its
integration root is group `staff`, mode `0775`, and is not owned by the current
process. The bounded helper correctly stops with the owner action
`chmod g+rwxs /Users/Shared/Workspace/dev-platform` (and does not mutate it).
This must be repaired by that checkout's owner before a managed lifecycle can
publish or complete the remaining release/rollout task.

OpenSpec-Verify: PENDING
