# Proposal: Stabilize concurrent lifecycle tests

## Why

Mandatory tests currently confuse process-start scheduling delay and host contention with product regressions. This makes every lifecycle change more expensive and less trustworthy.

## What Changes

- Synchronize process fixtures on explicit readiness instead of fixed sleeps.
- Centralize a bounded diagnostic test timeout for publication recovery.
- Cap automatic test-group parallelism conservatively while preserving an explicit override.
- Keep genuine hangs visible and do not add blind retries.

## Success criteria

- The delegated-writer cleanup test proves process-group reap after a bounded
  readiness handshake, not a race with interpreter startup; a delayed child and
  a never-ready child are both covered.
- Publication-recovery helper subprocesses share one bounded deadline with an
  operator override and, on expiry, report process identity, state and retained
  output.
- Automatically selected test-group parallelism is capped host-independently;
  an explicit `DEV_PLATFORM_TEST_JOBS` (or `--jobs`) is used verbatim and
  recorded in aggregate evidence.
- A genuinely hung helper still fails within the bounded timeout; no automatic
  reruns are added.
- `python3 scripts/run_test_groups.py --all` passes at the default and at an
  explicitly set worker count.
