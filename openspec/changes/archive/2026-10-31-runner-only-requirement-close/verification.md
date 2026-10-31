OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the agent-workflow and platform-lifecycle deltas, proposal, design and tasks; targeted unit tests over 17 affected test files (678 passing); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring; ADD approved by the chat coordinator under the owner's delegation (2026-10-31): BR-943 is a separate Requirement after this one; `requirement_terminal.py reconcile` stays a coordinator recovery command; no compatibility for stored pre-merge retrospective work. The ADD evidence was refreshed twice after `main` advanced, content unchanged.
- One predicate, `requirement_terminal.post_merge_closes` (coordinator lifecycle with the queue enabled), switches advance, finish and the shared-candidate publisher; `execute_requirement._contribution_publication_supported` now delegates to it.
- Without the pre-merge job the finalize job of a composition calls `advance_final_publication` (full final-head checks, ready, undraft, admission) right after recording `finalized`; the composition post-merge retrospective job records the Requirement checkpoint after every child and the composition, before terminal reconciliation reads it.
- The scenario "A finalized composition receives its parent retrospective" keeps its name and changes its content: OpenSpec refuses a MODIFIED block that drops a scenario.
- lifecycle-workers, publication-queue and chat-coordinator spec deltas are deferred while stream B has them in flight (coordinator instruction); the code no longer derives pre-merge work, which those specs only mention in passing.

## Completeness

- advance: `test_coordinator_mode_leaves_retrospective_and_close_to_post_merge_jobs` (await-post-merge with no checkpoint and no `reconcile_parent`; `done` for a CLOSED parent; portable mode still closes); `test_merged_composition_awaits_post_merge_without_touching_the_branch`, inventory tests for `_merged_composition`.
- finish: `LinkedParentReconciliationTests` (coordinator mode leaves the parent; portable mode closes it).
- Composition: `test_finalized_composition_goes_to_full_checks_without_a_requirement_retrospective`, `test_carried_composition_is_ready_without_the_local_receipt_file`, `test_full_final_head_checks_precede_ready_and_admission`, `test_final_gates_require_archive_and_exact_checks_but_no_retrospective`; `CompositionFinalizeTests` (finalize drives final publication, publishes no job); `CompositionPostMergeRetrospectiveTests` (checkpoint recorded after children and composition).
- Stored pre-merge work: `RemovedPremergeRetrospectiveTests` (job records take no phase; a record carrying one fails naming the PR).
- Docs: AGENTS.md (line replaced, 120 lines), task-intake, agent-workflow, chat-coordinator, template agent-workflow and task-intake, explorer feedback-learning and requirement-intake nodes; platform manifest regenerated.

## Correctness

- No fallback: a stored pre-merge job fails explicitly; a missing Requirement checkpoint still blocks `reconcile_parent`; the coordinator-mode decision reads the existing lifecycle and queue configuration and fails as before when it is invalid.
- Portable mode keeps the checkpoint requirement and the in-session close through the same functions.
- Post-merge chain order (retrospective before terminal reconciliation) guarantees the checkpoint exists when the composition terminal job closes the Requirement.

## Coherence

- Spec deltas, proposal, design, tasks and docs describe one closer; `requirement_terminal.py reconcile` is documented as recovery everywhere it appears.

## Not verified / limits

- Not exercised against a live composition or a live runner round; the first real Requirement after merge is the field check.
- Delivery precondition held by the coordinator: no open composition candidate awaits a pre-merge retrospective and BR-799 is terminal.
- The legacy shared-candidate publisher in coordinator mode no longer closes the parent; no open Requirement uses that path (checked: only single-child receipt directories are open).
