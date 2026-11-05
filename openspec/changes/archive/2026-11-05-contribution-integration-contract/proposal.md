## Why

Delivering a multi-child Requirement needed coordinator workarounds. A conflicted contribution waits forever for exact-head checks that GitHub does not start on a DIRTY PR. Freshness compares a contribution with main. Review stays bound to the start-time contribution base, so content merged from the requirement branch is attributed to the child. completion-lifecycle and platform-lifecycle state different bases and neither names the contribution case.

## What Changes

- Contribution integration evaluates content gates, then the conflict with the target, and only then exact-head required checks; a conflict becomes integration-repair-pending.
- `execute_requirement.py absorb-main --requirement owner/repo#N` merges main into the requirement branch by fast-forward push, refusing a queue-owned composition or a conflict.
- Task status, finish, reconcile, handoff and selected checks of a contribution measure freshness against its target branch.
- The contribution base moves only through a proven transition (reconcile, integration repair); gates survive only for equivalent or target-only content.
- Selected checks of a contribution run on its contribution base; the merge-base rule stays for main-target candidates.

## Impact

- `template/scripts/{requirement_contributions,integration_contour,post_review_finalization,pr_review_gate,publication_queue,task_reconciliation,project_publish,select_checks,execute_requirement,requirement_child_context}.py`, `scripts/dogfood_task.py`, docs, tests, manifest.
- Specs: publication-queue, platform-lifecycle, completion-lifecycle.
