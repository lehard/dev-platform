# Verification: worker-environment-preflight

OpenSpec-Verify: PASS
Verification-Method: documented equivalent semantic review of proposal, design, tasks and delta spec against the implementation, scenario by scenario. No opsx tool invocation.
Automated-Checks-Evidence: automated-checks.json

## Semantic assessment

- Several conditions unmet: `run_preflight` evaluates every condition and one refusal names all; `tests/test_worker_preflight.py` proves two named at once. `work-next --run` exits 3 and `work_next` is never called.
- Selected job with an unready provider: `review_provider_gate` probes the job's providers after selection and before claim, once per provider, and lists a refusal. A worker with `--providers` keeps the accepted skip without a claim.
- Standalone check: `worker-preflight` prints every condition and reads no job. Run live on this operator node for all kinds without an exported token: every condition passed. The executed script without openspec on PATH refused naming it, exit 3, no traceback.
- Registered failure after claim: the `EnvironmentFailure` constructor refuses an id outside `worker_preflight.CONDITION_IDS` with `ValueError`, so a typo stays an ordinary failure and spends budget; a test proves the refusal and another pins that the ids used in code are registered. `release_claim` writes the class, and `release_count` and `is_claimable` do not spend `MAX_RELEASES`.
- Finalize: `run_claimed_finalize` re-raises the class, so no `blocked-escalation` is recorded and the job stays claimable. Integration repair re-raises it before `fail`, so no attempt is spent.
- Candidate defect: any other exception stays an ordinary release; old `released` comments carry no class and count as before.
- Bound: `MAX_ENVIRONMENT_RELEASES` ends in `blocked-escalation` with `ENVIRONMENT_RELEASE_CAUSE`, which `operational_escalation` recognizes for review and repair and which finalize resume already accepts. Post-merge reaches its existing attention through `post_merge_release_limit`, per class.
- One class identity: the executed script used to be a second `__main__` copy of `lifecycle_workers`, so a class raised through an imported executor matched no `except` in `main`. It now runs through the importable module; a subprocess test proves the real script.
- Post-merge runner: exit 3 ends the round as `environment` in the journal.
- Provider gate scratch: the directory lives in a context manager around job selection; a test proves it is removed when selection raises.

## Re-verification after integration repair

Finalize of head 168c0162 stopped for fresh semantic verification: integration repair changed the task content after the first receipt. I read that delta and fixed two review advisories on top of it. This delta does not touch the other scenarios above; the refreshed selected checks in `automated-checks.json` rerun their tests.

- Integration repair changed only `tests/test_lifecycle_workers.py`: two tests now mock `provider_readiness` and `worker_preflight.run`, so they no longer depend on the local gh login and Claude token. Production behavior is unchanged and the tests still prove the same release and sandbox behavior.
- Review advisory `environment-condition-registry-not-enforced` (both perspectives) was a real gap between design and code. The constructor now enforces the design sentence, and all call sites pass registered ids.
- Review advisory `preflight-scratch-dir-leak` was real and is fixed. Neither fix changes the delta spec.

## Re-verification after the second review

The review of 2d078d28 raised one material finding and three advisories. I read each against the code.

- Material `overview-does-not-name-environment-condition`: confirmed. The escalation evidence now carries `condition`, and the overview reports `escalated-operational` with it for every job kind. Tests prove the evidence, the overview output and `resume` of a review with its attempts unchanged.
- While checking that scenario I found that `resume` never covered integration jobs, for this class or for any other escalation. Offering one again needs a fresh job id without spending an attempt, plus the integration red gate that the escalation replaced. That is a new behavior, so the delta and accepted spec now state the real boundary: `resume` lifts review, repair and finalize; a developer re-admission lifts an integration job. A test pins that the overview offers no `resume` for it.
- Advisory `standalone-preflight-unvalidated-kinds`: real and fixed. An unknown or empty `--kinds` exits 2 instead of passing with every condition not applicable.
- Advisory `runner-exit-code-duplicated-constant`: left as is. The runner runs apart from the template modules, and a test pins the value.
- Advisory `gh-token-decorator-blanket-mapping`: left as is. `active_gh_token` has one raise site, so nothing is misclassified today.

## Evidence

- `tests/test_worker_preflight.py`, `tests/test_worker_credentials.py`, `tests/test_post_merge_runner.py`, `tests/test_lifecycle_workers.py`, `tests/test_autonomous_integration_contour.py` pass; selected checks are recorded in `automated-checks.json`.

## Not verified

- No live queue run of the new job accounting: the live queue scenarios of the sibling Requirement are not in main at this handoff, so the accounting is proven by unit tests only.
- The environment release bound was not reached on real GitHub.
