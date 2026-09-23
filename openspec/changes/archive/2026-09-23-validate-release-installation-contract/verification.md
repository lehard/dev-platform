# Verification: Release installation contract

## Method

`/opsx:verify` was not available in this runtime. I performed the documented equivalent manual semantic review: compared the proposal's outcome and success evidence and each `platform-ci` delta scenario with the implementation, real installed results, workflow placement, focused negative tests, and product-check boundary.

## Outcome and scenario evidence

- `scripts/validate_release_installation.py` runs real Copier copy and update into disposable repositories. The matrix covers GitHub platform and project harnesses and the supported GitLab platform harness for both fresh installation and upgrade. A clean full-history clone of `lehard/dev-platform` with this candidate applied passed the first five cases together; the added GitLab upgrade case passed separately with the same source and latest stable tag `v1.5.8`. The local shared checkout has an unrelated stale shallow marker, so it was not used to claim installation success.
- The shared `validate_platform_installation` routine is called by both managed rollout and the release matrix. It checks unresolved `.rej` files, staged and unstaged `git diff --check`, then executes the rendered `platform_doctor.py`. The matrix normalizes Copier answers with rollout's existing function before diff hygiene; the initial real run exposed a generated extra blank line and passed after this correction.
- Focused negative tests confirm reject detection, staged trailing whitespace, missing mandatory input, and missing selected capability surface cause failure. The latter two use a synthetic doctor fixture to verify that a doctor failure propagates through the shared validator; the real positive matrix executes the actual rendered doctor. Existing doctor/capability tests remain in the full suite.
- Central PR CI and the release publication job invoke the same repository-owned entrypoint; publication runs it before tag creation. The entrypoint calls no downstream selector or application command. Generated project CI and product-test ownership are unchanged.

## Checks performed

- `python3 scripts/validate_release_installation.py` in a fresh full-history clone with candidate files: five cases passed; separate real GitLab upgrade passed after the matrix was extended to six cases.
- `python3 -m unittest tests.test_release_installation_validation`: 10 passed.
- `python3 scripts/run_test_groups.py --all`: 13 groups, 1239 tests discovered and declared, all groups passed on the final run. An earlier run found an outdated rollout test expectation for the newly added staged diff check; it was corrected before the final run.
- `python3 -m compileall -q template/scripts scripts`, `python3 -m ruff check scripts template/scripts tests`, `python3 scripts/managed_projects.py validate`, and `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `npx --yes @fission-ai/openspec@1.13.0 validate --all --strict --no-interactive`: 34 items passed, 0 failed. Informational length notices concern existing specifications and the new change; no structural failure.

The remaining lifecycle steps are archive, commit, protected PR validation, merge, and local-main reconciliation; this receipt does not claim those steps have happened.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this runtime)
Automated-Checks-Evidence: automated-checks.json
