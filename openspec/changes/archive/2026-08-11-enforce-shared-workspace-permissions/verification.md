## Verification evidence

- `python3 -m compileall -q template/scripts scripts` passed.
- `python3 -m unittest discover -s tests -q` passed.
- `openspec validate enforce-shared-workspace-permissions --strict --no-interactive` passed.
- `python3 scripts/managed_projects.py validate` passed.
- `python3 template/scripts/openspec_lifecycle.py check` passed while the
  post-merge release/rollout task remains open.

The runner cannot perform a two-effective-identity POSIX smoke. Unit coverage
therefore verifies setgid/group modes, secure atomic replacement, Git shared
repository configuration, bounded worktree traversal, symlink rejection,
foreign-owner diagnostics and the unsupported-platform no-op path.

The source checkout's permission blocker was repaired by its owner. A real
`python3 scripts/shared_workspace.py fix` followed by `check` now reports the
`staff` group contract valid for the integration root, platform state and Git
common directory.

Semantic review found the implementation coherent with both delta specs:
enforcement is portable/no-op when POSIX semantics are unavailable, mutations
are realpath-bounded to managed state and Git metadata, atomic writes retain
group access, immutable Git objects remain group-readable, and all remote
mutators preflight before fetch/push/merge operations. The release/rollout
dependency was separated with explicit user approval because it is a post-merge
operation and cannot truthfully be completed before an immutable release
exists.

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review plus full unittest matrix, strict OpenSpec validation, managed-project validation, and real POSIX fix/check smoke
