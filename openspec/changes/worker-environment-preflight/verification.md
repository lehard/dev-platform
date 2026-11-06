# Verification: worker-environment-preflight

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Several conditions unmet: `run_preflight` evaluates every condition and one refusal names all; `tests/test_worker_preflight.py` proves two named at once. `work-next --run` exits 3 and `work_next` is never called.
- Selected job with an unready provider: `review_provider_gate` probes the job's providers after selection and before claim, once per provider, and lists a refusal. A worker with `--providers` keeps the accepted skip without a claim.
- Standalone check: `worker-preflight` prints every condition and reads no job. Run live on this operator node for all kinds without an exported token: every condition passed. A run without openspec on PATH refused naming it.
- Registered failure after claim: `EnvironmentFailure` carries a registered id; a test pins that the ids used in code are in the registry. `release_claim` writes the class, and `release_count` and `is_claimable` do not spend `MAX_RELEASES`.
- Finalize: `run_claimed_finalize` re-raises the class, so no `blocked-escalation` is recorded and the job stays claimable. Integration repair re-raises it before `fail`, so no attempt is spent.
- Candidate defect: any other exception stays an ordinary release; old `released` comments carry no class and count as before.
- Bound: `MAX_ENVIRONMENT_RELEASES` ends in `blocked-escalation` with `ENVIRONMENT_RELEASE_CAUSE`, which `operational_escalation` recognizes for review and repair and which finalize resume already accepts. Post-merge reaches its existing attention through `post_merge_release_limit`, per class.
- Post-merge runner: exit 3 ends the round as `environment` in the journal.

## Evidence

- `tests/test_worker_preflight.py`, `tests/test_worker_credentials.py`, `tests/test_post_merge_runner.py`, `tests/test_lifecycle_workers.py`, `tests/test_autonomous_integration_contour.py` pass; selected checks are recorded in `automated-checks.json`.

## Not verified

- No live queue run of the new job accounting: the live queue scenarios of the sibling Requirement are not in main at this handoff, so the accounting is proven by unit tests only.
- The environment release bound was not reached on real GitHub.
