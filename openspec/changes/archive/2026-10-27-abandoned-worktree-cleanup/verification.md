OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the abandoned-worktree-cleanup worktree-coordination delta, proposal, design and tasks; targeted unit tests on Python 3.13 and 3.11 with real git worktrees and a stubbed GitHub lookup; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-771 fourth slice, scoped by the coordinator on 2026-10-27 with technical choices delegated: supported removal of an abandoned (closed without merge) candidate including its worktree, built on top of the BR-778 board-doctor merge-proof logic without weakening it. Contribution re-base on a moved requirement branch was split off as a fifth slice.

## Implementation

- `template/scripts/publication_state.py`: `ExactHeadPrLookup.exact_closed` is the PR of the branch/base whose exact head is CLOSED (not merged); more than one makes the lookup unavailable. Existing fields and callers are unchanged.
- `template/scripts/worktree_cleanup.py`: `cleanup --abandoned` with the exact `--worktree/--branch/--head` target (argparse and `cleanup()` refuse it with `--all`/`--apply` or a partial target). `_abandoned_refusal` checks, in order: not the integration copy, inside the managed worktree directory, registered with the exact branch and head, not locked/prunable, process check available and no cwd inside it, clean status, local branch ref equals the head, head not contained in main (`merged-into-main: use ordinary cleanup`), at most one board claim naming the worktree and with the same branch (`board-identity-mismatch`), GitHub provider and authentication, an available lookup, no exact merged PR, no exact or stale open PR, and an exact closed PR. Only then `_cleanup_abandoned` runs `git worktree remove` (no force), `git branch -D`, and releases the proven board entry under `locked_json`, re-checking it is unchanged. Result `completed`/`refused`/`failed` with `pr`, `removed`, `released_claim`, `errors`; `refused`/`failed` exit 1 through the existing `cleanup_failed`. `main_branch` comes from `require_main_branch` (no default).
- `agent_board.py` (doctor, `_safe_to_remove`, unproven-merge reasons) is not changed; scan and `cleanup --all` never infer abandonment.

## Completeness

- Closed exact PR: `test_closed_exact_pr_removes_worktree_branch_and_exact_claim` (worktree and branch gone, only the exact claim released, other claim kept, PR number reported, lookup called with the exact identity).
- PR open, merged or missing: `test_open_merged_or_missing_closed_pr_refuses` (exact open, stale open, exact merged, none closed, lookup unavailable; nothing removed, non-zero result).
- Unsafe local state: `test_unsafe_local_state_refuses_before_github` (dirty, active process, process check unavailable, identity mismatch; GitHub not consulted), `test_head_already_in_main_is_ordinary_cleanup`, `test_board_claim_with_another_branch_refuses`.
- GitHub evidence unavailable: `test_github_authentication_is_required` and the unavailable-lookup case.
- Argument validation: `test_abandoned_requires_one_exact_target`.
- Lookup: `test_closed_unmerged_pr_with_same_head_is_only_reported_as_exact_closed`, `test_multiple_exact_closed_prs_are_unavailable`.

All tasks in `tasks.md` are complete; 3.2 is this receipt together with the regenerated platform manifest and the selected checks.

## Correctness and coherence

- `tests/test_worktree_hygiene.py`, `tests/test_task_reconciliation.py`, `tests/test_shared_writer_guard.py` (95 tests) and `tests/test_publication_state.py` (45) pass on 3.13; the new class and `test_publication_state` pass under Python 3.11; `compileall` under 3.11 and `ruff` clean.
- The board write uses the shared `locked_json` helper, so the shared writer baseline is unchanged.
- Limitation: GitHub PR state is stubbed in the cleanup tests; the lookup classification is tested through the fake `gh` list fixture.
