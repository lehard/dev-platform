# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual walk of every scenario in the delta against the code and tests/test_delivery_trace.py, tests/test_task_reconciliation.py, tests/test_portable_finish_check_reuse.py and tests/test_independent_review.py; selected checks and strict `openspec validate` ran locally; live probes on the real PR lehard/dev-platform#950, closed without merge.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## What was checked

- First publication adds an empty commit with a valid trace and the same subject, and publication binds that head: `EnsureTests`.
- A traced head gets no second commit; a project without the setting or without a check configuration file gets none; a non-boolean setting stops naming it: `EnsureTests`.
- The trace commit keeps the checkpoint proof (`test_quick_checkpoint_proof_survives_a_merge_only_reconcile_but_not_an_edit`), the selected-check evidence for quick and managed tasks (`test_the_delivery_trace_commit_keeps_the_evidence`) and the review evidence (`test_the_delivery_trace_commit_needs_no_second_review`).
- Reconcile keeps the trace of a traced published head and gives none to a head without one: `test_a_traced_published_head_keeps_its_trace_across_reconcile`, `test_reconcile_gives_no_trace_to_a_head_that_had_none`.
- The guard passes a traced head, refuses a missing, repeated or mismatched trailer with the reason and the next command, stops on an unknown head, and reads the named head rather than the merge commit: `CheckTests`.
- The step reads `github.event.pull_request.head.sha`, runs before the unit tests, and no rendered workflow or template check file has it: `BoundaryTests`.

## Live probes on lehard/dev-platform#950

- Head without a trace, opened with `gh pr create`: `validate` failed at the guard in 7 s naming the reason and `python3 scripts/dogfood_task.py finish`.
- New traced head on the same PR: the guard step passed.
- Head whose tree differs from its trace: `validate` failed naming both trees.
- Head that removes the step from `ci.yml`: the run continued without the step, which is the documented way out.
- An earlier probe head with the tree of main also passed, because that tree has no step yet; it shows the same way out.

## Not checked here

A live `reconcile` on a real PR was not run before merge: a probe worktree outside the reviewed workspace roots was refused by the workspace hook. Reconcile is covered by the tests above with real Git and a bare remote. The writer runs live in this delivery's own `finish`.
