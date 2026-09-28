# Verification: stabilize-bounded-recovery-helper-timeout-test

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of Requirement lehard/development-backlog#233, the active proposal, design, tasks and platform-ci delta against the accepted platform-ci contract and the implemented test; focused regression and parallel full-suite execution; strict OpenSpec validation.

Automated-Checks-Evidence: automated-checks.json

## Outcome and evidence

- The controlled child waits 0.4 seconds before printing and flushing `partial`, longer than the 0.3 second hung-helper timeout. The parent waits for a marker written after that flush before it starts the timeout. Starting the timeout at spawn would reproduce the original false negative.
- The existing assertions still require `HelperTimeout`, the helper description, its PID, and retained `partial` output. No retry or global timeout change was made.
- The test's readiness wait is bounded by the existing shared readiness helper; the child is killed in cleanup if an assertion fails.

## Automated checks

- `python3 -m unittest discover -s tests -p test_publication_recovery_cli.py -k BoundedTestDeadlineHelperTests`: passed, 3 tests.
- `python3 scripts/run_test_groups.py --all`: passed, all 13 parallel groups (1380 declared and discovered tests, no coverage gaps; 4 workers). The `publication_recovery_cli` group passed.
- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: passed (3 managed projects).
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `openspec validate stabilize-bounded-recovery-helper-timeout-test --strict`: passed.
- `git diff --check`: passed.

## Semantic OpenSpec review

- **Outcome:** The timeout test now proves the intended hung-helper behavior even when child startup is delayed longer than its short timeout.
- **Completeness:** The delta covers bounded readiness, delayed startup, retained output and process identity; the existing global deadline and no-retry invariant remain intact.
- **Correctness:** The marker is created after stdout flush, so the readiness condition precedes timeout measurement and makes the partial output available for collection. The helper still hangs until killed by the timeout path.
- **Coherence:** Requirement, proposal, design, delta, implementation and assertions describe the same single test repair. No production behavior or shared helper implementation changed.

The archive helper will generate `automated-checks.json` for the exact archive candidate; this marker names that expected evidence.
