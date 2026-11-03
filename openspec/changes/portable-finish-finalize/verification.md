# Verification: portable-finish-finalize

OpenSpec-Verify: BLOCKED
Verification-Method: documented equivalent manual review of the proposal, design, completion-lifecycle delta, tasks and implementation; targeted regression tests and structural OpenSpec validation. Required full validation and independent runtime review remain blocked.

## Semantic assessment

- Portable finish invokes required independent review and shared developer-context `finalize_change` before archived-provenance/publication gates, then commits the archive.
- Portable Requirement advance finalizes completed, verified active children before creating ready receipts. It re-resolves canonical provenance and explicitly fails if finalization did not produce an archive.
- Developer archive refuses in both lifecycle modes before target validation or archive work. The trusted `--finalize` queue entry remains available.
- Selected checks use the existing finish evidence-reuse rule. The light-project regression executes checks once, commits the archive and reuses that evidence during finish validation.
- Portable review remains required with the optional setting disabled. Queue and portable review share runtime preflight and perspective launches. Queue snapshot containment still rejects reviewer writes.
- No material conflict with the authored contract was found. This assessment is not an independent model review or a terminal-delivery receipt.

## Passed checks

- `python3 -m compileall -q template/scripts scripts tests`
- `python3 scripts/check_ci_python.py --workflow .github/workflows/ci.yml --job validate --compile template/scripts --compile scripts --compile tests` (Python 3.11 compilation checked from the local Python 3.13 environment)
- `python3 -m ruff check scripts template/scripts tests`
- `python3 scripts/generate_platform_manifest.py --check`
- `python3 scripts/managed_projects.py validate`
- `python3 template/scripts/openspec_lifecycle.py check`
- `python3 scripts/check_docs_links.py`
- `openspec validate portable-finish-finalize --strict --no-interactive`
- `git diff --check`
- `PYTHONPATH=tests python3 -m unittest tests.test_archive_finalize_function tests.test_requirement_execution tests.test_portable_finish_check_reuse tests.test_independent_review tests.test_shared_writer_guard tests.test_finish_merged_queue` — 155 tests passed.
- `PYTHONPATH=tests python3 -m unittest -v tests.test_requirement_contribution_composition.ContributionTests` — 27 tests passed.

## Unresolved validation gates

- `python3 scripts/run_test_groups.py --all` refused before test execution: private managed-task lineage could not be verified by the early routing gate. Coverage discovery completed; the full suite did not run.
- A broader direct diagnostic run executed 241 tests and had five failures. The two change-caused failures (writer-site registry and obsolete guidance assertion) were repaired and pass in the final scoped run. The other three reproduce on an untouched snapshot of starting HEAD: two shared-workspace setgid/permission refusals and a configured machine-pool directory inaccessible from this sandbox.
- `python3 scripts/independent_review.py preflight portable-finish-finalize` failed because the configured Claude CLI was not logged in. No provider was switched and no independent runtime review was claimed.
- The friction checkpoint could not acquire the integration-owned lock outside the writable sandbox. The supervisor must review/record the observed lifecycle friction and resolve the checkpoint.

Task 3.1 remains open. No archive, commit, PR, publication or terminal-delivery claim was made for this task.
