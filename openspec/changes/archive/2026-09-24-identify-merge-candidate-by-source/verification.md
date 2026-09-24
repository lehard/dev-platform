# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, platform-lifecycle delta, exact generation diff, and regression behavior for corrected, identical and legacy manifests.
Automated-Checks-Evidence: automated-checks.json

New merge manifests derive their bounded namespace from both base and final source head while retaining full SHA values in the digest-bound manifest. A corrected child chain obtains a distinct candidate identity; an identical chain still fails on occupied branch/worktree. The legacy base-only manifest is accepted only when its exact inputs and digest match. This matches the authored lifecycle contract; no material finding remains.

Executed before archive:

- `python3 -m unittest tests.test_requirement_integration -v`: 22 tests passed, including new corrected-chain, collision and legacy cases.

The archive helper will run selected automated checks and record them in `automated-checks.json`. Protected PR CI and merge remain pending and are not claimed here.
