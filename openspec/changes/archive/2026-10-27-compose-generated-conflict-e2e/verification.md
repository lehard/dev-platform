OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the compose-generated-conflict-e2e publication-queue delta, proposal, design and tasks; targeted test runs on Python 3.13 (pytest) and 3.11 (unittest) during the change; a mutation run of the derived-merge route; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Implementation

- `tests/test_autonomous_integration_contour.py`: `ComposeGeneratedManifestConflictTests` builds real repositories: a source with a sealed Requirement composition manifest and two integrated children (the `Repository` builder of `tests/test_requirement_contribution_composition.py`), each child archived with a delta spec and its materialized current spec, the first child adding an entry to the declared generated file `template/dev-platform/platform-manifest.json`; a main that adds a neighbouring entry after admission; a bare remote; and a trusted default-branch clone that carries the `[[generated_files]]` declaration and the generator. GitHub I/O (`_pr`, `_comments`, `_gh`, labels, the merge `gh api` call) is faked; `publication_queue.worker` runs unmocked through `_integrate`, `_prepare`, `merge_conflicts`, `generated_files` and the real `prepare_derived_specs` / `rederive_archived_specs` (source URL redirected to the bare remote).
- Production code is unchanged: the scenario passed on the first full run, so no defect was found.

## Completeness

publication-queue delta, scenario "Requirement composition conflicts with main only in the generated manifest":
- GIVEN: the trial merge conflicts only in the manifest (`merge_conflicts(head, main) == [manifest]`), the candidate is `ready` with its real composition identity.
- WHEN / THEN: one `worker` run returns `merged`; the derivation took the composition branch (archived deltas replayed in manifest child order `first`, `second`; fast-forward push), the branch head is a merge whose parents are the admitted head and main, the manifest is regenerated to `base, first, main`, the merge changes only `entries/main.txt` and the manifest against the admitted head, and the composition task-content identity is equivalent before and after (`equivalent_proofs` on a fresh clone of the merged head). One coordinator `update` record names admitted head, merged head and main.
- AND: no `update-branch` call, no integration-repair attempt, no "Repair needed" comment, the next job after merge is `retrospective`; the merge was issued with the merged head SHA.

All tasks in `tasks.md` are complete; 2.1 is this receipt together with the selected checks.

## Correctness and coherence

- Mutation check: with the derived-merge route in `_prepare` disabled, the test fails with `waiting: merge of current main conflicts in: template/dev-platform/platform-manifest.json`, i.e. it detects exactly the 2026-10-22 failure mode (operator merge needed). The source was restored from Git before commit.
- `tests/test_autonomous_integration_contour.py` and `tests/test_requirement_contribution_composition.py` passed on Python 3.11 (124 tests, unittest).
- Limitations, stated truthfully: boundaries with their own coverage stay mocked — composition final-gate proofs (`require_composition_finalized`, `refresh_composition_checks`), the required-check observation, `_require_finalized` (fetches `pull/N/head`), and the OpenSpec CLI (the archived-delta replay is a deterministic stand-in equal to `openspec archive` for capabilities main did not touch; validation is a no-op), because CI unit tests do not install the OpenSpec CLI. No real GitHub merge or hosted run was exercised.
- Out of scope and not changed: enabling the hosted `integration-merge` class (owner step), any automatic writer.
