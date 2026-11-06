# Verification

OpenSpec-Verify: INCOMPLETE
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario. No opsx tool invocation.
Automated-Checks-Evidence: none; delivery stopped before a full run passed

## Semantic assessment

- Stale candidate in review: `execute_job` installs `dev-platform/source-contract.toml` of the trusted root, whatever the candidate holds. The review harness and the repair harness receive the same file, and so does the composition review and repair stage. A disposable repository proves that a contract missing `main_branch` reads the trusted value.
- Valid candidate in review: the same test with a valid candidate contract shows the trusted text installed. The source does not depend on a schema result.
- Missing trusted contract: the job fails naming the file, and a job without a trusted root fails before any checkout.
- Stale copy after the merge: `install_source_contract` now replaces an untracked copy, so `checkout_harness` gives the harness the merged head's contract, and integration repair refreshes it before regeneration. The test reproduces the case found: the key is in the committed contract and missing from the installed copy.
- Committed project contract: installation returns when git tracks `.dev-platform.toml`; a test proves the file and the status stay clean, including with `contract_from`.
- No contract at the head: the job fails naming `dev-platform/source-contract.toml`; a head that lost its contract does not keep the old copy.
- Missing required key at finalize: `finalize_contract_gate` reads the contract at the exact head through the same `prepare_checkout` and `read_project_config` as the job, before claim. The refusal names the key and the exit. A `work_next` test proves no claim is posted and both release counts stay at zero. A composition finalize takes the same path, and unreadable TOML or a head with no contract refuses.
- Exit taken: a descendant head with a valid contract passes the gate. Its re-admission from `finalize-pending` is the existing path, unchanged and covered by its own tests.

## Deviation from the approved ADD

The ADD assumed the integration kinds read no contract before merging main. That part holds, but after the merge the harness read the copy installed at the candidate head. The coordinator chose to make the merged head the source for integration jobs, and the design and delta spec record this.

## Evidence

- `tests/test_stale_candidate_contract.py` runs against disposable git repositories. The worker, review gate, integration contour, composition and finalization test modules pass, run by hand.
- The only completed full run failed one test, in `test_parallel_lifecycle_acceptance`. After the fixture fix that module passes alone. The full rerun on 2fb8f0ca was not awaited, because the coordinator stopped delivery.

## Not verified

- No real stale candidate exists, so no job ran on GitHub with one. The integration path is proven at `checkout_harness`, not by a full integration-repair run on a stale candidate.
- The writer's own checkout keeps the copy from the candidate head. It is data only and the harness reads nothing from it, but a writer running repository scripts there sees that copy.
