## Why

Mandatory gates for publication and verification must not let work through when their own dependencies, configuration or data are missing or damaged. Review of the platform's blocking checks found fail-open code of one class: a no-op stand-in, a silently substituted default, a swallowed exception or a git failure read as a negative answer. In each case a conflicting or unverified change can proceed without any diagnostic. The repository rule is explicit: no fallbacks, no defaults that mask a missing input, no swallowed exceptions; absence of a required input is an explicit error, and an exception exists only by an explicit owner decision for a specific case.

## What Changes

- Multi-agent scope gate (`agent_board.hard_scope_conflicts`, `enforce_scope_gate`, stand-ins in `select_checks.py` and `finish_task.py`): when `[capabilities] agent_board` is `true`, a missing board path, missing or unreadable or invalid board file, non-list `items`, missing claim for the current worktree/branch, or an unimportable `agent_board` module stops the check and finish with a diagnostic. When it is explicitly `false`, the gate is documented as not applicable and the portable path is unchanged. A missing or non-boolean `agent_board` capability is itself an error.
- `main_branch` is read without a default wherever a protected or coordinator check uses it (`select_checks.py`, `agent_board.py`, `delegation_containment.verify_remote_fast_forward`); absence is an explicit error.
- `publication_queue.py`: carry-forward of gates from a superseded head fails when its lineage record is absent; git ancestry checks distinguish "not an ancestor" (exit 1) from a git failure (any other exit), which raises with the failing command and stderr instead of selecting the update-branch path.
- `candidate_lifecycle.first_record` / `latest_record`: a malformed trusted record raises the module's malformed-marker error naming the comment instead of being skipped.
- `delegation_containment.verify_remote_fast_forward`: unreadable config or a git failure raises instead of returning `False`.
- `run_test_groups.resolve_jobs`: an invalid `DEV_PLATFORM_TEST_JOBS` is an error naming the value.
- `integration_state.serialized_integration`: a platform without `fcntl` raises instead of running unlocked.
- `_platform_common`: a missing shared-workspace module raises instead of installing a no-op stand-in.
- A decision inventory of every examined site (fixed, or kept with the recorded reason) in `design.md`.

## Capabilities

### New Capabilities

- `gate-fail-explicit`: required gates stop explicitly on missing or corrupt dependencies, config or data.

## Impact

Touches `template/scripts/{agent_board,select_checks,finish_task,publication_queue,candidate_lifecycle,delegation_containment,run_test_groups,integration_state,_platform_common}.py` and their tests. Rendered downstream projects receive stricter behavior through the normal release; a project with `agent_board = false` is unaffected.

Upgrade note: a project whose `.dev-platform.toml` lacks `main_branch` (or has no `.dev-platform.toml` at the integration root for head-move verification) now fails explicitly instead of assuming `main`, and must add the key. Projects rendered from the template are not affected: `template/.dev-platform.toml.jinja` always renders `main_branch` (the copier question defaults to `main`). The public source contract `dev-platform/source-contract.toml` now carries the same `[capabilities]` table as the installed contract, since a clean CI checkout installs it as `.dev-platform.toml`.

## Non-goals

Friction routing and its config handling (separate requirement); an audit of every platform script for fallbacks (only publication and verification gates); changing gate semantics beyond failing explicitly; adding configuration switches that re-enable the removed fallbacks.
