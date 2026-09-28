# Verification: isolated disposable repository sandboxes

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review of the authored outcome, design, three requirements and scenarios against the implementation, focused regression tests and agent guidance.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Outcome and completeness: `create` uses a local clone without Git object hardlinks and only reports success after verifying a standalone `.git`, no alternates or `commondir`, no hardlinked regular files, and no symlink outside the exact copy. `verify` and `cleanup` require the ownership marker and exact root/name binding. This covers both Git objects and workspace files.
- Correctness: `cleanup` runs verification before deletion and leaves an unsafe copy in place. A plain local clone with hardlinked loose objects is rejected while the source object's mode and contents remain unchanged. Linked metadata, alternates, outside and sibling symlinks, and hardlinked workspace files are rejected. Source and template guidance invoke the same helper and prohibit unsafe fallback cleanup.
- Coherence: the helper uses Git, Python filesystem operations and a thin central wrapper. It does not touch integration or sibling worktrees, alter normal Git clone behavior, or add a daemon or virtual filesystem. The conservative link-count rule can reject an internally hardlinked file; this is an intentional fail-closed limit.

## Checks actually run

- `python3 -m unittest tests.test_disposable_repository_sandbox -v`: 5 passed.
- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: OK, 3 managed projects.
- `python3 scripts/run_test_groups.py --all`: 14/14 groups passed, 1408 tests discovered and assigned.
- `openspec validate isolate-disposable-repository-sandboxes --strict`: valid.
- `python3 template/scripts/openspec_lifecycle.py check`: OK.
- `python3 scripts/check_docs_links.py`: no problems.
- `python3 scripts/render_agents_md_smoke.py`: 3 profiles OK.
- `python3 -m ruff check scripts/disposable_repository_sandbox.py template/scripts/disposable_repository_sandbox.py tests/test_disposable_repository_sandbox.py`: passed.
- `git diff --check`: clean.

The archive helper generates `automated-checks.json`; the marker above names that required output and does not claim it exists before archiving.
