OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the delegated executor's diff against the queue-regenerates-generated-files deltas (publication-queue, completion-lifecycle), proposal, design and tasks; targeted unit tests; repository-owned selected checks on the candidate head
Automated-Checks-Evidence: automated-checks.json

## Owner decision

During implementation the supervisor found that regenerating the manifest changes the task-content identity of an archived queue candidate. This would make the derived merge refuse and reset content-bound gates (the lehard/dev-platform#628 effect). The owner chose, verbatim: «Вариант A: включи в I2 исключение объявленных сгенерированных файлов из task-content identity (объявление читать из main, только файлы, которые проверяет обязательный CI-чек), с тестами на архивированном кандидате.» The coordinator relayed the bounds: the exclusion applies to review and composition identity; other task paths stay; a declaration without a required check fails explicitly; tests use an archived candidate. The OpenSpec package was updated before implementation (`design.md` "Owner decision 2026-10-22", completion-lifecycle delta, tasks 3.x).

## Implementation

A delegated native Claude executor (standard route, sonnet) wrote all code and tests in two rounds; the second round implemented the owner decision. Containment postcheck: clean.

- `template/scripts/post_review_finalization.py`: `rederive_archived_specs` is one derived merge. It re-derives archive-derived specs and regenerates each declared generated file that is conflicted or changed on both sides. The declared `regenerate` argv runs with cwd = the trusted default-branch root, `{tree}` = the disposable checkout and a credential-free environment. A failure, OS error or missing output raises `RederivationFailed`. The parents and both-sides bounds now cover spec ∪ generated paths. `derived_merge_only` takes the generated paths from the caller. `prepare_derived_specs` reads the declaration from the trusted root.
- `template/scripts/publication_queue.py` `_prepare` routes to the derived merge when:
  - a declared generated path changed on both sides;
  - only derived specs overlap (the existing case);
  - the merge conflicts only in derived or generated paths.

  Any other conflict raises `IntegrationRepairNeeded`, a clean merge goes through `update-branch`, and the declaration is read from the trusted root.
- `template/scripts/_platform_common.py`: `GeneratedFile(path, regenerate, check)`. An entry needs exactly `path`, `regenerate` and `check`, and `" ".join(check)` must be in `[settings].full_commands` at that commit. Otherwise it raises, naming the file and the check.
- `template/scripts/task_content_identity.py` `review_exclusion` also excludes declared generated paths, read at `merge-base(HEAD, origin/<main_branch>)`. A missing `main_branch` or merge base raises. Review identity, composition identity and the review path partition inherit the exclusion.
- `template/scripts/requirement_composition.py`: the sandbox child clone receives `refs/remotes/origin/<main>` from the composition checkout, so child identity can read the declaration. A missing `main_branch` raises.
- `dev-platform/checks.toml`: the manifest entry has `check = ["python3", "scripts/generate_platform_manifest.py", "--check"]`, which is added to `full_commands` (with a matching evidence type).
- Docs: one sentence each in `docs/engineering/agent-workflow.md` and `docs/engineering/openspec-workflow.md`. The manifest is regenerated.

Supervisor review checked:
- worker and queue checkouts are plain clones, so `origin/<main>` exists for the identity merge base;
- no caller converts the new explicit errors into "unknown identity".

## Completeness

publication-queue delta:
- Manifest-only conflict integrates: `test_neighbouring_entries_integrate_with_a_regenerated_file_from_trusted_code`, `test_both_sides_change_of_a_declared_generated_file_is_derived_merged` and `test_conflict_only_in_derived_and_generated_paths_is_derived_merged`. The update marker is recorded by the `prepare_derived_specs` test.
- Ordinary-file conflict goes to integration repair: `test_ordinary_file_conflict_is_not_resolved_and_nothing_is_pushed` and the PreparationTests ordinary-conflict case.
- Regeneration fails: `test_failed_regeneration_names_the_file_and_pushes_nothing`, `test_missing_generated_output_fails_explicitly` and the PreparationTests regeneration-failure case.
- No candidate code runs: the fake generator exists only in the trusted repository and logs its cwd; also `test_generated_files_require_a_trusted_root`.
- Unrecorded-update recovery: `test_merge_differing_only_in_a_declared_generated_path_is_recognized`.

completion-lifecycle delta:
- Manifest-only regeneration on an archived candidate keeps identity and gates: `ArchivedGeneratedMergeTests.test_regenerating_only_the_manifest_keeps_identity_and_gates_reusable` and `GeneratedFileExclusionTests.test_regenerating_only_the_manifest_keeps_the_identity_and_the_proof_equivalent`.
- An ordinary task path changes together with the manifest: `test_an_ordinary_task_path_changing_with_the_manifest_changes_the_identity` (identity) and `test_an_ordinary_task_path_changed_by_the_merge_stops_the_merge` (queue).
- A candidate's own declaration is ignored: `test_a_declaration_only_in_the_candidate_is_ignored`.
- No required check fails explicitly: `test_a_declaration_whose_check_is_not_a_full_command_fails_explicitly` and the reader cases in `tests/test_task_freshness.py`.
- `test_declared_generated_file_is_not_task_content_but_every_other_path_is` and `test_an_unreadable_merge_base_fails_explicitly`.

## Correctness and coherence

- The declaration and the regeneration code always come from main or the trusted default-branch checkout, never from the candidate.
- Rollout cost (recorded in design): candidates in flight that changed the manifest get a new identity once, because the manifest leaves their digest.
- Downstream projects without `[[generated_files]]` keep identical identity digests. A downstream `.dev-platform.toml` without `main_branch` now fails explicitly in identity, but the rendered template always sets it.

## Checks

- Targeted modules, machine pool unset: test_post_review_finalization, test_publication_queue, test_task_freshness, test_select_checks, test_platform_manifest, test_task_content_identity, test_managed_checkout_identity, test_openspec_lifecycle, test_pr_review_gate, test_template_contract, test_requirement_contribution_composition and test_blocking_gates ran 566 tests, OK.
- Repository-owned selected checks: `select_checks.py --base origin/main --execute --contribution-base 8a13069166e411bd197245c327216aee28c0287a --evidence openspec/changes/queue-regenerates-generated-files/automated-checks.json`, recorded in `automated-checks.json` for the final task content.
