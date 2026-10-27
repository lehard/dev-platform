OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the worktree-cleanup-truthful-failure worktree-coordination delta, proposal, design and tasks; targeted unit tests run during the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-771 first slice, scoped by the backlog-revision session on 2026-10-27 with technical choices delegated: `worktree_cleanup.py` must not report success for a failed or refused cleanup (revision item 3, first half). The abandoned unmerged worktree and the other revision items stay later slices.

## Implementation

- `template/scripts/worktree_cleanup.py`: `_cleanup_target` reports `failed` when errors were recorded (it reported `completed`). `main` returns `1 if cleanup_failed(payload) else 0`; `cleanup_failed` is true for a non-empty `errors` list or status `refused`/`failed`, so a targeted and a global cleanup with an error or refusal exit non-zero. Global `completed-with-errors` is kept as the status name.
- The post-merge `cleanup` job (`integration_contour.local_cleanup`) already reads `errors` and is unchanged.

## Completeness

- Targeted cleanup fails: `test_caller_worktree_cleanup_is_deferred_then_recovered_idempotently` now asserts `failed` for the active-process block; `test_cleanup_command_exits_non_zero_on_any_error_or_refusal` exits 1 for a failed target.
- Global cleanup with an error: the same test, `completed-with-errors` exits 1.
- Refused global preview: the same test, refused `--all` exits 1 (a refused target too).
- Clean cleanup: completed and already-cleaned targets and a clean `--all --apply` exit 0.

All tasks in `tasks.md` are complete; 2.2 is this receipt together with the selected checks.

## Correctness and coherence

- `tests/test_worktree_hygiene.py` (58 tests) passes with the change.
- Limitation: the exit-code test drives `main` with a patched `cleanup` payload; the status change is covered by a real repository fixture.
