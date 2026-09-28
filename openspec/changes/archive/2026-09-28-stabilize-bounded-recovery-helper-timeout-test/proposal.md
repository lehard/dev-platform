# Proposal: Stabilize bounded recovery helper timeout test

## Why

The test starts a 0.3 second timeout immediately after launching Python. Under parallel load the child can be delayed before it emits `partial`, so the timeout correctly kills the process but the test incorrectly fails its retained-output assertion. This was observed in lehard/dev-platform#124.

## What changes

Synchronize the test with the helper's partial-output readiness before measuring its intentionally short hung-process timeout. Preserve the timeout and diagnostic checks.

## Success evidence

The focused test proves a controlled hung helper times out with identity and retained output. A representative parallel full-suite run passes without the scheduling false negative.

## Constraints and non-goals

Do not add retries, increase production or global test timeouts, weaken diagnostic assertions, or rework the shared test framework.
