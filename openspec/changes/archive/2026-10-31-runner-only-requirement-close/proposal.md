## Why

The owner-approved lifecycle map (decision 2) makes the post-merge runner the only actor for the Requirement retrospective and close. Today the checkpoint is required before publication by `advance`, a separate pre-merge retrospective job gates composition admission, and the parent is closed from `advance`, `finish`, the shared-candidate publisher, recovery and the runner's terminal job.

## What Changes

- Coordinator mode: `advance` never requires the Requirement checkpoint and never calls `reconcile_parent`; after every mandatory child (or the composition PR) merged it returns `await-post-merge`; a closed parent returns `done`. A merged composition reports `await-post-merge` instead of failing.
- Coordinator mode: `finish_task.reconcile_linked_parent` and the shared-candidate publisher/recovery no longer close the parent.
- The pre-merge composition retrospective is removed: finalization publishes no pre-merge job; `advance_final_publication`, `require_final_gates` and `reconcile_composition` drop the `requirement-retrospective` gate; `run_claimed_retrospective`, `_offer_premerge_retrospective`, `premerge_retrospective_attempt`, the worker dispatch branch and the resume path are deleted.
- Derivation of a stored `retrospective` job with phase `pre-merge` fails naming the PR.
- Portable mode (no queue) keeps closing in session through the same functions.
- Docs: task-intake, agent-workflow, chat-coordinator, hosted-lifecycle-workers.

## Impact

- `template/scripts/{execute_requirement,finish_task,requirement_composition,post_review_finalization,lifecycle_workers,candidate_lifecycle,pr_review_gate,requirement_integration,requirement_merge_recovery}.py`, tests, docs, manifest.
- Specs: agent-workflow (2 modified), platform-lifecycle (2 added, 1 modified).
- Delivery precondition (coordinator): no open composition candidate awaits a pre-merge retrospective, and BR-799 is terminal.
