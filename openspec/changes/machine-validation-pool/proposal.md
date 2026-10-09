## Why

Several agents and lifecycle workers on one machine routinely run full validation at the same time (observed: load average ~550, three or four concurrent `run_test_groups.py --all` plus project Docker checks). Parallelism is capped only inside a single run (`run_test_groups.py`, auto 4 jobs), so N runs use 4N workers. Timeout-sensitive tests then fail from contention rather than regressions, and each failure triggers another full run. Content claims and the agent board coordinate repository scope, not the shared machine.

## What Changes

- New repository-owned module `machine_pool.py` providing a machine-wide counting pool built on kernel `flock` leases (released automatically when every holder process exits, including on SIGKILL), with all-or-nothing multi-token acquisition, a liveness-checked waiting queue ordered by priority class then arrival, load and available-memory admission, bounded wait, nested reuse and a read-only `status` command.
- The pool is opt-in per machine through the `DEV_PLATFORM_MACHINE_POOL` environment variable naming a machine-local TOML file. Unset means the declared unpooled mode and every acquiring run prints `DEV_PLATFORM_MACHINE_POOL: not configured`; a set but missing, unreadable or invalid configuration fails explicitly.
- `select_checks.py --execute`, `run_test_groups.py` (when not already inside a lease) and Requirement full-candidate validation acquire a lease before running heavy commands; nested invocations inherit the parent lease instead of acquiring again, and the test runner's parallelism is bounded by the lease weight.
- Lifecycle finalization and Requirement integration runs declare the `finalize` class and are admitted ahead of `development` runs.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: heavy validation runs coordinate through an opt-in machine-wide pool.

## Impact

`template/scripts/machine_pool.py` (new, with `scripts/` source adapter shim), `template/scripts/select_checks.py`, `template/scripts/run_test_groups.py`, `template/scripts/requirement_integration.py`, `template/scripts/post_review_finalization.py`, tests, `docs/engineering/agent-workflow.md` and its template copy. Projects receive the module through normal rollout; nothing changes for a machine that does not set the variable.

## Non-goals

Changing which checks run or reusing results (#468, #470); distributing work across machines or remote execution; optimizing tests; scheduling CI runners.
