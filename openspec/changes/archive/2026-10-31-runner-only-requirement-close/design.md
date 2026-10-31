## Context

The runner's retrospective job already records the Requirement checkpoint when the last child is closed (`integration_contour.run_retrospective`), and its terminal job closes the parent (`run_terminal`, `reconcile_composition`). Every other close or checkpoint requirement is redundant in coordinator mode.

## Decisions

- **Mode switch.** One predicate, the existing `execute_requirement._contribution_publication_supported` (coordinator lifecycle and queue enabled), decides: coordinator mode defers retrospective and close to post-merge jobs; otherwise behavior is unchanged (portable/light, map: same functions, finish as actor).
- **advance.** Single child: when the child is Done or merged, return `{"status": "await-post-merge", ...}` (or `done` when the parent Issue is CLOSED); the in-session `finish_task.py` path still publishes without a checkpoint. Legacy multi-child: same; shared publication without `require_checkpoint`. `_require_no_merged_composition` returns the `await-post-merge` result instead of raising.
- **Composition.** `require_final_gates` requires review, finalization and full-checks. `reconcile_composition` uses it after merge; the post-merge retrospective job for the composition runs before terminal in the chain, so the checkpoint exists when `reconcile_parent` reads it. The carried-gate branch disappears with the gate.
- **Stored pre-merge work.** `candidate_lifecycle` derivation raises `MalformedMarkerError` for a `retrospective` job with phase `pre-merge`, naming the PR; `job_record` refuses the phase. No compatibility path.
- **finish and shared candidate.** `reconcile_linked_parent` and `requirement_integration._reconcile_exact_merged` skip the parent close in coordinator mode and report that the post-merge jobs close it.
- **Recovery.** `requirement_terminal.py reconcile` is unchanged in code and documented as a coordinator recovery command.

## Risks

- A composition in flight with a pending pre-merge retrospective would fail derivation; the coordinator checks the overview for none before merge and holds merge until BR-799 is terminal.
- A Requirement whose runner obligation is exhausted needs `reoffer-post-merge` or the recovery command, as other post-merge work does.
