# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/spec delta against the diff, plus targeted, real-CLI and rendered-downstream checks
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- New-capability Purpose: `archive_content_problems` reads delta `## Purpose` for capabilities absent from `openspec/specs` (first creator in order), rejects missing/empty/TBD/TODO/FIXME/archive-sentence; `require_static_archive_readiness` raises it before review, checks, evidence or mutation (incl. `--finalize`).
- Committed package: `require_committed_package` runs for every non-finalize archive before review/checks; lifecycle evidence (review evidence, `automated-checks.json`, `evidence/`) is exempt; diagnostic lists paths and the commit command.
- Rehearsal and recovery: `rehearse_archive` runs archive + `validate --all --strict` on a copy of `openspec/`; `archive_with_recovery` captures `openspec/` and restores it exactly on a failed archive or post-validation, then exits non-zero with failing items and a rerun instruction. Strict validation is unchanged and still mandatory.
- Readable failures: `openspec_failure_summary`/`failing_lines` replace the 400-character tails in `post_review_finalization.trusted_archiver` and `_openspec`.
- Early readiness: `pr_review_gate.handoff_gates`, `requirement_composition.publish_composition` (before offering review), `execute_composition_review` (before reviewers) and `execute_composition_finalize` (before archiving any child) use the same predicate.
- Archive/hygiene exact-target exemption is unchanged; existing hygiene tests pass.
- Docs: platform and template `openspec-workflow.md`, `openspec/config.yaml` and the template config gain the `specs` Purpose rule and the commit-before-archive step.

## Checks actually run

- Targeted suites: `tests/test_openspec_lifecycle.py`, `tests/test_post_review_finalization.py`, `tests/test_requirement_contribution_composition.py`, `tests/test_pr_review_gate.py`, `tests/test_independent_review.py`, `tests/test_downstream_boundary.py`, `tests/test_machine_pool.py` pass (new tests: Purpose predicate, pre-mutation rejection, uncommitted package, rehearsal failure leaves tree unchanged, forced post-validation failure restores tree and rerun succeeds, failure summary, finalization error reporting, handoff and composition readiness).
- Real OpenSpec 1.13.2: new test `test_real_cli_new_capability_archive_has_no_tbd_and_validates_strictly` and the new `check_new_capability_purpose` fixture in `tests/openspec_1_13_regression.py` pass; `openspec validate --all --strict` on this checkout passes.
- Rendered downstream project (copier from this commit, `harness_mode=project`): archive without Purpose rejected before mutation; uncommitted Purpose fix rejected naming the file; after commit archive succeeded, main spec carries the authored Purpose, `validate --all --strict` passes, no `TBD`.
- Full `run_test_groups.py --all`: the archive-related failures from mocks/fixtures were fixed and their suites rerun green. Two `test_autonomous_integration_contour` window tests failed identically on clean `origin/main` (pre-existing time bomb: fixed 2026-10-0x dates aged out of the 14-day unattributed-event window after 2026-10-17); they blocked every selected-check run, so their fixtures now use dates relative to now (test-only repair, 56/56 pass). Authoritative selected-check evidence: `automated-checks.json`.

## Limitations

- Not exercised on a live downstream repository (terrazzo_mvp); that happens after release rollout.
- Pre-existing, out of scope: the template `rules.proposal` entry with an unquoted colon is parsed as a mapping, so OpenSpec ignores downstream proposal rules.
