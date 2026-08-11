# Verification: safe validation-feedback optimization

## Timing evidence

The accepted task package records the previous local full run at 457 seconds
for 323 tests and a 48-second required CI unit-test phase. Those figures are
historical context, not a basis for weakening the protected gate.

An isolated post-change protected-full run on 2026-08-11 completed
successfully in 218.49 seconds:

| Command | Outcome | Elapsed seconds |
| --- | --- | ---: |
| `python3 -m compileall -q template/scripts scripts` | success | 0.111 |
| `python3 scripts/managed_projects.py validate` | success | 0.081 |
| `python3 -m unittest discover -s tests -v` | success | 217.776 |
| `python3 template/scripts/openspec_lifecycle.py check` | success | 0.323 |

The selector now emits a `DEV_PLATFORM_CHECK_RESULT` JSON line for each of
these commands. Its elapsed time is useful feedback only; it does not replace
a protected PR run.

A deliberately contended experiment ran two full unit suites concurrently in
the same task worktree while another local validation process was active. Both
were still blocked in lifecycle/publication fixtures after 8 minutes and were
stopped with exit status 143. This is a negative benchmark, not a test
failure: it demonstrates that local concurrency currently has material
operational cost and cannot be used as evidence for safe CI partitioning.

## Partition-isolation audit

The candidate unit-test suite creates most fixture repositories in
`tempfile.TemporaryDirectory` locations. The audit also found lifecycle
fixtures that model fixed `/tmp/integration` paths and tests that patch
process-global environment state. No per-worker isolation contract, port
allocation contract, or aggregate-partition failure protocol exists yet.

Decision: retain the sequential full suite. No CI partitioning is introduced,
so the existing stable `platform-ci` / `checks` job identities remain the
authoritative protected checks. This is intentionally conservative; a future
parallelization proposal must first make every mutable resource worker-safe
or explicitly serialize it, then benchmark isolated and contended runs.

## Requirement review

- Command timing and bounded failure diagnostics are covered by
  `tests/test_select_checks.py`.
- The explicit `local-affected` and `protected-full` policies, unknown-path
  full fallback, and protected workflow invocation are covered by selector
  and generated-workflow contract tests.
- No local selected run can replace a protected check because the generated
  PR workflow calls `--mode protected-full` directly.

## Final validation

Before archive, the task ran compile checks, managed-project validation,
strict OpenSpec validation, lifecycle hygiene, the protected-full validation
set above, selector/workflow contract tests, and a standard-profile Copier
render plus generated doctor/selector smoke check.

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of all four added
`platform-lifecycle` requirements against the selector implementation,
protected PR workflow, regression tests, timing evidence, and documented
no-partition decision; structural validation used `openspec validate
optimize-platform-validation-feedback --strict`.
