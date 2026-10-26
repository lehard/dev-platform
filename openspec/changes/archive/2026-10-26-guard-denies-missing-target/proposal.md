## Why

The structured-write guard rendered by `delegated_write_guard.render_pretooluse_guard_script` answers `allow` when a guarded Write/Edit/NotebookEdit payload carries none of `file_path`, `path`, `notebook_path`. That is a silent fallback in a containment control: an unverified write passes.

Slice A of Requirement BR-780 (variant A, relayed by the backlog-revision session on 2026-10-26). The contribution-without-cache part of the Requirement is out of scope here and stays open on the Requirement.

## What Changes

- The guard denies a payload without a recognized target key, with a reason naming the expected keys.
- The test that pinned the old `allow` is replaced by a deny test.

## Impact

- `template/scripts/delegated_write_guard.py`, `tests/test_delegated_write_guard.py`, generated platform manifest.
- Spec `platform-delegation`: new scenario under "Delegated writes are contained to the assigned worktree".
