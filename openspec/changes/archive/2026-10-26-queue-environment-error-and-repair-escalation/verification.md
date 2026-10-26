OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the queue-environment-error-and-repair-escalation publication-queue delta, proposal, design and tasks; targeted unit tests run before and after the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-768, owner decision of 2026-10-26 (relayed by the backlog-revision session; the earlier variant A and the background repair agent were withdrawn): an environment failure of the queue's derived merge is an explicit queue error naming the cause, never an integration-repair job; a repair that needs a writer is escalated by the queue as "Repair needed, PR #N" with its reason and is run manually by the operator; no background agent and no automatic writer launch. The LLM-free hosted integration-merge kind is the next child.

## Implementation

- `template/scripts/post_review_finalization.py`: `RederivationEnvironmentFailed` (deliberately not a `RederivationFailed`). A missing OpenSpec CLI and a regeneration command that cannot start raise it directly. A regeneration that fails on the merged tree is probed once over a pristine detached worktree of the fetched main (`rederive-main-probe`); failing there as well raises it, succeeding there keeps `RederivationFailed` (integration repair). The probe runs only on the failure path.
- `template/scripts/publication_queue.py`: `QueueEnvironmentError` (deliberately not a `QueueError`, like `AttentionError`). `_prepare` maps the environment failure to it; `_integrate` releases `publication:active` and re-raises it without a block, a state record or a job; `worker` collects it per candidate, evaluates the rest and returns `environment-error` (not a progress state, so `main` exits 2) naming every cause, carrying another candidate's progress outcome as `progress`.
- `publication_queue._transition` posts `ensure_attention` for `repair-pending` and `integration-repair-pending` as for `blocked-escalation` (once per exact round, a lost comment re-posted on the next observation of the same round). `attention_body` renders `repair_attention_body`: "Repair needed: PR #N", reason, head, evidence, attempts and `lifecycle_workers.py work-next --repo <repo> --kinds <kind> --writer claude-sandboxed --run`. The published job stays claimable.
- Docs: the repair placement of `docs/engineering/hosted-lifecycle-workers.md`. The platform manifest is regenerated.

## Completeness

Delta scenarios:
- Candidate conflicts only in the generated manifest; Conflict in an ordinary file: unchanged behavior, existing `GeneratedFileMergeTests` pass.
- Regeneration fails (merged tree only): `test_failed_regeneration_names_the_file_and_pushes_nothing` now exercises the main probe (the candidate's `fail-generation` file is absent on main) and still gets `RederivationFailed`; `test_candidate_regeneration_failure_stays_integration_repair` maps it to `IntegrationRepairNeeded`.
- Regeneration environment is missing: `test_regeneration_failing_on_pristine_main_is_an_environment_failure` (absent Python module, head unchanged), `test_unstartable_regeneration_command_is_an_environment_failure`, `test_missing_openspec_cli_is_an_environment_failure`; queue side `test_environment_failure_is_a_queue_environment_error` (no GitHub write), `test_integrate_releases_ownership_and_records_nothing` (no transition, job or block), `test_worker_tries_the_rest_and_fails_the_run_naming_the_cause`.
- Integration repair is offered / Review findings need repair / Same round observed again: `RepairAttentionTests` (one comment with the integration-repair command; the repair command; no second comment for the same round, a lost one re-posted). The review path reaches it through `pr_review_gate.offer`, which calls `adapter._transition(..., "repair-pending")`.

All tasks in `tasks.md` are complete; 3.2 is this receipt together with the selected checks.

## Correctness and coherence

- Before the change, the existing suites `tests/test_post_review_finalization.py`, `tests/test_publication_queue.py` and `tests/test_autonomous_integration_contour.py` passed with the implementation in place (249 tests); the new tests pass (7 queue, 3 rederivation).
- The probe's verdict is structural (the same trusted command over main's own tree), not a guess from stderr text.
- Limitations, stated truthfully: no real hosted queue run was exercised; the worker loop and `_integrate` are covered with patched collaborators. A `git worktree add` failure of the probe is a harness `WorkerError`, which `prepare_derived_specs` already maps to `RederivationFailed` (unchanged pre-existing mapping, reported, not altered).
- Out of scope and not changed: the LLM-free hosted integration-merge kind, the Compose end-to-end regression.
