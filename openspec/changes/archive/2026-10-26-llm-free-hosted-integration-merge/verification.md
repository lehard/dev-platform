OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the llm-free-hosted-integration-merge lifecycle-workers and publication-queue deltas, proposal, design and tasks; targeted unit tests run during the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-768, owner decision of 2026-10-26, item 2 (relayed by the backlog-revision session): a candidate with no conflict outside derived paths and no red required gate is integrated in hosted CI by a clean merge of main, without `--llm-command` and without a writer; the `UNHOSTED` refusal is lifted only for this kind. Enabling the hosted class (`DEV_PLATFORM_HOSTED_KINDS`) remains an owner step and is not changed here.

## Implementation

- `template/scripts/lifecycle_workers.py`: `integration-merge` in `JOB_KINDS` (`MERGE_ONLY_KIND`), not a writer kind; `work-next --run` needs no `--llm-command` or `--provider` for it; dispatch passes no writer command, launch or provider.
- `template/scripts/integration_contour.py`: `run_claimed_integration_repair` accepts the kind, refuses a writer command, launch or provider for it, and skips the provider requirement; `execute_integration_repair` returns `failed` naming the conflicts (or the red required checks) before any writer for it; the failure path drops `merge_only` from the red gate, so the next attempt is a writer `integration-repair` (or a block at the bound).
- `template/scripts/publication_queue.py`: `IntegrationRepairNeeded(merge_only=...)`; a candidate-reason derived-merge failure is merge-only when `merge_conflicts(head, current main)` is empty. `_integration_repair` records `merge_only: true` on the red gate and publishes `integration_job_kind(red_gate)`; the interrupted-offer republish uses the same function; `publish_job` keeps the red gate for the kind; `needs_attention` skips the "Repair needed" comment for a merge-only round.
- `template/scripts/candidate_lifecycle.py`: validated-push recovery of an `integration-repair-pending` merge-only round matches the `integration-merge` job.
- `template/scripts/hosted_workers.py`: class `integrate` (`integration-merge`, no provider, no tools, contents and pull-requests write); `integrated` is a resulted hosted outcome. The workflow is unchanged: it installs the Claude CLI and passes the provider secret only for `review`.
- Docs: class table, token paragraph and placement table of `docs/engineering/hosted-lifecycle-workers.md`. The manifest is regenerated.

## Completeness

lifecycle-workers delta:
- Class token rights / allowed triggers / no merge: unchanged workflow; `test_classes_in_the_table_have_a_workflow_branch` requires the same permissions for `integrate` and no `integrate` branch (no install, no secret).
- LLM-free integration merge enabled: `test_llm_free_integration_merge_has_its_own_class_without_a_provider`, preflight `test_valid_configuration_passes_every_phase_for_every_class` (now with `integrate`), `test_integration_merge_runs_without_an_llm_command_while_integration_repair_needs_one`; outcomes `job-integrated` / `job-failed` in `test_outcomes_are_distinct_and_failures_are_red`.
- Kind without a hosted executor: `test_kinds_without_a_hosted_executor_are_refused_with_their_basis` unchanged; `integration-repair` stays in `UNHOSTED`.

publication-queue delta:
- Derived merge failed but the plain merge is clean: `test_candidate_regeneration_failure_stays_integration_repair` (`merge_only` true), `test_clean_trial_merge_after_a_failed_derived_merge_offers_an_llm_free_integration_merge` (state, flag, job without providers, no attention comment), `test_interrupted_merge_only_offer_republishes_the_integration_merge`.
- Integration merge succeeds: `test_clean_integration_merge_pushes_the_merge_of_main_without_a_writer` (real repositories; the runner refuses any non-git process; parents are the claimed head and main).
- Integration merge meets a conflict: `test_integration_merge_meeting_a_conflict_starts_no_writer_and_offers_integration_repair` (named conflict, no push, next job `integration-repair` attempt 2 with the route provider), plus `test_integration_merge_refuses_a_writer_command`.
- Real conflict keeps integration repair: `test_derived_merge_failure_with_a_conflicting_trial_merge_needs_a_writer` and the existing conflict tests.
- Integration merge needs no repair comment: covered in the offer test above; the T1 `RepairAttentionTests` still pass for writer rounds.
- Recovery keeps the kind: `test_validated_integration_merge_push_is_recovered_by_its_own_job`.

All tasks in `tasks.md` are complete; 4.2 is this receipt together with the selected checks.

## Correctness and coherence

- `tests/test_autonomous_integration_contour.py`, `tests/test_hosted_workers.py` and `tests/test_publication_queue.py` passed together (245 tests) after the change; the first run exposed that `publish_job` dropped the red gate for any non-repair kind, which would have lost the merge-only mark, fixed before the run. The first selected-check run also exposed that the new CLI test registered the process-wide friction sink (`work-next --run`) and broke later tests; the test now patches it.
- Limitations, stated truthfully: no real hosted workflow run of the `integrate` class was exercised; it is not enabled until the owner adds `integration-merge` to `DEV_PLATFORM_HOSTED_KINDS`. A failed GitHub branch update with a clean trial merge stays integration repair as the delta states.
- Out of scope and not changed: the Compose end-to-end regression.
