OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-lifecycle delta, proposal, design and tasks; targeted unit tests with the real hook installed; downstream smoke `tests/reconcile_merge_hook_smoke.py` on a template rendered by copier with hooks installed by `agent_doctor.py`; `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle; local `public_distribution_snapshot_smoke.py` at candidate stage
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision 2026-10-23: variant A (scoped environment variable on the reconcile merge). Owner decision 2026-10-29: variant B (one-shot intent in the task worktree's own git directory), replacing A as the more reliable option; recorded in the ADD.
- Accepted boundary: the hook guards against accidental agent actions; a deliberately written intent with the exact commit is forgeable, and `DEV_PLATFORM_ALLOW_MERGE_COMMIT=1`, `git merge --no-verify` and finishing a refused or conflicted merge with `git commit` stay unchanged.

## Completeness

- Reconcile with the installed hook passes and leaves no intent: `tests/test_task_reconciliation.py` `test_installed_merge_hook_admits_only_the_reconcile_merge_in_a_task_worktree`; without the fix the same test fails with "merge commits in task worktrees are blocked" (reproduced on the unfixed tree, lehard/dev-platform#420).
- Conflicting reconcile leaves no intent: `test_conflicting_reconcile_leaves_no_intent`.
- Matching intent admits exactly one merge and is consumed: `tests/test_blocking_gates.py` `test_reconcile_intent_admits_the_matching_merge_once`.
- Another branch, another ref, a stale target, no intent with `DEV_PLATFORM_RECONCILE_MERGE=1`: `test_reconcile_intent_admits_no_other_merge`.
- Intent of another worktree: `test_reconcile_intent_of_another_worktree_admits_nothing`.
- Integration copy with an intent and the flag: `test_reconcile_intent_does_not_admit_a_merge_commit_in_the_integration_copy`.
- Downstream shape: `tests/reconcile_merge_hook_smoke.py` renders the committed template (multi-agent, pr), installs hooks through `agent_doctor.py`, shows the plain merge blocked, runs `finish_task.py --reconcile` (merge commit of the task head and `origin/main`, no intent left), shows an ad-hoc task merge and an integration-copy merge refused, `origin/main` untouched and the unpublished branch not pushed. Passed.

## Correctness

- The intent is written with `atomic_write_text` immediately before the single `git merge --no-edit origin/<main_branch>` and removed in `finally`; its target is the commit `origin/<main_branch>` resolves to at that moment, and reconcile's existing re-observation still refuses a moved main.
- The hook reads `main_branch` from the worktree's `.dev-platform.toml`; an unreadable value refuses the merge with a named reason.
- `blocking-gates.toml` known gap 3 is resolved and corrected: committing a resolved reconcile conflict uses `git commit`, which does not run `pre-merge-commit`.

## Coherence

- `template/docs/engineering/agent-workflow.md.jinja` documents the admission and the `git commit` path; the hook message names reconcile instead of rebase.

## Test adaptation

- The first candidate-stage snapshot smoke failed in `test_shared_writer_guard` because the intent was written with a direct `write_text`; it now uses the shared `atomic_write_text`, and the rerun of the smoke passed (18 groups).

## Not verified here

- Confirmation on a real downstream project with an installed platform release: possible only after a release containing this change; to be done as a post-release step (reconcile of a diverged task with a published PR on a managed project).
- `tests/reconcile_merge_hook_smoke.py` is an on-demand smoke and is not wired into CI.
